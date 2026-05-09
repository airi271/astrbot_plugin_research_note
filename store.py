import json
from pathlib import Path

from astrbot.api import logger


EMPTY_STORE = {
    "schema_version": 2,
    "documents": [],
    "chunks": [],
}


class NoteStore:
    def __init__(self, notes_file: Path):
        self.notes_file = notes_file
        self.notes_file.parent.mkdir(parents=True, exist_ok=True)

    # 始终返回 schema_version 2 的保存结构。
    def load_store(self) -> dict:
        if not self.notes_file.exists():
            return self._empty_store()
        try:
            with self.notes_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            logger.error("research_notes.json is broken.", exc_info=True)
            return self._empty_store()

        if not isinstance(data, dict) or data.get("schema_version") != 2:
            return self._empty_store()
        return {
            "schema_version": 2,
            "documents": data.get("documents", [])
            if isinstance(data.get("documents"), list)
            else [],
            "chunks": data.get("chunks", [])
            if isinstance(data.get("chunks"), list)
            else [],
        }

    # 原子写入，避免保存中断时破坏主文件。
    def save_store(self, data: dict) -> None:
        normalized = {
            "schema_version": 2,
            "documents": data.get("documents", [])
            if isinstance(data.get("documents"), list)
            else [],
            "chunks": data.get("chunks", [])
            if isinstance(data.get("chunks"), list)
            else [],
        }
        tmp_file = self.notes_file.with_suffix(".json.tmp")
        with tmp_file.open("w", encoding="utf-8") as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2)
        tmp_file.replace(self.notes_file)

    def _empty_store(self) -> dict:
        return {
            "schema_version": EMPTY_STORE["schema_version"],
            "documents": [],
            "chunks": [],
        }
