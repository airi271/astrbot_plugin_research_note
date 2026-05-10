import json
from datetime import datetime
from pathlib import Path

from astrbot.api import AstrBotConfig, FunctionTool, ToolSet, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.tools.registry import get_builtin_tool_name, iter_builtin_tool_classes

from .agent_prompts import (
    build_mcp_research_agent_system_prompt,
    build_research_agent_system_prompt,
    build_web_research_agent_system_prompt,
)
from .chunking import split_text_into_chunks
from .importers.url_importer import fetch_url_text
from .pending_imports import PendingImportStore
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
        self.pending_imports = PendingImportStore(self.data_dir / "pending_imports.json")
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

    def _format_chunk_detail(self, document: dict, chunk: dict) -> str:
        has_embedding = isinstance(chunk.get("embedding"), list)
        return (
            f"資料: {document.get('id', '')}\n"
            f"title: {document.get('title', '')}\n"
            f"source: {document.get('source_type', 'text')}\n"
            f"source_uri: {document.get('source_uri', '')}\n"
            f"chunk: {chunk.get('id', 'unknown')}\n"
            f"index: {chunk.get('index', 'unknown')}\n"
            f"embedding: {'あり' if has_embedding else 'なし'}\n\n"
            f"content:\n{chunk.get('content', '')}"
        )

    # 从 /research 子命令后面提取用户输入的自由文本。
    def _extract_research_tail(self, event: AstrMessageEvent) -> str:
        raw_text = event.message_str.strip().removeprefix("/").strip()
        for prefix in (
            "research add",
            "research ask",
            "research show",
            "research delete",
            "research search",
            "research agent_mcp",
            "research agent_web",
            "research agent",
            "research import_text",
            "research import_url",
            "research import_confirm",
            "research import",
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
        max_chars: int | None = None,
    ) -> dict:
        content = content.strip()
        if not content:
            raise ResearchToolError("content_required")

        max_add_chars = max_chars or int(self.config.get("max_add_chars", 8000))
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
            "import_not_found": "指定された pending import が見つかりません。",
        }
        return messages.get(error.code, "Research Note tool の実行に失敗しました。")

    def _build_import_preview(self, payload: dict, pending_id: str) -> str:
        content = str(payload.get("content", ""))
        preview_chars = int(self.config.get("import_preview_chars", 800))
        chunk_count = len(
            split_text_into_chunks(
                content,
                chunk_size=int(self.config.get("chunk_size", 800)),
                chunk_overlap=int(self.config.get("chunk_overlap", 120)),
            )
        )
        source_uri = payload.get("source_uri") or ""
        source_line = f"source: {source_uri}\n" if source_uri else ""
        return (
            "Import preview\n"
            f"id: {pending_id}\n"
            f"title: {payload.get('title', '')}\n"
            f"source_type: {payload.get('source_type', 'text')}\n"
            f"{source_line}"
            f"chars: {len(content)}\n"
            f"chunks: {chunk_count}\n\n"
            f"preview:\n{content[:preview_chars]}\n\n"
            f"保存するには: /research import confirm {pending_id}"
        )

    def _add_pending_import(self, payload: dict) -> tuple[str, dict]:
        max_import_chars = int(self.config.get("max_import_chars", 50000))
        content = str(payload.get("content", "")).strip()
        if not content:
            raise ResearchToolError("content_required")
        payload = dict(payload)
        payload["content"] = content[:max_import_chars]
        payload["title"] = str(payload.get("title") or content.replace("\n", " ")[:60])
        payload["source_type"] = str(payload.get("source_type") or "text")
        payload["source_uri"] = str(payload.get("source_uri") or "")
        return self.pending_imports.add(payload), payload

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

    def _get_research_tool_set(self) -> ToolSet:
        tool_manager = self.context.get_llm_tool_manager()
        tool_names = (
            "research_search",
            "research_get_document",
            "research_list_documents",
            "research_add_text",
            "research_delete_document",
        )
        tools = []
        for name in tool_names:
            tool = tool_manager.get_func(name)
            if tool:
                tools.append(tool)
        return ToolSet(tools)

    def _get_web_research_tool_set(self) -> ToolSet:
        tools = list(self._get_research_tool_set().tools)
        tool_manager = self.context.get_llm_tool_manager()
        safe_web_tool_names = {
            "web_search_baidu",
            "web_search_tavily",
            "tavily_extract_web_page",
            "web_search_bocha",
            "web_search_brave",
            "web_search_firecrawl",
            "firecrawl_extract_web_page",
        }
        raw_allowed_names = self.config.get(
            "allowed_web_tools",
            ["web_search_tavily", "tavily_extract_web_page"],
        )
        if isinstance(raw_allowed_names, str):
            allowed_names = [
                name.strip() for name in raw_allowed_names.split(",") if name.strip()
            ]
        else:
            allowed_names = [
                str(name).strip()
                for name in raw_allowed_names
                if str(name).strip()
            ]

        for name in allowed_names:
            if name not in safe_web_tool_names:
                logger.warning(f"Ignored non-web tool in allowed_web_tools: {name}")
                continue
            tool = tool_manager.get_func(name)
            if not tool:
                logger.warning(f"Configured web tool not found: {name}")
                continue
            tools.append(tool)
        return ToolSet(tools)

    def _config_list(self, name: str, default: list[str] | None = None) -> list[str]:
        raw_value = self.config.get(name, default or [])
        if raw_value is None:
            return []
        if isinstance(raw_value, str):
            return [item.strip() for item in raw_value.split(",") if item.strip()]
        if not isinstance(raw_value, list | tuple):
            return [str(raw_value).strip()] if str(raw_value).strip() else []
        return [str(item).strip() for item in raw_value if str(item).strip()]

    def _get_mcp_research_tool_set(self) -> ToolSet:
        tool_set = ToolSet(list(self._get_research_tool_set().tools))
        tool_manager = self.context.get_llm_tool_manager()

        builtin_tool_names = {
            "astrbot_file_read_tool",
            "astrbot_grep_tool",
            "astrbot_download_file",
            "astrbot_upload_file",
            "astrbot_file_write_tool",
            "astrbot_file_edit_tool",
            "astrbot_execute_python",
            "astrbot_execute_ipython",
            "astrbot_execute_shell",
            "astr_kb_search",
            "web_search_tavily",
            "tavily_extract_web_page",
            "web_search_baidu",
            "web_search_bocha",
            "web_search_brave",
            "web_search_firecrawl",
            "firecrawl_extract_web_page",
        }
        if self.config.get("allow_all_builtin_tools", False):
            builtin_tool_names.update(
                name
                for tool_cls in iter_builtin_tool_classes()
                if (name := get_builtin_tool_name(tool_cls))
            )

        denied_builtin_tools = set(self._config_list("denied_builtin_tools"))
        dangerous_builtin_tools = {
            "astrbot_download_file",
            "astrbot_upload_file",
            "astrbot_file_write_tool",
            "astrbot_file_edit_tool",
            "astrbot_execute_python",
            "astrbot_execute_ipython",
            "astrbot_execute_shell",
        }

        if self.config.get("allow_all_builtin_tools", False):
            allowed_builtin_names = sorted(builtin_tool_names)
        else:
            allowed_builtin_names = self._config_list(
                "allowed_builtin_tools",
                [
                "astrbot_file_read_tool",
                "astrbot_grep_tool",
                "astr_kb_search",
                "web_search_tavily",
                    "tavily_extract_web_page",
                ],
            )

        for name in allowed_builtin_names:
            if name in denied_builtin_tools:
                logger.warning(f"Denied builtin tool for agent_mcp: {name}")
                continue
            if name not in builtin_tool_names:
                logger.warning(f"Ignored unsupported builtin tool: {name}")
                continue
            if name in dangerous_builtin_tools:
                logger.warning(f"Allowed high-risk builtin tool for agent_mcp: {name}")
            tool = tool_manager.get_func(name)
            if not tool:
                logger.warning(f"Configured builtin tool not found: {name}")
                continue
            tool_set.add_tool(tool)

        mcp_tools_by_name = {
            tool.name: tool
            for tool in tool_manager.func_list
            if not str(tool.name).startswith("research_")
        }
        for name in self._config_list("allowed_mcp_tools"):
            tool = mcp_tools_by_name.get(name)
            if not tool:
                logger.warning(f"Configured MCP tool not found: {name}")
                continue
            tool_set.add_tool(tool)
        return tool_set

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
    /research show <doc_id> - 指定した資料と chunk preview を表示
    /research show <doc_id> <chunk_index|chunk_id> - 指定した chunk 本文を表示
    /research show <chunk_id> - 指定した chunk 本文を表示
    /research search <query> - embedding 検索結果を表示
    /research ask <question> - 資料に基づいて質問
    /research agent <task> - Research Note tools を使って調査
    /research agent_web <task> - 保存済み資料と Web Search で調査
    /research agent_mcp <task> - 保存済み資料と許可済み MCP / AstrBot tools で調査
    /research import text <text> - preview 後に資料として取り込み
    /research import url <url> - URL を preview 後に資料として取り込み
    /research import confirm <id> - preview 済み import を保存
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
        # 显示单条资料及其 chunk preview，也支持查看具体 chunk 本文。
        raw_tail = self._extract_research_tail(event)
        if not raw_tail:
            yield event.plain_result("資料IDまたは chunk ID を指定してください。")
            return

        store = self.store.load_store()
        if not store["documents"]:
            yield event.plain_result("保存済み資料はありません。")
            return

        documents_by_id = {doc.get("id"): doc for doc in store["documents"]}
        args = raw_tail.replace("/", " ").split()

        if args and args[0].startswith("chunk_"):
            chunk_id = args[0]
            chunk = next(
                (chunk for chunk in store["chunks"] if chunk.get("id") == chunk_id),
                None,
            )
            if not chunk:
                yield event.plain_result("指定された chunk が見つかりません。")
                return
            document = documents_by_id.get(chunk.get("doc_id"), {})
            yield event.plain_result(self._format_chunk_detail(document, chunk))
            return

        doc_id = self._normalize_doc_id(args[0])

        document = next(
            (doc for doc in store["documents"] if doc.get("id") == doc_id), None
        )
        if not document:
            yield event.plain_result("指定された資料が見つかりません。")
            return

        chunks = [chunk for chunk in store["chunks"] if chunk.get("doc_id") == doc_id]
        if len(args) >= 2:
            chunk_ref = args[1]
            chunk = None
            if chunk_ref.startswith("chunk_"):
                chunk = next(
                    (item for item in chunks if item.get("id") == chunk_ref),
                    None,
                )
            else:
                try:
                    chunk_index = int(chunk_ref)
                except ValueError:
                    chunk_index = -1
                chunk = next(
                    (item for item in chunks if item.get("index") == chunk_index),
                    None,
                )
            if not chunk:
                yield event.plain_result("指定された chunk が見つかりません。")
                return
            yield event.plain_result(self._format_chunk_detail(document, chunk))
            return

        chunk_lines = []
        for chunk in chunks[:5]:
            preview = str(chunk.get("content", "")).replace("\n", " ")[:120]
            has_embedding = isinstance(chunk.get("embedding"), list)
            chunk_lines.append(
                f"- {chunk.get('id', 'unknown')} (index: {chunk.get('index', 'unknown')}): {preview} "
                f"(embedding: {'あり' if has_embedding else 'なし'})"
            )
        hint = (
            "\n\nchunk 本文を見るには:\n"
            f"/research show {doc_id} <chunk_index>\n"
            f"/research show {doc_id} <chunk_id>\n"
            "/research show <chunk_id>"
        )
        yield event.plain_result(
            f"資料: {document['id']}\n"
            f"title: {document.get('title', '')}\n"
            f"source: {document.get('source_type', 'text')}\n"
            f"source_uri: {document.get('source_uri', '')}\n"
            f"作成日時: {document.get('created_at', 'unknown')}\n"
            f"chunks: {len(chunks)}\n\n"
            f"chunk preview:\n" + "\n".join(chunk_lines) + hint
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

    @research_group.command("agent")
    async def research_agent(self, event: AstrMessageEvent, task: str = ""):
        """Research Note tools を使う agent を実行します。"""
        # agent mode では LLM が必要に応じて Research Note tools を呼ぶ。
        task = self._extract_research_tail(event)
        if not task:
            yield event.plain_result("agent に依頼する内容を入力してください。")
            return

        try:
            provider_id = await self.context.get_current_chat_provider_id(
                umo=event.unified_msg_origin
            )
        except Exception:
            logger.error("Failed to get current chat provider.", exc_info=True)
            yield event.plain_result("利用可能な LLM provider が見つかりません。")
            return

        tools = self._get_research_tool_set()
        if tools.empty():
            yield event.plain_result("Research agent で利用できる tool がありません。")
            return

        try:
            llm_resp = await self.context.tool_loop_agent(
                event=event,
                chat_provider_id=provider_id,
                prompt=task,
                system_prompt=build_research_agent_system_prompt(
                    strict_grounding=self.config.get("strict_grounding", True)
                ),
                tools=tools,
                max_steps=int(self.config.get("agent_max_steps", 8)),
                tool_call_timeout=int(
                    self.config.get("agent_tool_call_timeout", 60)
                ),
            )
        except Exception:
            logger.error("Research agent failed.", exc_info=True)
            yield event.plain_result(
                "Research agent の実行に失敗しました。ログを確認してください。"
            )
            return

        answer = (
            llm_resp.completion_text
            if llm_resp
            else "Research agent は回答を生成できませんでした。"
        )
        yield event.plain_result(answer)

    @research_group.command("agent_web")
    async def research_agent_web(self, event: AstrMessageEvent, task: str = ""):
        """Research Note tools と許可済み Web Search tools を使う agent を実行します。"""
        # Web mode は外部 API を呼ぶため、通常 agent とは明示的に分ける。
        if not self.config.get("enable_web_research", False):
            yield event.plain_result("Web research は設定で無効です。")
            return

        task = self._extract_research_tail(event)
        if not task:
            yield event.plain_result("agent_web に依頼する内容を入力してください。")
            return

        try:
            provider_id = await self.context.get_current_chat_provider_id(
                umo=event.unified_msg_origin
            )
        except Exception:
            logger.error("Failed to get current chat provider.", exc_info=True)
            yield event.plain_result("利用可能な LLM provider が見つかりません。")
            return

        tools = self._get_web_research_tool_set()
        if tools.empty():
            yield event.plain_result("Research Web agent で利用できる tool がありません。")
            return

        try:
            llm_resp = await self.context.tool_loop_agent(
                event=event,
                chat_provider_id=provider_id,
                prompt=task,
                system_prompt=build_web_research_agent_system_prompt(
                    strict_grounding=self.config.get("strict_grounding", True)
                ),
                tools=tools,
                max_steps=int(self.config.get("agent_max_steps", 8)),
                tool_call_timeout=int(
                    self.config.get("agent_tool_call_timeout", 60)
                ),
            )
        except Exception:
            logger.error("Research Web agent failed.", exc_info=True)
            yield event.plain_result(
                "Research Web agent の実行に失敗しました。ログを確認してください。"
            )
            return

        answer = (
            llm_resp.completion_text
            if llm_resp
            else "Research Web agent は回答を生成できませんでした。"
        )
        yield event.plain_result(answer)

    @research_group.command("agent_mcp")
    async def research_agent_mcp(self, event: AstrMessageEvent, task: str = ""):
        """Research Note tools と許可済み MCP / AstrBot tools を使う agent を実行します。"""
        # MCP mode は外部プロセスやファイルに触れる可能性があるため、明示的に分ける。
        if not self.config.get("enable_mcp_research", False):
            yield event.plain_result("MCP research は設定で無効です。")
            return

        task = self._extract_research_tail(event)
        if not task:
            yield event.plain_result("agent_mcp に依頼する内容を入力してください。")
            return

        try:
            provider_id = await self.context.get_current_chat_provider_id(
                umo=event.unified_msg_origin
            )
        except Exception:
            logger.error("Failed to get current chat provider.", exc_info=True)
            yield event.plain_result("利用可能な LLM provider が見つかりません。")
            return

        tools = self._get_mcp_research_tool_set()
        if tools.empty():
            yield event.plain_result("Research MCP agent で利用できる tool がありません。")
            return

        try:
            llm_resp = await self.context.tool_loop_agent(
                event=event,
                chat_provider_id=provider_id,
                prompt=task,
                system_prompt=build_mcp_research_agent_system_prompt(
                    strict_grounding=self.config.get("strict_grounding", True)
                ),
                tools=tools,
                max_steps=int(self.config.get("agent_max_steps", 8)),
                tool_call_timeout=int(
                    self.config.get("agent_tool_call_timeout", 60)
                ),
            )
        except Exception:
            logger.error("Research MCP agent failed.", exc_info=True)
            yield event.plain_result(
                "Research MCP agent の実行に失敗しました。ログを確認してください。"
            )
            return

        answer = (
            llm_resp.completion_text
            if llm_resp
            else "Research MCP agent は回答を生成できませんでした。"
        )
        yield event.plain_result(answer)

    @research_group.command("import")
    async def research_import_command(self, event: AstrMessageEvent, args: str = ""):
        """text または URL を preview 付きで取り込みます。"""
        # import は preview を作るだけで、confirm まで保存しない。
        tail = self._extract_research_tail(event)
        command, _, value = tail.partition(" ")
        command = command.strip().lower()
        value = value.strip()

        if command == "text":
            yield event.plain_result(await self._build_import_text_preview(value))
            return
        if command == "url":
            yield event.plain_result(await self._build_import_url_preview(value))
            return
        if command == "confirm":
            yield event.plain_result(await self._confirm_import(value))
            return

        yield event.plain_result(
            "使い方: /research import text <text>\n"
            "       /research import url <url>\n"
            "       /research import confirm <id>"
        )

    @research_group.command("import_text")
    async def research_import_text(self, event: AstrMessageEvent, content: str = ""):
        """text import の短縮コマンドです。"""
        yield event.plain_result(
            await self._build_import_text_preview(self._extract_research_tail(event))
        )

    @research_group.command("import_url")
    async def research_import_url(self, event: AstrMessageEvent, url: str = ""):
        """URL import の短縮コマンドです。"""
        yield event.plain_result(
            await self._build_import_url_preview(self._extract_research_tail(event))
        )

    @research_group.command("import_confirm")
    async def research_import_confirm(
        self,
        event: AstrMessageEvent,
        pending_id: str = "",
    ):
        """import preview を保存する短縮コマンドです。"""
        yield event.plain_result(
            await self._confirm_import(self._extract_research_tail(event))
        )

    async def _build_import_text_preview(
        self,
        content: str,
    ) -> str:
        content = content.strip()
        if not content:
            return "import する text を入力してください。"

        try:
            payload = {
                "title": content.replace("\n", " ")[:60],
                "content": content,
                "source_type": "text_import",
                "source_uri": "",
            }
            pending_id, payload = self._add_pending_import(payload)
        except ResearchToolError as exc:
            return self._tool_error_message(exc)

        return self._build_import_preview(payload, pending_id)

    async def _build_import_url_preview(
        self,
        url: str,
    ) -> str:
        url = url.strip()
        if not url:
            return "URL を入力してください。"

        try:
            payload = await fetch_url_text(
                url,
                timeout=int(self.config.get("import_url_timeout", 20)),
            )
            pending_id, payload = self._add_pending_import(payload)
        except ResearchToolError as exc:
            return self._tool_error_message(exc)
        except Exception:
            logger.error("URL import failed.", exc_info=True)
            return "URL の取得に失敗しました。http/https の HTML URL を指定してください。"

        return self._build_import_preview(payload, pending_id)

    async def _confirm_import(
        self,
        pending_id: str,
    ) -> str:
        pending_id = (
            pending_id.strip().split(maxsplit=1)[0] if pending_id.strip() else ""
        )
        if not pending_id:
            return "pending import id を入力してください。"

        pending = self.pending_imports.load_all()
        payload = pending.get(pending_id)
        if not payload:
            return self._tool_error_message(ResearchToolError("import_not_found"))

        try:
            saved = await self._add_document_from_text(
                str(payload.get("content", "")),
                title=str(payload.get("title", "")),
                source_type=str(payload.get("source_type", "text_import")),
                source_uri=str(payload.get("source_uri", "")),
                max_chars=int(self.config.get("max_import_chars", 50000)),
            )
        except ResearchToolError as exc:
            if exc.code == "embedding_failed":
                logger.error("Failed to generate embeddings for import.", exc_info=True)
            return self._tool_error_message(exc)

        pending.pop(pending_id, None)
        self.pending_imports.save_all(pending)

        document = saved["document"]
        return (
            f"import を保存しました: {document['id']}\n"
            f"title: {document.get('title', '')}\n"
            f"source_type: {document.get('source_type', '')}\n"
            f"source_uri: {document.get('source_uri', '')}\n"
            f"chunks: {len(saved['chunks'])}\n"
            "embedding: 全 chunk 作成済み"
        )

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
