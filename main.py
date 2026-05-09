from datetime import datetime
from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .chunking import split_text_into_chunks
from .prompts import build_answer_prompt
from .search import search_chunks_by_embedding
from .store import NoteStore


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

        store = self.store.load_store()
        now = datetime.now().isoformat(timespec="seconds")
        doc_id = self._next_doc_id(store["documents"])
        document = {
            "id": doc_id,
            "project_id": "default",
            "title": content.replace("\n", " ")[:60] or doc_id,
            "source_type": "text",
            "source_uri": "",
            "tags": [],
            "created_at": now,
            "updated_at": now,
        }

        chunk_texts = split_text_into_chunks(
            content,
            chunk_size=int(self.config.get("chunk_size", 800)),
            chunk_overlap=int(self.config.get("chunk_overlap", 120)),
        )
        embedding_provider = self._get_embedding_provider()
        if not embedding_provider:
            yield event.plain_result("embedding provider が設定されていません。")
            return

        try:
            embedded_chunks = []
            for chunk_text in chunk_texts:
                embedded_chunks.extend(
                    await self._split_text_for_embedding(embedding_provider, chunk_text)
                )
        except Exception:
            logger.error(
                "Failed to generate embeddings for added document.", exc_info=True
            )
            yield event.plain_result(
                "embedding の作成に失敗したため、資料は保存しませんでした。"
                "chunk_size を小さくして再試行してください。"
            )
            return

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

        yield event.plain_result(
            f"資料を保存しました: {doc_id}\n"
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
            query_embedding = await embedding_provider.get_embedding(question)
        except Exception:
            logger.error("Failed to generate embedding for question.", exc_info=True)
            yield event.plain_result("質問の embedding 作成に失敗しました。")
            return

        matched_chunks = search_chunks_by_embedding(
            query_embedding, chunks, top_k=top_k
        )
        logger.info(
            f"Found {len(matched_chunks)} matched chunks using embedding search."
        )

        if not matched_chunks:
            yield event.plain_result("関連する資料が見つかりませんでした。")
            return

        # prompt 构造放在 prompts.py 中，保持命令逻辑简洁。
        prompt = build_answer_prompt(
            question,
            matched_chunks,
            max_note_chars=int(self.config.get("max_note_chars", 1200)),
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
