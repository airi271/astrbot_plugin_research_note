from click import prompt

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import AstrBotConfig, logger
import json
from datetime import datetime
from pathlib import Path
from .store import NoteStore
from .search import search_notes
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

    # 生成下一个 note 的 ID，格式为 note_001, note_002, ...        
    def _next_note_id(self, notes: list[dict]) -> str:
        return f"note_{len(notes) + 1:03d}"
    # 从消息中提取 research add 或 research ask 指令的内容
    def _extract_research_tail(self, event: AstrMessageEvent) -> str:
        raw_text = event.message_str.strip()
        prefix1 = "research add"
        prefix2 = "research ask"
        if raw_text.startswith(prefix1):
            return raw_text[len(prefix1):].strip()
        if raw_text.startswith(prefix2):
            return raw_text[len(prefix2):].strip()
        return ""
        
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

    # 注册指令的装饰器。指令名为 research_hellow。注册成功后，发送 `/research_hellow` 就会触发这个指令，并回复 `Research Note is ready, {user_name}!`
    @filter.command("research_hellow")
    async def research_hellow(self, event: AstrMessageEvent):
        """Research Note の動作確認コマンド。""" # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        user_name = event.get_sender_name()
        yield event.plain_result(f"Research Note is ready, {user_name}!") # 发送一条纯文本消息

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
    """
        yield event.plain_result(text)

    @research_group.command("add")
    async def research_add(self, event: AstrMessageEvent, content: str=""):
        """資料を追加します。"""
        content = self._extract_research_tail(event)
        if not content:
            yield event.plain_result("追加する資料テキストを入力してください。")
            return
        max_add_chars = int(self.config.get("max_add_chars", 8000))
        if len(content) > max_add_chars:
            yield event.plain_result(f"資料が長すぎます。最大 {max_add_chars} 文字までです。")
            return
        notes = self.store.load_notes(logger)
        note = {
            "id": self._next_note_id(notes),
            "content": content,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        notes.append(note)
        self.store.save_notes(notes)

        yield event.plain_result(f"資料を保存しました: {note['id']}")

    @research_group.command("list")
    async def research_list(self, event: AstrMessageEvent):
        """保存済み資料を表示します。"""
        notes = self.store.load_notes(logger)
        if not notes:
            yield event.plain_result("保存済み資料はありません。")
            return

        lines = ["保存済み資料:"]
        for note in notes[:10]:
            preview = note["content"].replace("\n", " ")[:60]
            lines.append(f"- {note['id']}: {preview}")

        yield event.plain_result("\n".join(lines))

    @research_group.command("ask")
    async def research_ask(self, event: AstrMessageEvent, question: str=""):
        """資料に基づいて質問します。"""
        question = self._extract_research_tail(event)
        if not question:
            yield event.plain_result("質問を入力してください。")
            return

        notes = self.store.load_notes(logger)
        if not notes:
            yield event.plain_result("保存済み資料がありません。先に /research add で資料を追加してください。")
            return
        
        top_k = int(self.config.get("top_k", 3))
        matched_notes = search_notes(question, notes, top_k=top_k)
        if not matched_notes:
            yield event.plain_result("関連する資料が見つかりませんでした。")
            return
        
        prompt = build_answer_prompt(question, matched_notes, max_note_chars=int(self.config.get("max_note_chars", 1200)), strict_grounding=self.config.get("strict_grounding", True))
        provider_id = await self.context.get_current_chat_provider_id(
            umo=event.unified_msg_origin
        )
        if not provider_id:
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

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
