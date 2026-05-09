import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4


class PendingImportStore:
    def __init__(self, pending_file: Path):
        self.pending_file = pending_file
        self.pending_file.parent.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> dict:
        if not self.pending_file.exists():
            return {}
        with self.pending_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}

    def save_all(self, data: dict) -> None:
        tmp_file = self.pending_file.with_suffix(".json.tmp")
        with tmp_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_file.replace(self.pending_file)

    def add(self, payload: dict) -> str:
        pending = self.load_all()
        pending_id = f"import_{uuid4().hex[:8]}"
        pending[pending_id] = {
            **payload,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.save_all(pending)
        return pending_id

    def pop(self, pending_id: str) -> dict | None:
        pending = self.load_all()
        payload = pending.pop(pending_id, None)
        self.save_all(pending)
        return payload
