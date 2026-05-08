# 03 Hybrid Search And Citation: 検索品質と根拠表示を強くする

この Phase では、検索を `keyword` と `embedding` のどちらか一方ではなく、両方を使う `hybrid search` にします。また、回答の根拠をより分かりやすく表示します。

## 目的

この Phase の目的は以下です。

- keyword score を計算する。
- embedding score を計算する。
- 2つの score を混ぜて hybrid score を作る。
- 検索結果に score と match reason を付ける。
- `/research search <query>` を追加する。
- 回答 prompt に citation rule を入れる。
- 回答に source list と unknowns を出せるようにする。

## なぜ hybrid search が必要か

keyword search は、同じ単語があると強いです。

```text
質問: Transformer
資料: Transformer は attention を使います。
```

embedding search は、意味が近い文を探すのが得意です。

```text
質問: 文章生成で外部資料を使う方法
資料: RAG は検索した資料を LLM に渡して回答する仕組みです。
```

研究資料では、固有名詞、略語、式、論文名が多いので keyword も重要です。一方で、言い換え質問には embedding が有効です。そのため両方を使います。

## まだ早い場合

以下が未完成なら Phase 2 に戻ります。

- Document と Chunk に分かれている。
- 検索対象が chunk になっている。
- 回答 source に `doc_id` と `chunk_id` が出る。
- chunk ごとの embedding を保存できる、または provider がない場合に keyword で動く。

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

検索結果は chunk そのものだけでなく、score 情報を持たせます。

例です。

```python
{
    "chunk": chunk,
    "document": document,
    "keyword_score": 2.0,
    "embedding_score": 0.82,
    "hybrid_score": 0.76,
    "match_reason": "keyword+embedding",
}
```

この形にすると、`/research search` で「なぜ選ばれたか」を表示できます。

## Step 2: keyword score を作る

最初は簡単でよいです。

```text
質問を tokenize する
chunk content に含まれる token 数を数える
長すぎる chunk が有利になりすぎないよう少し正規化する
```

例です。

```python
def keyword_score(query: str, content: str) -> float:
    tokens = tokenize(query)
    if not tokens:
        return 0.0
    content_lower = content.lower()
    hits = sum(1 for token in tokens if token in content_lower)
    return hits / len(tokens)
```

`0.0` から `1.0` に近い値になると扱いやすいです。

## Step 3: embedding score を作る

すでに `cosine_similarity` があるなら、それを使います。

```python
embedding_score = cosine_similarity(query_embedding, chunk_embedding)
```

provider がない場合や chunk に embedding がない場合は `0.0` にします。

```python
if not query_embedding or not chunk_embedding:
    embedding_score = 0.0
```

## Step 4: hybrid score を作る

最初は重み付き平均で十分です。

```python
hybrid_score = keyword_weight * keyword_score + embedding_weight * embedding_score
```

設定例です。

```json
"keyword_weight": {
  "description": "hybrid search で keyword score に掛ける重み",
  "type": "float",
  "default": 0.4,
  "minimum": 0,
  "maximum": 1
},
"embedding_weight": {
  "description": "hybrid search で embedding score に掛ける重み",
  "type": "float",
  "default": 0.6,
  "minimum": 0,
  "maximum": 1
}
```

provider がない環境では keyword だけで動かします。

```text
embedding provider あり: hybrid
embedding provider なし: keyword
```

## Step 5: min_score を入れる

score が低すぎる chunk は使わないようにします。

```json
"min_score": {
  "description": "検索結果として採用する最小 score",
  "type": "float",
  "default": 0.05,
  "minimum": 0,
  "maximum": 1
}
```

最初は低めでよいです。高すぎると何も見つからなくなります。

## Step 6: /research search を作る

`/research search <query>` は LLM を呼びません。

検索結果だけを表示します。

例です。

```text
/research search attention mechanism
```

返答例です。

```text
検索結果:
1. doc_001 / chunk_002 score=0.82 reason=keyword+embedding
   title: Transformer memo
   preview: Self-attention は入力系列内の...

2. doc_003 / chunk_001 score=0.41 reason=embedding
   title: Attention survey
   preview: Neural attention mechanisms...
```

これは実用上とても重要です。回答が変なとき、検索が悪いのか、LLM が悪いのかを切り分けられます。

## Step 7: citation rule を prompt に入れる

`prompts.py` の回答 prompt に、source の書き方を明示します。

例です。

```text
回答では、根拠にした文の近くに [doc_001/chunk_002] の形式で引用を付けてください。
資料にない内容は「資料からは分かりません」と書いてください。
回答の最後に Sources と Unknowns を付けてください。
```

出力形式も指定します。

```text
Answer:
...

Sources:
- doc_001/chunk_002: Transformer memo

Unknowns:
- 資料からは分からない点...
```

## Step 8: max_context_chars を入れる

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

## 動作確認

資料を追加します。

```text
/research add Transformer は self-attention mechanism を使います。RNN と違い、系列を並列に処理しやすいです。
/research add RAG は検索した資料を LLM に渡して回答する方法です。
```

