# 03 Embedding Search And Citation: embedding 検索と根拠表示を強くする

この Phase では、検索を `keyword` と `embedding` の hybrid にせず、`embedding` だけに絞ります。

理由は、現在の方針が「全 chunk に embedding を付ける」「キーワード検索 fallback は使わない」だからです。検索方式を1つに絞ると、実装も評価も分かりやすくなります。

Phase 3 でやることは、検索方式を増やすことではなく、embedding 検索の品質と citation を強くすることです。

## 目的

この Phase の目的は以下です。

- embedding score を検索結果に持たせる。
- score が低すぎる chunk を除外できるようにする。
- `/research search <query>` を追加し、LLM を呼ばず検索結果だけ確認できるようにする。
- 回答 prompt に citation rule を明確に入れる。
- 回答に Sources と Unknowns を出せるようにする。
- LLM に渡す context の最大文字数を制限する。

やらないことです。

- keyword score は作らない。
- hybrid score は作らない。
- embedding provider なしの fallback は作らない。

## なぜ embedding-only にするのか

今回の設計では、保存する chunk はすべて embedding を持つことにします。

```text
/research add
-> chunk に分割
-> すべての chunk に embedding を作成
-> 全 chunk 成功した場合だけ保存
```

この形にすると、検索時に「embedding がある chunk とない chunk が混ざる」問題を避けられます。

また、keyword fallback を入れると、以下のような混乱が起きます。

- embedding 検索なのか keyword 検索なのか結果から分かりにくい。
- embedding 失敗に気づかず、品質が低い検索で動き続ける。
- Phase 3 の評価軸がぶれる。

そのため Phase 3 では、embedding-only のまま品質を上げます。

## まだ早い場合

以下が未完成なら Phase 2 に戻ります。

- Document と Chunk に分かれている。
- `/research add` で全 chunk に embedding が保存される。
- embedding 生成に失敗した資料は保存されない。
- `/research ask` が embedding 検索だけで動く。
- 回答 source に `doc_id/chunk_id` が出る。

## 変更するファイル

```text
search.py
prompts.py
main.py
_conf_schema.json
```

必要なら追加します。

```text
citations.py
```

## Step 1: 検索結果の形を決める

今の `search_chunks_by_embedding()` は chunk の list を返します。

Phase 3 では、chunk だけでなく score と document metadata も持たせます。

例です。

```python
{
    "chunk": chunk,
    "document": document,
    "embedding_score": 0.82,
}
```

この形にすると、`/research search` で score、title、preview を表示できます。

## Step 2: document index を作る

chunk には `doc_id` があります。表示には Document の title や source_uri も必要です。

```python
def build_document_index(documents: list[dict]) -> dict[str, dict]:
    return {str(doc.get("id")): doc for doc in documents}
```

## Step 3: embedding search result を作る

`cosine_similarity()` を使い、query embedding と chunk embedding の類似度を計算します。

```python
def search_chunks_by_embedding(
    query_embedding: list[float],
    documents: list[dict],
    chunks: list[dict],
    top_k: int = 5,
    min_embedding_score: float = 0.0,
) -> list[dict]:
    doc_index = build_document_index(documents)
    results = []

    for chunk in chunks:
        chunk_embedding = chunk.get("embedding")
        if not isinstance(chunk_embedding, list):
            continue

        score = cosine_similarity(query_embedding, chunk_embedding)
        if score < min_embedding_score:
            continue

        results.append(
            {
                "chunk": chunk,
                "document": doc_index.get(str(chunk.get("doc_id")), {}),
                "embedding_score": score,
            }
        )

    results.sort(key=lambda item: item["embedding_score"], reverse=True)
    return results[:top_k]
```

## Step 4: min_embedding_score を入れる

score が低すぎる chunk は使わないようにします。

```json
"min_embedding_score": {
  "description": "検索結果として採用する最小 embedding score",
  "type": "float",
  "default": 0.0,
  "minimum": -1,
  "maximum": 1
}
```

最初は `0.0` でよいです。高くしすぎると何も見つからなくなります。

## Step 5: /research search を作る

`/research search <query>` は LLM を呼びません。

検索結果だけを表示します。

例です。

```text
/research search 医歯理工融合教育
```

返答例です。

```text
検索結果:
1. doc_003/chunk_003_001 score=0.82
   title: 東京科学大学、英語名 Institute of Science Tokyo...
   preview: 東京科学大学では、理工学系の学生が医歯学系の科目を...

2. doc_003/chunk_003_000 score=0.61
   title: 東京科学大学、英語名 Institute of Science Tokyo...
   preview: 東京科学大学は、2024年10月1日に...
```

これは実用上重要です。回答が変なとき、検索が悪いのか、LLM が悪いのかを切り分けられます。

## Step 6: citation rule を prompt に入れる

`prompts.py` の回答 prompt に、source の書き方を明示します。

例です。

```text
回答では、根拠にした文の近くに [doc_001/chunk_001_000] の形式で引用を付けてください。
資料にない内容は「資料からは分かりません」と書いてください。
回答の最後に Sources と Unknowns を付けてください。
```

出力形式も指定します。

```text
Answer:
...

Sources:
- doc_001/chunk_001_000: Transformer memo

Unknowns:
- 資料からは分からない点...
```

## Step 7: max_context_chars を入れる

検索結果 top_k が多くても、LLM に渡す文字数には上限が必要です。

```json
"max_context_chars": {
  "description": "LLM に渡す検索結果全体の最大文字数",
  "type": "int",
  "default": 6000,
  "minimum": 1000,
  "maximum": 30000
}
```

