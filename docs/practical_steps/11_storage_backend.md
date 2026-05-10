# 11 Storage Backend: 保存 backend を強くする

この Phase では、JSON 保存からより強い保存 backend へ進む準備をします。現在の実装では、既存 command を変えずに `json` と `sqlite` を切り替えられる最小 backend を追加します。

最初は JSON で十分です。しかし、資料と chunk が増えると、読み書きが遅くなったり、検索や migration が大変になったりします。

## 目的

この Phase の目的は以下です。

- JSON の限界を理解する。
- schema_version と migration を管理する。
- backup と export/import を作る。
- `storage_backend` で JSON と SQLite を切り替えられるようにする。
- embedding の保存場所を整理する。
- Milvus / Milvus Lite は必要になってから検討する。

## まだ早い場合

以下なら、まだ JSON のままでよいです。

- chunk 数が数百以下。
- 保存と検索が十分速い。
- データ破損が起きていない。
- migration が少ない。

保存 backend 強化は大きい変更です。必要になるまで急がなくてよいです。

## 変更するファイル

```text
store.py
_conf_schema.json
main.py
```

将来、保存処理がさらに大きくなった場合の分割候補です。

```text
storage/base.py
storage/json_store.py
storage/sqlite_store.py
```

## Step 1: まず backup を作る

SQLite に進む前に、現在の保存 backend の backup を作ります。

コマンド候補です。

```text
/research backup
```

最初は `/research backup` だけでよいです。export/import は必要になってから追加します。

例です。

```text
research_store.json
research_store.20260507_120000.bak.json
research_notes.sqlite3
research_notes.20260507_120000.bak.sqlite3
```

## Step 2: schema_version を必ず見る

保存ファイルには `schema_version` を置きます。

```json
{
  "schema_version": 2,
  "documents": [],
  "chunks": []
}
```

読み込み時に version を見ます。

```text
version なし: 読み込まず空 store にする、または必要なら migration を作る
version 2: 現行形式
version が未来: 読み込まず警告
```

## Step 3: migration は必要になってから関数に分ける

今回は既存データが空だったため、migration は実装しません。将来必要になったら、store.py に直接書きすぎず、migration 用関数に分けます。

```text
migrations.py
- migrate_v1_notes_to_v2_store
- migrate_v2_to_v3
```

大事なルールです。

- migration 前に backup を作る。
- migration 後に件数を表示する。
- 失敗したら元ファイルを残す。

## Step 4: SQLite に進む判断

SQLite に進む目安です。

- chunk が1000件を超えた。
- JSON load が体感で遅い。
- delete や update が増えた。
- project や tag で絞り込みたい。
- backup と migration を安定させたい。

SQLite にすると、document と chunk を table にできます。現在の最小実装では `documents` と `chunks` の `data` 列に JSON を保存し、command 側の `load_store()` / `save_store()` API は変えません。

```text
documents table
chunks table
```

## Step 5: Store interface を作る

JSON と SQLite を切り替えるには、共通 interface を決めます。

例です。

```python
class ResearchStoreBase:
    def list_documents(self) -> list[dict]: ...
    def get_document(self, doc_id: str) -> dict | None: ...
    def add_document(self, document: dict, chunks: list[dict]) -> None: ...
    def delete_document(self, doc_id: str) -> bool: ...
    def search_chunks_data(self) -> list[dict]: ...
```

現在の実装では、既存 command を壊さないために `load_store()`、`save_store()`、`create_backup()` を共通 interface として使います。細かい差分更新 API は必要になってから追加します。

## Step 6: embedding の保存を考える

embedding は list[float] なので JSON だとファイルが大きくなります。

選択肢です。

- JSON backend では JSON にそのまま保存する。
- SQLite backend では当面 chunk JSON 内に保存する。
- SQLite の embeddings table に保存する。
- embedding だけ別ファイルにする。
- Milvus / Milvus Lite に保存する。

