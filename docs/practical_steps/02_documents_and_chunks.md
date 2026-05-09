# 02 Documents And Chunks: Document と Chunk への移行

この Phase では、1つの note に全文を保存する形から、Document と Chunk に分ける形へ移行します。

根拠付きの研究補助では、長い資料を扱う必要があります。長い資料をそのまま LLM に渡すと、prompt が長くなりすぎたり、関係ない部分まで混ざったりします。そのため、資料を小さな chunk に分けて検索します。

## 目的

この Phase の目的は以下です。

- 資料全体を `Document` として保存する。
- 検索対象の小片を `Chunk` として保存する。
- 長文資料を chunk 分割できるようにする。
- 検索結果を note 単位ではなく chunk 単位にする。
- 回答の根拠に `doc_id`、`chunk_id`、title、source_uri を出す。
- 空の `research_notes.json` から新形式で保存を始められるようにする。

## なぜ Document と Chunk に分けるのか

Document は資料全体です。

```text
論文1本
Webページ1ページ
手で追加した長いメモ1件
PDFから抽出した文章1件
```

Chunk は検索に使う短い本文です。

```text
Document の 0文字目から800文字
Document の 600文字目から1400文字
Document の見出しごとの本文
```

分ける理由です。

- 長文でも検索しやすい。
- 回答に必要な部分だけ LLM に渡せる。
- citation を細かく出せる。
- 将来 URL、PDF、Web検索結果を同じ形で扱える。

## まだ早い場合

以下が未完成なら Phase 1 に戻ります。

- `/research show` がある。
- `/research delete` がある。
- 保存が atomic write になっている。
- ID 生成が重複しにくい。
- 既存機能が安定している。

## 変更するファイル

触る可能性が高いファイルです。

```text
main.py
store.py
search.py
prompts.py
_conf_schema.json
```

新しく作る候補です。今回の最小実装では `chunking.py` だけを追加します。

```text
models.py
chunking.py
```

最初は dataclass を使わず dict のままでもよいです。ただし、形を明確にするために `models.py` にコメントや型 alias を置くと読みやすくなります。

## 新しい保存形式

最初は1つの JSON にまとめます。

```json
{
  "schema_version": 2,
  "documents": [],
  "chunks": []
}
```

Document の例です。

```json
{
  "id": "doc_001",
  "project_id": "default",
  "title": "Transformer memo",
  "source_type": "text",
  "source_uri": "",
  "tags": [],
  "created_at": "2026-05-07T12:00:00",
  "updated_at": "2026-05-07T12:00:00"
}
```

Chunk の例です。

```json
{
  "id": "chunk_001_000",
  "doc_id": "doc_001",
  "index": 0,
  "content": "Transformer は attention を使います。",
  "embedding": null,
  "metadata": {}
}
```

## Step 1: Store の読み書きを新形式にする

`NoteStore` という名前のままでも動きますが、実用化では `ResearchStore` などに変えると分かりやすいです。

最初に作る関数です。

```python
def load_store(self) -> dict:
    ...

def save_store(self, data: dict) -> None:
    ...
```

返す形は必ず以下にします。

```python
{
    "schema_version": 2,
    "documents": [],
    "chunks": [],
}
```

ファイルがない場合も、この空構造を返します。

## Step 2: chunking.py を作る

chunk 分割は独立した関数にします。

```python
def split_text_into_chunks(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[str]:
    ...
```

考え方です。

```text
0文字目から800文字を chunk 1 にする
680文字目から1480文字を chunk 2 にする
1360文字目から2160文字を chunk 3 にする
```

overlap を入れる理由です。

- 文の途中で切れても、前後の文脈が少し残る。
- 検索時に重要な語が chunk 境界で失われにくい。

最初は文字数ベースで十分です。見出しや段落を考慮するのは後でよいです。

## Step 3: 設定を追加する

`_conf_schema.json` に追加します。

