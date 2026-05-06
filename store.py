import json
from pathlib import Path

class NoteStore:
    def __init__(self, notes_file: Path):
        self.notes_file = notes_file
        self.notes_file.parent.mkdir(parents=True, exist_ok=True)
        # 从文件中加载 notes 列表，如果文件不存在或格式错误则返回空列表
    def load_notes(self,logger) -> list[dict]:
        if not self.notes_file.exists():
            return []
        try:
            with self.notes_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            logger.error("research_notes.json is broken.", exc_info=True)
            return []

        if not isinstance(data, list):
            return []
        return data
    # 将 notes 列表保存到文件中    
    def save_notes(self, notes: list[dict]) -> None:
        with self.notes_file.open("w", encoding="utf-8") as f:
            json.dump(notes, f, ensure_ascii=False, indent=2)