最初は JSON または chunk JSON 内保存でよいです。重くなってから分けます。

## Step 7: Milvus は最後でよい

Milvus は本格的な vector database です。

使う判断基準です。

- chunk 数がかなり多い。
- embedding search が遅い。
- 複数 project を大量に扱う。
- 運用コストを受け入れられる。

Research Note の初期実用版では SQLite までで十分な可能性が高いです。

## 設定例

JSON backend のまま使う場合です。

```json
{
  "storage_backend": "json"
}
```

SQLite backend を使う場合です。

```json
{
  "storage_backend": "sqlite"
}
```

## 動作確認

backup を試します。

```text
/research backup
```

SQLite backend に切り替えた状態で、既存 command が同じように使えることを確認します。

```text
/research add SQLite backend test
/research list
/research show doc_001
/research search backend test
/research backup
```

期待することです。

- backup ファイルができる。
- JSON / SQLite のどちらでも command の使い方が変わらない。
- SQLite backup は `.sqlite3` として作られる。

## よくある失敗

### migration でデータが消える

必ず backup を先に作ります。migration は元ファイルを直接破壊しない形にします。

### SQLite にしたら既存コマンドが壊れる

store interface を揃えます。command 側が JSON の内部構造に直接触らないようにします。

### embedding で DB が大きくなる

embedding を別 table または別ファイルに分けることを検討します。

## この Phase の完了条件

- `schema_version` を見て読み込む。
- `storage_backend` で `json` / `sqlite` を選べる。
- backup command がある。
- SQLite へ進む判断基準が明確。
- store の責任が command から分離されている。

## 実装例

### backup.py

まずは JSON backup を安全に作ります。

```python
from datetime import datetime
from pathlib import Path
from shutil import copy2


def create_backup(store_file: Path, backup_dir: Path) -> Path | None:
    # No backup is needed if the store file does not exist yet.
    if not store_file.exists():
        return None

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"{store_file.stem}.{timestamp}.bak{store_file.suffix}"
    copy2(store_file, backup_file)
    return backup_file
```

### /research backup

```python
@research_group.command("backup")
async def research_backup(self, event: AstrMessageEvent):
    # Backup is read-only from the user's perspective and safe to run anytime.
    backup_file = create_backup(
        self.store.store_file,
        self.data_dir / "backups",
    )
    if backup_file is None:
        yield event.plain_result("保存ファイルがまだないため、backup は作成されませんでした。")
        return
    yield event.plain_result(f"backup を作成しました: {backup_file.name}")
```

### storage/base.py

SQLite に進む前に、command が依存する interface を決めます。

```python
from abc import ABC, abstractmethod


class ResearchStoreBase(ABC):
    @abstractmethod
    def list_documents(self) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def get_document(self, doc_id: str) -> dict | None:
        raise NotImplementedError

    @abstractmethod
    def add_document(self, document: dict, chunks: list[dict]) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_document(self, doc_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def search_chunks_data(self) -> list[dict]:
        raise NotImplementedError
```

### storage/sqlite_store.py の最小形

```python
import json
import sqlite3
from pathlib import Path


class SQLiteResearchStore:
    def __init__(self, db_file: Path):
        self.db_file = db_file
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self):
        return sqlite3.connect(self.db_file)

    def _init_schema(self) -> None:
        # Store embeddings as JSON text first; optimize later only if needed.
        with self._connect() as conn:
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
                    data TEXT NOT NULL
                )
                """
            )

    def add_document(self, document: dict, chunks: list[dict]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO documents (id, data) VALUES (?, ?)",
                (document["id"], json.dumps(document, ensure_ascii=False)),
            )
            for chunk in chunks:
                conn.execute(
                    "INSERT OR REPLACE INTO chunks (id, doc_id, data) VALUES (?, ?, ?)",
                    (chunk["id"], chunk["doc_id"], json.dumps(chunk, ensure_ascii=False)),
                )
```