```json
"chunk_size": {
  "description": "資料を分割する chunk の文字数",
  "type": "int",
  "default": 800,
  "minimum": 200,
  "maximum": 3000
},
"chunk_overlap": {
  "description": "隣り合う chunk で重ねる文字数",
  "type": "int",
  "default": 120,
  "minimum": 0,
  "maximum": 1000
}
```

最初は `chunk_size=800`、`chunk_overlap=120` くらいが扱いやすいです。

## Step 4: add で Document と Chunk を保存する

`/research add <text>` の内部処理を変えます。

流れです。

```text
本文を取り出す
Document ID を作る
Document を作る
本文を chunks に分割する
各 chunk に chunk ID と doc_id を付ける
必要なら chunk ごとに embedding を作る
documents と chunks を保存する
```

ユーザーへの返答例です。

```text
資料を保存しました: doc_001
chunks: 3
```

## Step 5: list を Document 一覧にする

`/research list` は chunk ではなく Document を表示します。

例です。

```text
保存済み資料:
- doc_001: Transformer memo (chunks: 3)
- doc_002: RAG memo (chunks: 1)
```

chunk 数を出すと、長い資料かどうか分かります。

## Step 6: show を Document 表示にする

`/research show doc_001` は Document の metadata と chunk preview を表示します。

例です。

```text
doc_001
title: Transformer memo
source: text
chunks: 3

[chunk_001_000]
Transformer は attention...

[chunk_001_001]
Self-attention は...
```

全文を出すと長くなりすぎるので、最初は preview で十分です。

## Step 7: search を chunk 単位にする

`search_notes` を `search_chunks` に変えます。

入力は以下です。

```python
search_chunks(question: str, chunks: list[dict], top_k: int = 3)
```

返すのは chunk の list です。

ただし、回答では title も必要です。chunk から `doc_id` を見て Document を引ける helper を作ると便利です。

```python
def get_document_by_id(documents: list[dict], doc_id: str) -> dict | None:
    ...
```

## Step 8: prompt を chunk 用に変える

Phase 1 では `[note_001]` のように出していました。

chunk 化後は以下のようにします。

```text
[doc_001 / chunk_001_000]
title: Transformer memo
source: text
content:
Transformer は attention を使います。
```

LLM には、回答で `doc_001/chunk_001_000` のような source を示すように指示します。

## Step 9: 新形式だけに絞る

今回は旧データが空なので、旧 list 形式からの migration は作りません。余計な互換処理を入れると、保存形式が2種類あるように見えてコードが読みにくくなります。

最小実装の方針です。

- `load_store()` は `schema_version: 2` の dict だけを読む。
- ファイルがない、壊れている、形式が違う場合は空 store を返す。
- `save_store()` は必ず `schema_version: 2`、`documents`、`chunks` を保存する。

## 動作確認

短い資料を追加します。

```text
/research add Transformer は attention を使います。
/research list
/research show doc_001
/research ask Transformer は何を使いますか？
```

長い資料も追加します。

```text
/research add <長い文章>
/research list
/research show doc_002
/research ask 長い文章の中の具体的な内容について質問
```

期待することです。

- 長い資料が複数 chunk になる。
- `/research ask` が chunk を使って答える。
- 回答の source に `doc_id` と `chunk_id` が出る。

## よくある失敗

### chunk が空になる

入力 text を strip しすぎていないか確認します。

### overlap が chunk_size より大きい

`chunk_overlap < chunk_size` になるように調整します。今回の実装では、設定値が大きすぎる場合は `chunk_size - 1` に丸めています。

### 同じ chunk が無限に作られる

次の開始位置が前に進んでいるか確認します。

注意が必要な例です。

```text
start = start + chunk_size - chunk_overlap
```

この値が 0 以下になると無限 loop になります。実装では `chunk_size` を最低1にし、`chunk_overlap` を `chunk_size - 1` 以下に丸めて防ぎます。

### Document は見えるが検索されない

