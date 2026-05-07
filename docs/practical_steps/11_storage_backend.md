# 11 Storage Backend: 保存 backend を強くする

この Phase では、JSON 保存からより強い保存 backend へ進む準備をします。

最初は JSON で十分です。しかし、資料と chunk が増えると、読み書きが遅くなったり、検索や migration が大変になったりします。

## 目的

この Phase の目的は以下です。

- JSON の限界を理解する。
- schema_version と migration を管理する。
- backup と export/import を作る。
- 必要になったら SQLite へ移行する。
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
migrations.py
_conf_schema.json
```

SQLite に進む場合の候補です。

```text
storage/base.py
storage/json_store.py
storage/sqlite_store.py
```

## Step 1: まず JSON の backup を作る

SQLite に進む前に、JSON の backup を作ります。

コマンド候補です。

```text
/research backup
/research export
/research import_backup <file>
```

最初は `/research backup` だけでよいです。

例です。

```text
research_store.json
research_store.20260507_120000.bak.json
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
version なし: 旧 note 形式として migration
version 2: 現行形式
version が未来: 読み込まず警告
```

## Step 3: migration を関数に分ける

migration は store.py に直接書きすぎない方がよいです。

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

SQLite にすると、document と chunk を table にできます。

```text
documents table
chunks table
embeddings table
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

最初から完璧に抽象化しなくてよいです。SQLite に進む直前に整理しても大丈夫です。

## Step 6: embedding の保存を考える

embedding は list[float] なので JSON だとファイルが大きくなります。

選択肢です。

- JSON にそのまま保存する。
- SQLite の embeddings table に保存する。
- embedding だけ別ファイルにする。
- Milvus / Milvus Lite に保存する。

最初は JSON でよいです。重くなってから分けます。

## Step 7: Milvus は最後でよい

Milvus は本格的な vector database です。

使う判断基準です。

- chunk 数がかなり多い。
- embedding search が遅い。
- 複数 project を大量に扱う。
- 運用コストを受け入れられる。

Research Note の初期実用版では SQLite までで十分な可能性が高いです。

## 動作確認

backup を試します。

```text
/research backup
```

migration を試します。

```text
/research migrate
```

export を作った場合です。

```text
/research export
```

期待することです。

- backup ファイルができる。
- migration 前に backup される。
- migration 後に document 件数と chunk 件数が分かる。

## よくある失敗

### migration でデータが消える

必ず backup を先に作ります。migration は元ファイルを直接破壊しない形にします。

### SQLite にしたら既存コマンドが壊れる

store interface を揃えます。command 側が JSON の内部構造に直接触らないようにします。

### embedding で DB が大きくなる

embedding を別 table または別ファイルに分けることを検討します。

## この Phase の完了条件

- `schema_version` を見て読み込む。
- backup command がある。
- migration 前に backup する。
- export/import の方針がある。
- SQLite へ進む判断基準が明確。
- store の責任が command から分離されている。
