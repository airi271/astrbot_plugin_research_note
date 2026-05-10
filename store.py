import json
import sqlite3
from pathlib import Path
from shutil import copy2

from astrbot.api import logger


EMPTY_STORE = {
    "schema_version": 2,
    "documents": [],
    "chunks": [],
}


class NoteStore:
    def __init__(self, notes_file: Path):
        self.notes_file = notes_file
        self.store_file = notes_file
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

    def create_backup(self, backup_dir: Path) -> Path | None:
        if not self.store_file.exists():
            return None
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = backup_dir / (
            f"{self.store_file.stem}.{_timestamp()}.bak{self.store_file.suffix}"
        )
        copy2(self.store_file, backup_file)
        return backup_file


class SQLiteNoteStore:
    def __init__(self, db_file: Path):
        self.db_file = db_file
        self.store_file = db_file
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    FOREIGN KEY(doc_id) REFERENCES documents(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id)"
            )

    def load_store(self) -> dict:
        with self._connect() as conn:
            documents = [
                json.loads(row["data"])
                for row in conn.execute("SELECT data FROM documents ORDER BY id")
            ]
            chunks = [
                json.loads(row["data"])
                for row in conn.execute("SELECT data FROM chunks ORDER BY doc_id, id")
            ]
        return {"schema_version": 2, "documents": documents, "chunks": chunks}

    def save_store(self, data: dict) -> None:
        documents = (
            data.get("documents", []) if isinstance(data.get("documents"), list) else []
        )
        chunks = data.get("chunks", []) if isinstance(data.get("chunks"), list) else []
        with self._connect() as conn:
            conn.execute("BEGIN")
            conn.execute("DELETE FROM chunks")
            conn.execute("DELETE FROM documents")
            conn.executemany(
                "INSERT OR REPLACE INTO documents (id, data) VALUES (?, ?)",
                [
                    (
                        str(document.get("id", "")),
                        json.dumps(document, ensure_ascii=False),
                    )
                    for document in documents
                    if document.get("id")
                ],
            )
            conn.executemany(
                "INSERT OR REPLACE INTO chunks (id, doc_id, data) VALUES (?, ?, ?)",
                [
                    (
                        str(chunk.get("id", "")),
                        str(chunk.get("doc_id", "")),
                        json.dumps(chunk, ensure_ascii=False),
                    )
                    for chunk in chunks
                    if chunk.get("id") and chunk.get("doc_id")
                ],
            )
            conn.commit()

    def create_backup(self, backup_dir: Path) -> Path | None:
        if not self.store_file.exists():
            return None
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = backup_dir / (
            f"{self.store_file.stem}.{_timestamp()}.bak{self.store_file.suffix}"
        )
        with self._connect() as source_conn:
            with sqlite3.connect(backup_file) as backup_conn:
                source_conn.backup(backup_conn)
        return backup_file


def create_note_store(data_dir: Path, backend: str = "json"):
    if backend.strip().lower() == "sqlite":
        return SQLiteNoteStore(data_dir / "research_notes.sqlite3")
    return NoteStore(data_dir / "research_notes.json")


def _timestamp() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y%m%d_%H%M%S")
