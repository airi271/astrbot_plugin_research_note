import json
from datetime import datetime
from pathlib import Path

from astrbot.api import AstrBotConfig, FunctionTool, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .chunking import split_text_into_chunks
from .prompts import build_answer_prompt
from .store import NoteStore
from .tool_utils import (
    ResearchToolError,
    compact_search_results,
    get_document_summary,
    search_research_store,
)


@register(
    "ResearchNote",
    "airi271",
    "Research note assistant for source-grounded question answering.",
    "0.1.0",
)
class ResearchNotePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.data_dir = Path(__file__).parent / "data"
        self.notes_file = self.data_dir / "research_notes.json"
        self.store = NoteStore(self.notes_file)
        self._register_research_tools()

    # 生成新的 doc id，避免删除资料后重复使用旧 id。
    def _next_doc_id(self, documents: list[dict]) -> str:
        max_num = 0
        for document in documents:
            doc_id = str(document.get("id", ""))
            if not doc_id.startswith("doc_"):
                continue
            try:
                max_num = max(max_num, int(doc_id.removeprefix("doc_")))
            except ValueError:
                continue
        return f"doc_{max_num + 1:03d}"

    # 一个 document 内で chunk id を連番にする。
    def _chunk_id(self, doc_id: str, index: int) -> str:
        return f"chunk_{doc_id.removeprefix('doc_')}_{index:03d}"

    # 统一用户输入的资料 id，支持 "001"、"doc_001" 和旧的 "note_001" 写法。
    def _normalize_doc_id(self, doc_id: str) -> str:
        doc_id = doc_id.strip()
        if not doc_id:
            return ""
        if doc_id.startswith("doc_"):
            return doc_id
        if doc_id.startswith("note_"):
            return f"doc_{doc_id.removeprefix('note_')}"
        return f"doc_{doc_id}"

    # 从 /research 子命令后面提取用户输入的自由文本。
    def _extract_research_tail(self, event: AstrMessageEvent) -> str:
        raw_text = event.message_str.strip().removeprefix("/").strip()
        for prefix in (
            "research add",
            "research ask",
            "research show",
            "research delete",
            "research search",
        ):
            if raw_text.startswith(prefix):
                return raw_text[len(prefix) :].strip()
        return ""

    # 获取第一个可用的 embedding provider。
    def _get_embedding_provider(self):
        providers = self.context.get_all_embedding_providers()
        if not providers:
            return None
        return providers[0]

    # embedding API の長さ制限エラーだけを、追加分割で回復できるエラーとして扱う。
    def _is_embedding_length_error(self, error: Exception) -> bool:
        message = str(error).lower()
        return "context length" in message or "input length" in message

    # 長すぎる chunk はさらに分割し、全ての保存 chunk に embedding を付ける。
    async def _split_text_for_embedding(
        self,
        embedding_provider,
        text: str,
        min_chars: int = 80,
    ) -> list[tuple[str, list[float]]]:
        try:
            embedding = await embedding_provider.get_embedding(text)
            return [(text, embedding)]
        except Exception as exc:
            if len(text) <= min_chars or not self._is_embedding_length_error(exc):
                raise
            midpoint = len(text) // 2
            parts = []
            for part in (text[:midpoint].strip(), text[midpoint:].strip()):
                if part:
                    parts.extend(
                        await self._split_text_for_embedding(
                            embedding_provider,
                            part,
                            min_chars=min_chars,
                        )
                    )
            return parts

    # prompt と検索用に chunk へ document metadata を付ける。
    def _chunks_with_document_metadata(self, store: dict) -> list[dict]:
        documents_by_id = {doc.get("id"): doc for doc in store["documents"]}
        chunks = []
        for chunk in store["chunks"]:
            document = documents_by_id.get(chunk.get("doc_id"), {})
            enriched = dict(chunk)
            enriched["title"] = document.get("title", "")
            enriched["source_uri"] = document.get("source_uri", "")
            chunks.append(enriched)
        return chunks

    def _chunks_from_search_results(self, results: list[dict]) -> list[dict]:
        chunks = []
        for result in results:
            chunk = dict(result["chunk"])
            document = result.get("document", {})
            chunk["title"] = document.get("title", "")
            chunk["source_uri"] = document.get("source_uri", "")
            chunk["embedding_score"] = result.get("embedding_score", 0.0)
            chunks.append(chunk)
        return chunks

    async def _add_document_from_text(
        self,
        content: str,
        title: str = "",
        source_type: str = "text",
        source_uri: str = "",
        tags: list[str] | None = None,
    ) -> dict:
        content = content.strip()
        if not content:
            raise ResearchToolError("content_required")

        max_add_chars = int(self.config.get("max_add_chars", 8000))
        if len(content) > max_add_chars:
            raise ResearchToolError("content_too_long")

        embedding_provider = self._get_embedding_provider()
        if not embedding_provider:
            raise ResearchToolError("embedding_provider_missing")

        store = self.store.load_store()
        now = datetime.now().isoformat(timespec="seconds")
        doc_id = self._next_doc_id(store["documents"])
        document = {
            "id": doc_id,
            "project_id": "default",
            "title": title.strip() or content.replace("\n", " ")[:60] or doc_id,
            "source_type": source_type,
            "source_uri": source_uri,
            "tags": tags or [],
            "created_at": now,
            "updated_at": now,
        }

        chunk_texts = split_text_into_chunks(
            content,
            chunk_size=int(self.config.get("chunk_size", 800)),
            chunk_overlap=int(self.config.get("chunk_overlap", 120)),
        )
        try:
            embedded_chunks = []
            for chunk_text in chunk_texts:
                embedded_chunks.extend(
                    await self._split_text_for_embedding(embedding_provider, chunk_text)
                )
        except Exception as exc:
            raise ResearchToolError("embedding_failed") from exc

        chunks = []
        for index, (chunk_text, embedding) in enumerate(embedded_chunks):
            chunks.append(
                {
                    "id": self._chunk_id(doc_id, index),
                    "doc_id": doc_id,
                    "index": index,
                    "content": chunk_text,
                    "embedding": embedding,
                    "metadata": {},
                }
            )

        store["documents"].append(document)
        store["chunks"].extend(chunks)
        self.store.save_store(store)
        return {"document": document, "chunks": chunks}

    def _tool_error_message(self, error: ResearchToolError) -> str:
        messages = {
            "embedding_provider_missing": "embedding provider が設定されていません。",
            "empty_store": "保存済み資料がありません。先に /research add で資料を追加してください。",
            "missing_embedding": "embedding がない chunk があります。/research reindex を実行してください。",
            "query_embedding_failed": "検索 query の embedding 作成に失敗しました。",
            "content_required": "保存する本文を入力してください。",
            "content_too_long": "資料が長すぎます。",
            "embedding_failed": "embedding の作成に失敗したため、資料は保存しませんでした。",
        }
        return messages.get(error.code, "Research Note tool の実行に失敗しました。")

    def _register_research_tools(self) -> None:
        # 先に読み取り専用 tool だけを登録する。書き込み tool は確認フローを作ってから追加する。
        self.context.add_llm_tools(
            FunctionTool(
                name="research_search",
                description=(
                    "Search saved Research Note documents with embedding search. "
                    "Use this for questions about stored research materials."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query or research question.",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Maximum number of chunks to return.",
                        },
                    },
                    "required": ["query"],
                },
                handler=self._research_search_tool,
            ),
            FunctionTool(
                name="research_get_document",
                description=(
                    "Get metadata and chunk previews for a saved Research Note document."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "doc_id": {
                            "type": "string",
                            "description": "Document ID such as doc_001.",
                        }
                    },
                    "required": ["doc_id"],
                },
                handler=self._research_get_document_tool,
            ),
            FunctionTool(
                name="research_list_documents",
                description=(
                    "List saved Research Note documents with IDs, titles, and chunk counts."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of documents to return.",
                        }
                    },
                },
                handler=self._research_list_documents_tool,
            ),
            FunctionTool(
                name="research_add_text",
                description=(
                    "Save text into Research Note as an embedded document. "
                    "Only use this when the user clearly asks to save or remember text."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Text content to save.",
                        },
                        "title": {
                            "type": "string",
                            "description": "Optional document title.",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional tags.",
                        },
                    },
                    "required": ["content"],
                },
                handler=self._research_add_text_tool,
            ),
            FunctionTool(
                name="research_delete_document",
                description=(
                    "Delete a saved Research Note document and its chunks. "
                    "Only use this when the user explicitly asks to delete a specific doc_id. "
                    "The confirm_doc_id argument must exactly match doc_id."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "doc_id": {
                            "type": "string",
                            "description": "Document ID to delete, such as doc_001.",
                        },
                        "confirm_doc_id": {
                            "type": "string",
                            "description": "Must exactly match doc_id to confirm deletion.",
                        },
                    },
                    "required": ["doc_id", "confirm_doc_id"],
                },
                handler=self._research_delete_document_tool,
            ),
        )

    async def _research_search_tool(
        self,
        *args,
        **kwargs,
    ) -> str:
        query = str(kwargs.get("query") or self._first_tool_arg(args, 1)).strip()
        top_k = kwargs.get("top_k")
        if not query:
            return json.dumps({"error": "query_required"}, ensure_ascii=False)
        try:
            top_k_value = (
                int(top_k) if top_k is not None else int(self.config.get("top_k", 3))
            )
        except (TypeError, ValueError):
            top_k_value = int(self.config.get("top_k", 3))
        try:
            _, results = await search_research_store(
                self.store,
                query,
                top_k=top_k_value,
                embedding_provider=self._get_embedding_provider(),
                min_embedding_score=float(self.config.get("min_embedding_score", 0.0)),
            )
        except ResearchToolError as exc:
            return json.dumps({"error": exc.code}, ensure_ascii=False)
        return json.dumps(compact_search_results(results), ensure_ascii=False)

    async def _research_get_document_tool(
        self,
        *args,
        **kwargs,
    ) -> str:
        doc_id = str(kwargs.get("doc_id") or self._first_tool_arg(args, 1)).strip()
        if not doc_id:
            return json.dumps({"error": "doc_id_required"}, ensure_ascii=False)
        normalized_doc_id = self._normalize_doc_id(doc_id)
        return json.dumps(
            get_document_summary(self.store, normalized_doc_id),
            ensure_ascii=False,
        )

    async def _research_list_documents_tool(self, *args, **kwargs) -> str:
        limit = kwargs.get("limit")
        try:
            limit_value = int(limit) if limit is not None else 10
        except (TypeError, ValueError):
            limit_value = 10

        store = self.store.load_store()
        chunk_counts = {}
        for chunk in store["chunks"]:
            doc_id = chunk.get("doc_id")
            chunk_counts[doc_id] = chunk_counts.get(doc_id, 0) + 1

        documents = []
        for document in store["documents"][: max(1, min(limit_value, 50))]:
            doc_id = document.get("id", "")
            documents.append(
                {
                    "doc_id": doc_id,
                    "title": document.get("title", ""),
                    "source_type": document.get("source_type", ""),
                    "source_uri": document.get("source_uri", ""),
                    "tags": document.get("tags", []),
                    "chunk_count": chunk_counts.get(doc_id, 0),
                    "created_at": document.get("created_at", ""),
                }
            )
        return json.dumps({"documents": documents}, ensure_ascii=False)

    async def _research_add_text_tool(self, *args, **kwargs) -> str:
        content = str(kwargs.get("content") or self._first_tool_arg(args, 1)).strip()
        title = str(kwargs.get("title") or "").strip()
        raw_tags = kwargs.get("tags") or []
        if isinstance(raw_tags, str):
            raw_tags = [raw_tags]
        tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()]
        try:
            saved = await self._add_document_from_text(
                content,
                title=title,
                source_type="tool_text",
                tags=tags,
            )
        except ResearchToolError as exc:
            return json.dumps({"error": exc.code}, ensure_ascii=False)

        document = saved["document"]
        return json.dumps(
            {
                "doc_id": document.get("id"),
                "title": document.get("title", ""),
                "chunk_count": len(saved["chunks"]),
                "embedding": "created_for_all_chunks",
            },
            ensure_ascii=False,
        )

    async def _research_delete_document_tool(self, *args, **kwargs) -> str:
        doc_id = str(kwargs.get("doc_id") or self._first_tool_arg(args, 1)).strip()
        confirm_doc_id = str(kwargs.get("confirm_doc_id") or "").strip()
        normalized_doc_id = self._normalize_doc_id(doc_id)
        normalized_confirm_doc_id = self._normalize_doc_id(confirm_doc_id)
        if not normalized_doc_id:
            return json.dumps({"error": "doc_id_required"}, ensure_ascii=False)
        if normalized_doc_id != normalized_confirm_doc_id:
            return json.dumps(
                {
                    "error": "confirmation_mismatch",
                    "doc_id": normalized_doc_id,
                },
                ensure_ascii=False,
            )

        store = self.store.load_store()
        old_document_count = len(store["documents"])
        store["documents"] = [
            doc for doc in store["documents"] if doc.get("id") != normalized_doc_id
        ]
        if len(store["documents"]) == old_document_count:
            return json.dumps(
                {"error": "document_not_found", "doc_id": normalized_doc_id},
                ensure_ascii=False,
            )

        old_chunk_count = len(store["chunks"])
        store["chunks"] = [
            chunk for chunk in store["chunks"] if chunk.get("doc_id") != normalized_doc_id
        ]
        self.store.save_store(store)
        return json.dumps(
            {
                "deleted_doc_id": normalized_doc_id,
                "deleted_chunks": old_chunk_count - len(store["chunks"]),
            },
            ensure_ascii=False,
        )

    def _first_tool_arg(self, args: tuple, index: int):
        if len(args) > index:
            return args[index]
        return ""

    async def initialize(self):
        """Optional async initialization hook."""

    @filter.command_group("research")
    def research_group(self):
        """Research Note commands."""
        pass

    @research_group.command("help")
    async def research_help(self, event: AstrMessageEvent):
        """Research Note の使い方を表示します。"""
        text = """Research Note commands:
    /research add <text> - 資料を追加
    /research list - 資料一覧
    /research show <doc_id> - 指定した資料を表示
    /research search <query> - embedding 検索結果を表示
    /research ask <question> - 資料に基づいて質問
    /research delete <doc_id> --confirm - 指定した資料を削除
    /research reindex - 既存資料の embedding を再作成
    /research clear --confirm - 全資料を削除
    /research help - このヘルプを表示
    """
        yield event.plain_result(text)

    @research_group.command("add")
    async def research_add(self, event: AstrMessageEvent, content: str = ""):
        """資料を追加します。"""
        # 先读取并检查文本，再分割为 chunks。
        content = self._extract_research_tail(event)
        if not content:
            yield event.plain_result("追加する資料テキストを入力してください。")
            return

        max_add_chars = int(self.config.get("max_add_chars", 8000))
        if len(content) > max_add_chars:
            yield event.plain_result(f"資料が長すぎます。最大 {max_add_chars} 文字までです。")
            return

        try:
            saved = await self._add_document_from_text(content)
        except ResearchToolError as exc:
            if exc.code == "embedding_failed":
                logger.error(
                    "Failed to generate embeddings for added document.", exc_info=True
                )
            yield event.plain_result(self._tool_error_message(exc))
            return

        document = saved["document"]
        chunks = saved["chunks"]
        if not chunks:
            logger.error("Added document has no chunks.", exc_info=True)
            yield event.plain_result("資料の保存に失敗しました。")
            return

        yield event.plain_result(
            f"資料を保存しました: {document['id']}\n"
            f"chunks: {len(chunks)}\n"
            "embedding: 全 chunk 作成済み"
        )

    @research_group.command("list")
    async def research_list(self, event: AstrMessageEvent):
        """保存済み資料を表示します。"""
        # 列表中只显示 document 和 chunk 数，避免长资料刷屏。
        store = self.store.load_store()
        documents = store["documents"]
        if not documents:
            yield event.plain_result("保存済み資料はありません。")
            return

        chunk_counts = {}
        for chunk in store["chunks"]:
            doc_id = chunk.get("doc_id")
            chunk_counts[doc_id] = chunk_counts.get(doc_id, 0) + 1

        lines = ["保存済み資料:"]
        for document in documents[:10]:
            doc_id = document.get("id", "unknown")
            title = document.get("title") or doc_id
            lines.append(
                f"- {doc_id}: {title} (chunks: {chunk_counts.get(doc_id, 0)})"
            )
        yield event.plain_result("\n".join(lines))

    @research_group.command("show")
    async def research_show(self, event: AstrMessageEvent, doc_id: str = ""):
        """保存済み資料を表示します。"""
        # 显示单条资料及其 chunk preview，方便检查资料和引用。
        doc_id = self._normalize_doc_id(self._extract_research_tail(event))
        if not doc_id:
            yield event.plain_result("資料IDを指定してください。")
            return

        store = self.store.load_store()
        if not store["documents"]:
            yield event.plain_result("保存済み資料はありません。")
            return

        document = next(
            (doc for doc in store["documents"] if doc.get("id") == doc_id), None
        )
        if not document:
            yield event.plain_result("指定された資料が見つかりません。")
            return

        chunks = [chunk for chunk in store["chunks"] if chunk.get("doc_id") == doc_id]
        chunk_lines = []
        for chunk in chunks[:5]:
            preview = str(chunk.get("content", "")).replace("\n", " ")[:120]
            has_embedding = isinstance(chunk.get("embedding"), list)
            chunk_lines.append(
                f"- {chunk.get('id', 'unknown')}: {preview} "
                f"(embedding: {'あり' if has_embedding else 'なし'})"
            )
        yield event.plain_result(
            f"資料: {document['id']}\n"
            f"title: {document.get('title', '')}\n"
            f"source: {document.get('source_type', 'text')}\n"
            f"source_uri: {document.get('source_uri', '')}\n"
            f"作成日時: {document.get('created_at', 'unknown')}\n"
            f"chunks: {len(chunks)}\n\n"
            f"chunk preview:\n" + "\n".join(chunk_lines)
        )

    @research_group.command("ask")
    async def research_ask(self, event: AstrMessageEvent, question: str = ""):
        """資料に基づいて質問します。"""
        # ask 是固定 RAG 流程：先检索 chunks，再构造 prompt，最后调用 LLM。
        question = self._extract_research_tail(event)
        if not question:
            yield event.plain_result("質問を入力してください。")
            return

        store = self.store.load_store()
        chunks = self._chunks_with_document_metadata(store)
        if not chunks:
            yield event.plain_result(
                "保存済み資料がありません。先に /research add で資料を追加してください。"
            )
            return

        top_k = int(self.config.get("top_k", 3))
        embedding_provider = self._get_embedding_provider()
        if not embedding_provider:
            yield event.plain_result("embedding provider が設定されていません。")
            return

        if any(not isinstance(chunk.get("embedding"), list) for chunk in chunks):
            yield event.plain_result(
                "embedding がない chunk があります。/research reindex を実行してください。"
            )
            return

        try:
            _, results = await search_research_store(
                self.store,
                question,
                top_k=top_k,
                embedding_provider=embedding_provider,
                min_embedding_score=float(self.config.get("min_embedding_score", 0.0)),
            )
        except ResearchToolError as exc:
            if exc.code == "query_embedding_failed":
                logger.error(
                    "Failed to generate embedding for question.", exc_info=True
                )
            yield event.plain_result(self._tool_error_message(exc))
            return

        logger.info(
            f"Found {len(results)} matched chunks using embedding search."
        )

        if not results:
            yield event.plain_result("関連する資料が見つかりませんでした。")
            return

        matched_chunks = self._chunks_from_search_results(results)

        # prompt 构造放在 prompts.py 中，保持命令逻辑简洁。
        prompt = build_answer_prompt(
            question,
            matched_chunks,
            max_note_chars=int(self.config.get("max_note_chars", 1200)),
            max_context_chars=int(self.config.get("max_context_chars", 6000)),
            strict_grounding=self.config.get("strict_grounding", True),
        )
        try:
            # 未配置 chat provider 时，这里可能会失败。
            provider_id = await self.context.get_current_chat_provider_id(
                umo=event.unified_msg_origin
            )
        except Exception:
            logger.error("Failed to get current chat provider.", exc_info=True)
            yield event.plain_result("利用可能な LLM provider が見つかりません。")
            return

        llm_resp = await self.context.llm_generate(
            chat_provider_id=provider_id,
            prompt=prompt,
        )
        answer = llm_resp.completion_text if llm_resp else "回答を生成できませんでした。"
        source_ids = ", ".join(
            f"{chunk.get('doc_id', 'unknown')}/{chunk.get('id', 'unknown')}"
            for chunk in matched_chunks
        )
        result = f"{answer}\n\n使用資料: {source_ids}"
        # debug prompt 只在开发时显示，默认不输出给用户。
        if self.config.get("show_debug_prompt", False):
            result += f"\n\nprompt:\n{prompt}"
        yield event.plain_result(result)

    @research_group.command("search")
    async def research_search(self, event: AstrMessageEvent, query: str = ""):
        """embedding 検索結果を表示します。"""
        query = self._extract_research_tail(event)
        if not query:
            yield event.plain_result("検索 query を入力してください。")
            return

        embedding_provider = self._get_embedding_provider()
        if not embedding_provider:
            yield event.plain_result("embedding provider が設定されていません。")
            return

        store = self.store.load_store()
        if not store["chunks"]:
            yield event.plain_result(
                "保存済み資料がありません。先に /research add で資料を追加してください。"
            )
            return
        if any(
            not isinstance(chunk.get("embedding"), list) for chunk in store["chunks"]
        ):
            yield event.plain_result(
                "embedding がない chunk があります。/research reindex を実行してください。"
            )
            return

        try:
            _, results = await search_research_store(
                self.store,
                query,
                top_k=int(self.config.get("top_k", 3)),
                embedding_provider=embedding_provider,
                min_embedding_score=float(self.config.get("min_embedding_score", 0.0)),
            )
        except ResearchToolError as exc:
            if exc.code == "query_embedding_failed":
                logger.error(
                    "Failed to generate embedding for search query.", exc_info=True
                )
            yield event.plain_result(self._tool_error_message(exc))
            return

        if not results:
            yield event.plain_result("関連する資料が見つかりませんでした。")
            return

        lines = ["検索結果:"]
        for index, result in enumerate(results, start=1):
            chunk = result["chunk"]
            document = result.get("document", {})
            preview = str(chunk.get("content", "")).replace("\n", " ")[:100]
            lines.append(
                f"{index}. {chunk.get('doc_id')}/{chunk.get('id')} "
                f"score={result.get('embedding_score', 0.0):.3f}\n"
                f"   title: {document.get('title', '')}\n"
                f"   preview: {preview}"
            )
        yield event.plain_result("\n".join(lines))

    @research_group.command("delete")
    async def research_delete(
        self,
        event: AstrMessageEvent,
        doc_id: str = "",
        confirm: str | None = None,
    ):
        """保存済み資料を削除します。"""
        # 删除类操作必须显式确认。
        raw_tail = self._extract_research_tail(event)
        if confirm != "--confirm":
            if raw_tail.endswith("--confirm"):
                confirm = "--confirm"
            else:
                yield event.plain_result(
                    "削除するには /research delete <doc_id> --confirm を実行してください。"
                )
                return

        doc_id = self._normalize_doc_id(raw_tail.replace("--confirm", "").strip())
        if not doc_id:
            yield event.plain_result("資料IDを指定してください。")
            return

        # document と関連 chunk をまとめて削除する。
        store = self.store.load_store()
        if not store["documents"]:
            yield event.plain_result("保存済み資料はありません。")
            return

        new_documents = [
            doc for doc in store["documents"] if doc.get("id") != doc_id
        ]
        if len(new_documents) == len(store["documents"]):
            yield event.plain_result("指定された資料が見つかりません。")
            return

        store["documents"] = new_documents
        store["chunks"] = [
            chunk for chunk in store["chunks"] if chunk.get("doc_id") != doc_id
        ]
        self.store.save_store(store)
        yield event.plain_result(f"資料を削除しました: {doc_id}")

    @research_group.command("reindex")
    async def research_reindex(self, event: AstrMessageEvent):
        """既存資料の embedding を再作成します。"""
        # reindex 用于给 chunks 重新生成 embedding。
        embedding_provider = self._get_embedding_provider()
        if not embedding_provider:
            yield event.plain_result("embedding provider が設定されていません。")
            return

        store = self.store.load_store()
        if not store["chunks"]:
            yield event.plain_result("保存済み資料はありません。")
            return

        updated = 0
        counters = {}
        new_chunks = []
        for chunk in store["chunks"]:
            content = str(chunk.get("content", ""))
            if not content:
                continue
            try:
                embedded_chunks = await self._split_text_for_embedding(
                    embedding_provider, content
                )
            except Exception:
                logger.error("Failed to regenerate chunk embedding.", exc_info=True)
                yield event.plain_result(
                    "embedding の再作成に失敗したため、変更は保存しませんでした。"
                    "chunk_size を小さくして再試行してください。"
                )
                return

            doc_id = chunk.get("doc_id", "")
            for chunk_text, embedding in embedded_chunks:
                index = counters.get(doc_id, 0)
                counters[doc_id] = index + 1
                new_chunk = dict(chunk)
                new_chunk["id"] = self._chunk_id(doc_id, index)
                new_chunk["index"] = index
                new_chunk["content"] = chunk_text
                new_chunk["embedding"] = embedding
                new_chunks.append(new_chunk)
                updated += 1

        store["chunks"] = new_chunks
        self.store.save_store(store)
        yield event.plain_result(f"embedding を再作成しました: {updated} 件")

    @research_group.command("clear")
    async def research_clear(self, event: AstrMessageEvent, confirm: str | None = None):
        """保存済み資料をすべて削除します。"""
        # clear 会删除全部资料，因此必须要求 --confirm。
        if confirm != "--confirm":
            yield event.plain_result("削除するには /research clear --confirm を実行してください。")
            return
        self.store.save_store({"schema_version": 2, "documents": [], "chunks": []})
        yield event.plain_result("保存済み資料をすべて削除しました。")

    async def terminate(self):
        """Optional async cleanup hook."""
