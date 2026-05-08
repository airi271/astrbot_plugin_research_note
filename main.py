from datetime import datetime
from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .prompts import build_answer_prompt
from .search import search_notes, search_notes_by_embedding
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

    # 生成新的 note id，避免删除资料后重复使用旧 id。
    def _next_note_id(self, notes: list[dict]) -> str:
        max_num = 0
        for note in notes:
            note_id = str(note.get("id", ""))
            if not note_id.startswith("note_"):
                continue
            try:
                max_num = max(max_num, int(note_id.removeprefix("note_")))
            except ValueError:
                continue
        return f"note_{max_num + 1:03d}"

    # 统一用户输入的资料 id，支持 "001" 和 "note_001" 两种写法。
    def _normalize_note_id(self, note_id: str) -> str:
        note_id = note_id.strip()
        if not note_id:
            return ""
        if note_id.startswith("note_"):
            return note_id
        return f"note_{note_id}"

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

    # 获取第一个可用的 embedding provider；没有时仍然可以使用关键词搜索。
    def _get_embedding_provider(self):
        providers = self.context.get_all_embedding_providers()
        if not providers:
            return None
        return providers[0]

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
    /research show <note_id> - 指定した資料を表示
    /research ask <question> - 資料に基づいて質問
    /research delete <note_id> --confirm - 指定した資料を削除
    /research reindex - 既存資料の embedding を再作成
    /research clear --confirm - 全資料を削除
    /research help - このヘルプを表示
    """
        yield event.plain_result(text)

    @research_group.command("add")
    async def research_add(self, event: AstrMessageEvent, content: str = ""):
        """資料を追加します。"""
        # 先读取并检查文本，再生成 embedding。
        content = self._extract_research_tail(event)
        if not content:
            yield event.plain_result("追加する資料テキストを入力してください。")
            return

        max_add_chars = int(self.config.get("max_add_chars", 8000))
        if len(content) > max_add_chars:
            yield event.plain_result(f"資料が長すぎます。最大 {max_add_chars} 文字までです。")
            return

        # embedding 是可选的；没有 embedding 时仍然可以用关键词搜索。
        embedding = None
        embedding_provider = self._get_embedding_provider()
        if embedding_provider:
            embedding = await embedding_provider.get_embedding(content)

        # Phase 2 之前先保持 note 级别的保存格式。
        notes = self.store.load_notes()
        note = {
            "id": self._next_note_id(notes),
            "content": content,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "embedding": embedding,
        }
        notes.append(note)
        self.store.save_notes(notes)

        yield event.plain_result(f"資料を保存しました: {note['id']}")

    @research_group.command("list")
    async def research_list(self, event: AstrMessageEvent):
        """保存済み資料を表示します。"""
        # 列表中只显示短预览，避免长资料刷屏。
        notes = self.store.load_notes()
        if not notes:
            yield event.plain_result("保存済み資料はありません。")
            return

        lines = ["保存済み資料:"]
        for note in notes[:10]:
            preview = str(note.get("content", "")).replace("\n", " ")[:60]
            lines.append(f"- {note.get('id', 'unknown')}: {preview}")
        yield event.plain_result("\n".join(lines))

    @research_group.command("show")
    async def research_show(self, event: AstrMessageEvent, note_id: str = ""):
        """保存済み資料を表示します。"""
        # 显示单条资料及其 metadata，方便检查资料和引用。
        note_id = self._normalize_note_id(self._extract_research_tail(event))
        if not note_id:
            yield event.plain_result("資料IDを指定してください。")
            return

        notes = self.store.load_notes()
        if not notes:
            yield event.plain_result("保存済み資料はありません。")
            return

        note = next((n for n in notes if n.get("id") == note_id), None)
        if not note:
            yield event.plain_result("指定された資料が見つかりません。")
            return

        has_embedding = isinstance(note.get("embedding"), list)
        yield event.plain_result(
            f"資料: {note['id']}\n"
            f"作成日時: {note.get('created_at', 'unknown')}\n"
            f"embedding: {'あり' if has_embedding else 'なし'}\n\n"
            f"内容:\n{note.get('content', '')}"
        )

    @research_group.command("ask")
    async def research_ask(self, event: AstrMessageEvent, question: str = ""):
        """資料に基づいて質問します。"""
        # ask 是固定 RAG 流程：先检索资料，再构造 prompt，最后调用 LLM。
        question = self._extract_research_tail(event)
        if not question:
            yield event.plain_result("質問を入力してください。")
            return

        notes = self.store.load_notes()
        if not notes:
            yield event.plain_result("保存済み資料がありません。先に /research add で資料を追加してください。")
            return

        top_k = int(self.config.get("top_k", 3))
        embedding_provider = self._get_embedding_provider()
        if not embedding_provider:
            matched_notes = search_notes(question, notes, top_k=top_k)
        else:
            # 如果 embedding 搜索没有结果，则回退到关键词搜索。
            query_embedding = await embedding_provider.get_embedding(question)
            matched_notes = search_notes_by_embedding(query_embedding, notes, top_k=top_k)
            logger.info(f"Found {len(matched_notes)} matched notes using embedding search.")
            if not matched_notes:
                matched_notes = search_notes(question, notes, top_k=top_k)

        if not matched_notes:
            yield event.plain_result("関連する資料が見つかりませんでした。")
            return

        # prompt 构造放在 prompts.py 中，保持命令逻辑简洁。
        prompt = build_answer_prompt(
            question,
            matched_notes,
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
        source_ids = ", ".join(note["id"] for note in matched_notes)
        result = f"{answer}\n\n使用資料: {source_ids}"
        # debug prompt 只在开发时显示，默认不输出给用户。
        if self.config.get("show_debug_prompt", False):
            result += f"\n\nprompt:\n{prompt}"
        yield event.plain_result(result)

    @research_group.command("delete")
    async def research_delete(
        self,
        event: AstrMessageEvent,
        note_id: str = "",
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
                    "削除するには /research delete <note_id> --confirm を実行してください。"
                )
                return

        note_id = self._normalize_note_id(
            raw_tail.replace("--confirm", "").strip()
        )
        if not note_id:
            yield event.plain_result("資料IDを指定してください。")
            return

        # 通过创建新列表来删除资料，再交给 store 做原子保存。
        notes = self.store.load_notes()
        if not notes:
            yield event.plain_result("保存済み資料はありません。")
            return

        new_notes = [note for note in notes if note.get("id") != note_id]
        if len(new_notes) == len(notes):
            yield event.plain_result("指定された資料が見つかりません。")
            return

        self.store.save_notes(new_notes)
        yield event.plain_result(f"資料を削除しました: {note_id}")

    @research_group.command("reindex")
    async def research_reindex(self, event: AstrMessageEvent):
        """既存資料の embedding を再作成します。"""
        # reindex 用于给旧资料重新生成 embedding。
        embedding_provider = self._get_embedding_provider()
        if not embedding_provider:
            yield event.plain_result("embedding provider が設定されていません。")
            return

        notes = self.store.load_notes()
        if not notes:
            yield event.plain_result("保存済み資料はありません。")
            return

        updated = 0
        for note in notes:
            content = str(note.get("content", ""))
            if not content:
                continue
            note["embedding"] = await embedding_provider.get_embedding(content)
            updated += 1

        self.store.save_notes(notes)
        yield event.plain_result(f"embedding を再作成しました: {updated} 件")

    @research_group.command("clear")
    async def research_clear(self, event: AstrMessageEvent, confirm: str | None = None):
        """保存済み資料をすべて削除します。"""
        # clear 会删除全部资料，因此必须要求 --confirm。
        if confirm != "--confirm":
            yield event.plain_result("削除するには /research clear --confirm を実行してください。")
            return
        self.store.save_notes([])
        yield event.plain_result("保存済み資料をすべて削除しました。")

    async def terminate(self):
        """Optional async cleanup hook."""