検索対象が `documents` ではなく `chunks` になっているか確認します。

## この Phase の完了条件

- 保存形式に `schema_version` がある。
- `documents` と `chunks` が保存される。
- `/research add` が chunk を作る。
- `/research list` が Document 一覧を出す。
- `/research show <doc_id>` が metadata と chunk preview を出す。
- `/research ask` が chunk 単位で検索する。
- 回答の source に `doc_id` と `chunk_id` が出る。
- 旧データ移行用の余計な互換処理を持たない。

## 実装例

ここでは、Phase 1 の note 形式から、Document / Chunk 形式へ進むための最小コードを示します。

### chunking.py

まずは文字数ベースで分割します。見出しや段落単位の分割は後で追加します。

```python
def split_text_into_chunks(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[str]:
    # Normalize line breaks so chunk boundaries are predictable.
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must not be negative")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = end - chunk_overlap

    return chunks
```

### store.py

常に同じ形の dict を返すようにします。

```python
import json
from pathlib import Path

from astrbot.api import logger

EMPTY_STORE = {"schema_version": 2, "documents": [], "chunks": []}


class NoteStore:
    def __init__(self, notes_file: Path):
        self.notes_file = notes_file
        self.notes_file.parent.mkdir(parents=True, exist_ok=True)

    def load_store(self) -> dict:
        # Keep command code simple by hiding file/schema problems here.
        if not self.notes_file.exists():
            return dict(EMPTY_STORE)
        try:
            with self.notes_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            logger.error("research_notes.json is broken.", exc_info=True)
            return dict(EMPTY_STORE)

        if not isinstance(data, dict) or data.get("schema_version") != 2:
            return dict(EMPTY_STORE)

        return {
            "schema_version": 2,
            "documents": data.get("documents", []),
            "chunks": data.get("chunks", []),
        }

    def save_store(self, data: dict) -> None:
        # Atomic write prevents partially written JSON from replacing good data.
        tmp_file = self.notes_file.with_suffix(".json.tmp")
        with tmp_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_file.replace(self.notes_file)
```

### add の内部処理

`/research add` では Document を1件作り、本文を複数 Chunk に分けます。

```python
def _next_doc_id(documents: list[dict]) -> str:
    max_num = 0
    for document in documents:
        doc_id = str(document.get("id", ""))
        if not doc_id.startswith("doc_"):
            continue
        try:
            max_num = max(max_num, int(doc_id.removeprefix("doc_")))
        except ValueError:
            continue
    return f"doc_{max_num + 1:03d}"


def _chunk_id(doc_id: str, index: int) -> str:
    return f"chunk_{doc_id.removeprefix('doc_')}_{index:03d}"
```

```python
data = self.store.load_store()
doc_id = self._next_doc_id(data["documents"])
now = datetime.now().isoformat(timespec="seconds")

document = {
    "id": doc_id,
    "project_id": "default",
    "title": content.replace("\n", " ")[:40] or doc_id,
    "source_type": "text",
    "source_uri": "",
    "tags": [],
    "created_at": now,
    "updated_at": now,
}

chunk_texts = split_text_into_chunks(
    content,
    chunk_size=int(self.config.get("chunk_size", 800)),
    chunk_overlap=int(self.config.get("chunk_overlap", 120)),
)

embedding_provider = self._get_embedding_provider()
new_chunks = []
for index, chunk_text in enumerate(chunk_texts):
    embedding = None
    if embedding_provider:
        embedding = await embedding_provider.get_embedding(chunk_text)
    new_chunks.append(
        {
            "id": self._chunk_id(doc_id, index),
            "doc_id": doc_id,
            "index": index,
            "content": chunk_text,
            "embedding": embedding,
            "metadata": {},
        }
    )

data["documents"].append(document)
data["chunks"].extend(new_chunks)
self.store.save_store(data)
yield event.plain_result(f"資料を保存しました: {doc_id}\nchunks: {len(new_chunks)}")
```