検索します。

```text
/research search attention
/research search 外部資料を使って回答する方法
```

質問します。

```text
/research ask Transformer の特徴は？
/research ask 外部資料を使って回答する方法は？
```

期待することです。

- `/research search` に score が出る。
- keyword と embedding のどちらで見つかったか分かる。
- `/research ask` の回答に `doc_id/chunk_id` が出る。
- 資料にない質問では Unknowns に出る。

## よくある失敗

### embedding score が全部 0 になる

chunk に embedding が保存されているか確認します。Phase 2 の migration 後は `/research reindex` が必要です。

### keyword search だけより悪くなった

`keyword_weight` を上げます。研究資料では固有名詞が重要なので、keyword を軽くしすぎない方がよいです。

### 何も検索されない

`min_score` が高すぎる可能性があります。まず `0.0` または `0.05` にします。

### citation が回答に出ない

prompt の source 表記を簡単にします。LLM は複雑な形式を守れないことがあります。

## この Phase の完了条件

- keyword score がある。
- embedding score がある。
- hybrid score がある。
- provider がない場合は keyword で動く。
- `/research search <query>` が使える。
- 検索結果に score、reason、preview が出る。
- `/research ask` の回答に citation が出る。
- Sources と Unknowns が回答に含まれる。

## 実装例

### search.py

keyword と embedding を混ぜて chunk を検索します。

```python
def keyword_score(query: str, content: str) -> float:
    # Score how many query tokens appear in the chunk text.
    tokens = tokenize(query)
    if not tokens:
        return 0.0
    content_lower = content.lower()
    hits = sum(1 for token in tokens if token in content_lower)
    return hits / len(tokens)


def build_document_index(documents: list[dict]) -> dict[str, dict]:
    # Lookup document metadata by doc_id while formatting results.
    return {str(doc.get("id")): doc for doc in documents}


def hybrid_search_chunks(
    query: str,
    documents: list[dict],
    chunks: list[dict],
    query_embedding: list[float] | None = None,
    top_k: int = 5,
    keyword_weight: float = 0.4,
    embedding_weight: float = 0.6,
    min_score: float = 0.05,
) -> list[dict]:
    doc_index = build_document_index(documents)
    results = []

    for chunk in chunks:
        content = str(chunk.get("content", ""))
        k_score = keyword_score(query, content)
        e_score = 0.0

        chunk_embedding = chunk.get("embedding")
        if query_embedding and isinstance(chunk_embedding, list):
            e_score = cosine_similarity(query_embedding, chunk_embedding)

        hybrid_score = (
            keyword_weight * k_score + embedding_weight * e_score
            if query_embedding
            else k_score
        )
        if hybrid_score < min_score:
            continue

        reason = []
        if k_score > 0:
            reason.append("keyword")
        if e_score > 0:
            reason.append("embedding")

        results.append(
            {
                "chunk": chunk,
                "document": doc_index.get(str(chunk.get("doc_id")), {}),
                "keyword_score": k_score,
                "embedding_score": e_score,
                "hybrid_score": hybrid_score,
                "match_reason": "+".join(reason) or "unknown",
            }
        )

    results.sort(key=lambda item: item["hybrid_score"], reverse=True)
    return results[:top_k]
```

### /research search

LLM を呼ばず、検索結果だけを表示します。

```python
@research_group.command("search")
async def research_search(self, event: AstrMessageEvent, query: str = ""):
    # This command helps debug retrieval quality before asking the LLM.
    query = self._extract_research_tail(event) or query.strip()
    if not query:
        yield event.plain_result("検索 query を入力してください。")
        return

    data = self.store.load_store()
    embedding_provider = self._get_embedding_provider()
    query_embedding = None
    if embedding_provider:
        query_embedding = await embedding_provider.get_embedding(query)

    results = hybrid_search_chunks(
        query=query,
        documents=data["documents"],
        chunks=data["chunks"],
        query_embedding=query_embedding,
        top_k=int(self.config.get("top_k", 5)),
        keyword_weight=float(self.config.get("keyword_weight", 0.4)),
        embedding_weight=float(self.config.get("embedding_weight", 0.6)),
        min_score=float(self.config.get("min_score", 0.05)),
    )

    lines = ["検索結果:"]
    for index, result in enumerate(results, start=1):
        chunk = result["chunk"]
        document = result["document"]
        preview = str(chunk.get("content", "")).replace("\n", " ")[:80]
        lines.append(
            f"{index}. {chunk.get('doc_id')}/{chunk.get('id')} "
            f"score={result['hybrid_score']:.2f} reason={result['match_reason']}\n"
            f"   title: {document.get('title', '')}\n"
            f"   preview: {preview}"
        )
    yield event.plain_result("\n".join(lines))
```

### citation prompt

回答 prompt には citation 形式を明確に書きます。

```python
def build_cited_answer_prompt(question: str, results: list[dict]) -> str:
    # Convert search results into compact cited context blocks.
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