context pack を作るとき、合計文字数が上限を超えたら止めます。

## Step 8: embedding 不備を明確に扱う

embedding-only では、embedding がない chunk を黙って無視しません。

扱いは以下です。

- `/research add`: 全 chunk の embedding 作成に成功した場合だけ保存する。
- `/research ask`: embedding がない chunk があれば `/research reindex` を促す。
- `/research reindex`: 全 chunk の embedding を作り直す。長すぎる chunk はさらに分割する。

## 動作確認

資料を追加します。

```text
/research add 東京科学大学は、2024年10月1日に東京医科歯科大学と東京工業大学が統合して誕生した国立大学です。
/research add 医歯理工融合教育は、医歯学と理工学を横断して学ぶ教育構想です。
```

検索します。

```text
/research search 医歯理工融合教育
/research search 東京科学大学はいつ誕生しましたか？
```

質問します。

```text
/research ask 東京科学大学はいつ誕生しましたか？
/research ask 医歯理工融合教育とは何ですか？
```

期待することです。

- `/research add` の返答に `embedding: 全 chunk 作成済み` が出る。
- `/research search` に embedding score が出る。
- `/research ask` の回答に `doc_id/chunk_id` が出る。
- 資料にない質問では Unknowns に出る。

## よくある失敗

### embedding score が全部 0 になる

query embedding と chunk embedding の次元が同じか確認します。provider を変えた後は `/research reindex` が必要です。

### 何も検索されない

`min_embedding_score` が高すぎる可能性があります。まず `0.0` にします。

### embedding 作成で input length error が出る

Phase 2 の実装では、長すぎる chunk をさらに分割して再試行します。それでも失敗する場合は `chunk_size` を小さくします。

### citation が回答に出ない

prompt の source 表記を簡単にします。LLM は複雑な形式を守れないことがあります。

## この Phase の完了条件

- keyword search fallback がない。
- embedding score が検索結果に出る。
- `min_embedding_score` を設定できる。
- `/research search <query>` が embedding 検索だけで動く。
- 検索結果に score、title、preview が出る。
- `/research ask` の回答に citation が出る。
- Sources と Unknowns が回答に含まれる。
- `max_context_chars` で prompt に入れる総文字数を制御できる。

## 実装例

### search.py

embedding score だけで chunk を検索します。

```python
import math


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_document_index(documents: list[dict]) -> dict[str, dict]:
    return {str(doc.get("id")): doc for doc in documents}


def search_chunks_by_embedding(
    query_embedding: list[float],
    documents: list[dict],
    chunks: list[dict],
    top_k: int = 5,
    min_embedding_score: float = 0.0,
) -> list[dict]:
    doc_index = build_document_index(documents)
    results = []

    for chunk in chunks:
        chunk_embedding = chunk.get("embedding")
        if not isinstance(chunk_embedding, list):
            continue
        score = cosine_similarity(query_embedding, chunk_embedding)
        if score < min_embedding_score:
            continue
        results.append(
            {
                "chunk": chunk,
                "document": doc_index.get(str(chunk.get("doc_id")), {}),
                "embedding_score": score,
            }
        )

    results.sort(key=lambda item: item["embedding_score"], reverse=True)
    return results[:top_k]
```

### /research search

LLM を呼ばず、検索結果だけを表示します。

```python
@research_group.command("search")
async def research_search(self, event: AstrMessageEvent, query: str = ""):
    query = self._extract_research_tail(event) or query.strip()
    if not query:
        yield event.plain_result("検索 query を入力してください。")
        return

    embedding_provider = self._get_embedding_provider()
    if not embedding_provider:
        yield event.plain_result("embedding provider が設定されていません。")
        return

    data = self.store.load_store()
    query_embedding = await embedding_provider.get_embedding(query)
    results = search_chunks_by_embedding(
        query_embedding=query_embedding,
        documents=data["documents"],
        chunks=data["chunks"],
        top_k=int(self.config.get("top_k", 5)),
        min_embedding_score=float(self.config.get("min_embedding_score", 0.0)),
    )

    if not results:
        yield event.plain_result("関連する資料が見つかりませんでした。")
        return

    lines = ["検索結果:"]
    for index, result in enumerate(results, start=1):
        chunk = result["chunk"]
        document = result["document"]
        preview = str(chunk.get("content", "")).replace("\n", " ")[:80]
        lines.append(
            f"{index}. {chunk.get('doc_id')}/{chunk.get('id')} "
            f"score={result['embedding_score']:.2f}\n"
            f"   title: {document.get('title', '')}\n"
            f"   preview: {preview}"
        )
    yield event.plain_result("\n".join(lines))
```

### citation prompt

回答 prompt には citation 形式を明確に書きます。

```python
def build_cited_answer_prompt(question: str, results: list[dict]) -> str:
    blocks = []
    for result in results:
        chunk = result["chunk"]
        document = result["document"]
        source_id = f"{chunk.get('doc_id')}/{chunk.get('id')}"
        blocks.append(
            f"[{source_id}] title={document.get('title', '')}\n"
            f"{chunk.get('content', '')}"
        )

    return f"""あなたは研究補助AIです。
以下の資料だけを根拠にして回答してください。
根拠にした文の近くに [doc_id/chunk_id] の形式で citation を付けてください。
資料にない内容は Unknowns に書いてください。

資料:
{chr(10).join(blocks)}

質問:
{question}

出力形式:
Answer:
...

Sources:
- doc_id/chunk_id: title

Unknowns:
- 資料からは分からない点
"""
```
