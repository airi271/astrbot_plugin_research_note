from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import json
from datetime import datetime
from pathlib import Path

@register("ResearchNote", "airi271", "Research note assistant for source-grounded question answering.", "0.1.0")
class ResearchNotePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_dir = Path(__file__).parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.notes_file = self.data_dir / "research_notes.json"
    # 从文件中加载 notes 列表，如果文件不存在则返回空列表
    def _load_notes(self) -> list[dict]:
        if not self.notes_file.exists():
            return []
        with self.notes_file.open("r", encoding="utf-8") as f:
            return json.load(f)
    # 将 notes 列表保存到文件中    
    def _save_notes(self, notes: list[dict]) -> None:
        with self.notes_file.open("w", encoding="utf-8") as f:
            json.dump(notes, f, ensure_ascii=False, indent=2)
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
    
    def _tokenize(self, text: str) -> list[str]:
        normalized = text.lower().replace("\n", " ")
        tokens = []
        for token in normalized.split():
            token = token.strip(".,!?;:()[]{}<>。、！？「」『』（）")
            if token:
                tokens.append(token)
        return tokens

    def _score_note(self, question: str, note: dict) -> int:
        tokens = self._tokenize(question)
        content = str(note.get("content", "")).lower()
        score = 0
        for token in tokens:
            if token in content:
                score += 1
        return score
    
    def _search_notes(self, question: str, notes: list[dict], top_k: int = 3) -> list[dict]:
        scored = []
        for note in notes:
            score = self._score_note(question, note)
            if score > 0:
                scored.append((score, note))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [note for score, note in scored[:top_k]]
        
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

        notes = self._load_notes()
        note = {
            "id": self._next_note_id(notes),
            "content": content,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        notes.append(note)
        self._save_notes(notes)

        yield event.plain_result(f"資料を保存しました: {note['id']}")

    @research_group.command("list")
    async def research_list(self, event: AstrMessageEvent):
        """保存済み資料を表示します。"""
        notes = self._load_notes()
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

        notes = self._load_notes()
        if not notes:
            yield event.plain_result("保存済み資料がありません。先に /research add で資料を追加してください。")
            return

        matched_notes = self._search_notes(question, notes, top_k=3)
        if not matched_notes:
            yield event.plain_result("関連する資料が見つかりませんでした。")
            return

        lines = ["関連資料:"]
        for note in matched_notes:
            preview = note["content"].replace("\n", " ")[:120]
            lines.append(f"- {note['id']}: {preview}")

        yield event.plain_result("\n".join(lines))

    @research_group.command("clear")
    async def research_clear(self, event: AstrMessageEvent, confirm: str | None = None):
        """保存済み資料を削除します。"""
        if confirm != "--confirm":
            yield event.plain_result("削除するには /research clear --confirm を実行してください。")
            return
        self._save_notes([])
        yield event.plain_result("保存済み資料をすべて削除しました。")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
