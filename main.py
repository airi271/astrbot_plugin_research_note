from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import AstrBotConfig, logger
from datetime import datetime
from pathlib import Path
from .store import NoteStore
from .search import search_notes, search_notes_by_embedding
from .prompts import build_answer_prompt
@register("ResearchNote", "airi271", "Research note assistant for source-grounded question answering.", "0.1.0")
class ResearchNotePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.data_dir = Path(__file__).parent / "data"
        #self.data_dir.mkdir(parents=True, exist_ok=True)
        self.notes_file = self.data_dir / "research_notes.json"
        self.store = NoteStore(self.notes_file)

    # 生成新的 note id，格式为 note_001, note_002 等        
    def _next_note_id(self, notes: list[dict]) -> str:
        max_num = 0
        for note in notes:
            note_id = str(note.get("id", ""))
            if note_id.startswith("note_"):
                try:
                    max_num = max(max_num, int(note_id.removeprefix("note_")))
                except ValueError:
                    continue
        return f"note_{max_num + 1:03d}"
    
    # 从消息中提取 research add 或 research ask 指令的内容
    def _extract_research_tail(self, event: AstrMessageEvent) -> str:
        raw_text = event.message_str.strip()
        prefix1 = "research add"
        prefix2 = "research ask"
        prefix3 = "research show"
        prefix4 = "research delete --confirm"
        if raw_text.startswith(prefix1):
            return raw_text[len(prefix1):].strip()
        if raw_text.startswith(prefix2):
            return raw_text[len(prefix2):].strip()
        if raw_text.startswith(prefix3):
            return raw_text[len(prefix3):].strip()
        if raw_text.startswith(prefix4):
            return raw_text[len(prefix4):].strip()
        return ""
    def _get_embedding_provider(self):
        providers = self.context.get_all_embedding_providers()
        if not providers:
            logger.error("No embedding provider found.", exc_info=True)
            return None
        return providers[0]

        
    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    @filter.command("helloworld")
    async def helloworld(self, event: AstrMessageEvent):
        """这是一个 hello world 指令""" # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        user_name = event.get_sender_name()
        message_str = event.message_str # 用户发的纯文本消息字符串
        message_chain = event.get_messages() # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)
        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!") # 发送一条纯文本消息

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
    /research ask <question> - 資料に基づいて質問
    /research clear --confirm - 全資料を削除
    /research delete --confirm <id> - 指定した資料を削除
    /research show <id> - 指定した資料を表示
    /research help - このヘルプを表示
    """
        yield event.plain_result(text)

    @research_group.command("add")
    async def research_add(self, event: AstrMessageEvent, content: str=""):
        """資料を追加します。"""
        content = self._extract_research_tail(event)
        if not content:
            yield event.plain_result("追加する資料テキストを入力してください。")
            return
        embedding = None
        embedding_provider = self._get_embedding_provider()
        if embedding_provider:
            embedding = await embedding_provider.get_embedding(content)
        max_add_chars = int(self.config.get("max_add_chars", 8000))
        if len(content) > max_add_chars:
            yield event.plain_result(f"資料が長すぎます。最大 {max_add_chars} 文字までです。")
            return
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
        notes = self.store.load_notes()
        if not notes:
            yield event.plain_result("保存済み資料はありません。")
            return

        lines = ["保存済み資料:"]
        for note in notes[:10]:
            preview = note["content"].replace("\n", " ")[:60]
            lines.append(f"- {note['id']}: {preview}")
        yield event.plain_result("\n".join(lines))

    @research_group.command("show")
    async def research_show(self, event: AstrMessageEvent, note_id: str=""):
        """保存済み資料を表示します。"""
        note_id = self._extract_research_tail(event)
        note_id = f"note_{note_id}"
        notes = self.store.load_notes()
        if not notes:
            yield event.plain_result("保存済み資料はありません。")
            return
        if note_id:
            note = next((n for n in notes if n["id"] == note_id), None)
            if not note:
                yield event.plain_result("指定された資料が見つかりません。")
                return
            yield event.plain_result(f"資料: {note['id']}\n内容: {note['content']}")
        else:
            yield event.plain_result("資料IDを指定してください。")
            return
        
    @research_group.command("ask")
    async def research_ask(self, event: AstrMessageEvent, question: str=""):
        """資料に基づいて質問します。"""
        embedding_provider = self._get_embedding_provider()
        question = self._extract_research_tail(event)
        if not question:
            yield event.plain_result("質問を入力してください。")
            return

        notes = self.store.load_notes()
        if not notes:
            yield event.plain_result("保存済み資料がありません。先に /research add で資料を追加してください。")
            return
        
        top_k = int(self.config.get("top_k", 3))
        if not embedding_provider:
            matched_notes = search_notes(question, notes, top_k=top_k)
        else:
            query_embedding = await embedding_provider.get_embedding(question)
            matched_notes = search_notes_by_embedding(query_embedding, notes, top_k=top_k)
            logger.info(f"Found {len(matched_notes)} matched notes for the question using embedding search.")
        if not matched_notes:
            yield event.plain_result("関連する資料が見つかりませんでした。")
            return
        
        prompt = build_answer_prompt(question, matched_notes, max_note_chars=int(self.config.get("max_note_chars", 1200)), strict_grounding=self.config.get("strict_grounding", True))
        try:
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
        yield event.plain_result(f"{answer}\n\n使用資料: {source_ids}\n\nprompt:\n{prompt}")

    @research_group.command("clear")
    async def research_clear(self, event: AstrMessageEvent, confirm: str | None = None):
        """保存済み資料を削除します。"""
        if confirm != "--confirm":
            yield event.plain_result("削除するには /research clear --confirm を実行してください。")
            return
        self.store.save_notes([])
        yield event.plain_result("保存済み資料をすべて削除しました。")

    @research_group.command("delete")
    async def research_delete(self, event: AstrMessageEvent, confirm: str | None = None):
        """保存済み資料を削除します。"""
        if confirm != "--confirm":
            yield event.plain_result("削除するには /research delete --confirm を実行してください。")
            return
        note_id = self._extract_research_tail(event)
        note_id = f"note_{note_id}"
        notes = self.store.load_notes()
        if not notes:
            yield event.plain_result("保存済み資料はありません。")
            return
        new_notes = [note for note in notes if note["id"] != note_id]
        if len(new_notes) == len(notes):
            yield event.plain_result("指定された資料が見つかりません。")
            return
        self.store.save_notes(new_notes)
        yield event.plain_result("保存済み資料を削除しました。")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
