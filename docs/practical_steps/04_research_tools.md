# 04 Research Tools: Research Note を LLM tool 化する

この Phase では、Research Note の検索や資料取得を `FunctionTool` として公開します。

これにより、ユーザーが `/research ask` を直接打たなくても、LLM や agent が必要なときに Research Note を検索できるようになります。

## 目的

この Phase の目的は以下です。

- Research Note の機能を `FunctionTool` として定義する。
- `research_search` tool を作る。
- `research_get_document` tool を作る。
- `research_add_text` tool を作る。
- `context.add_llm_tools()` で tool を登録する。
- コマンドと tool で同じ検索ロジックを使う。

## tool 化とは何か

普通のコマンドは、人間が呼びます。

```text
/research search attention
```

tool は、LLM が呼びます。

```text
LLM: research_search(query="attention") を使う
Tool: 検索結果を返す
LLM: 検索結果を読んで回答する
```

実用的な研究補助に近づけるには、LLM が自分で資料検索できる必要があります。

## まだ早い場合

以下が未完成なら Phase 3 に戻ります。

- chunk 単位の検索ができる。
- `/research search` がある。
- 検索結果に citation 用情報がある。
- 検索ロジックが `search.py` にまとまっている。

## 変更するファイル

```text
main.py
store.py
search.py
```

新しく作る候補です。

```text
tools/__init__.py
tools/research_search.py
tools/research_get_document.py
tools/research_add_text.py
tool_utils.py
```

## Step 1: tool 用 helper を先に作る

tool と command が同じ処理を使えるよう、検索処理を関数に切り出します。

例です。

```python
async def search_research_store(
    store,
    query: str,
    top_k: int,
    embedding_provider=None,
) -> list[dict]:
    ...
```

この関数は、以下の両方から呼べるようにします。

- `/research search`
- `research_search` tool

大事なのは、同じ処理を2回書かないことです。

## Step 2: research_search tool を作る

`FunctionTool` は、LLM から呼ばれる関数の説明書です。

必要な情報です。

- `name`: tool 名。
- `description`: LLM がいつ使うべきかの説明。
- `parameters`: 引数の JSON schema。
- `call`: 実際の処理。

`research_search` の引数は最初は `query` と `top_k` だけで十分です。

```text
query: 検索したい質問やキーワード
top_k: 返す chunk 数
```

返却は長すぎない JSON 文字列にします。

例です。

```json
{
  "results": [
    {
      "doc_id": "doc_001",
      "chunk_id": "chunk_002",
      "title": "Transformer memo",
      "score": 0.82,
      "preview": "Self-attention は..."
    }
  ]
}
```

## Step 3: tool から plugin の store にアクセスする

tool は plugin class の外に置くことが多いです。そのため、store をどう渡すかを決めます。

簡単な方法です。

- tool の `__init__` で store と config を受け取る。
- plugin の `__init__` で tool を作る。

イメージです。

```python
self.context.add_llm_tools(
    ResearchSearchTool(self.store, self.config, self._get_embedding_provider),
)
```

最初は完璧な設計にしなくてよいです。大事なのは、tool が store を読めることです。

## Step 4: research_get_document tool を作る

検索結果だけでは、資料全体の title や chunk 一覧を知りたい場合があります。

`research_get_document` を作ります。

引数です。

```text
doc_id: document ID
```

返す情報です。

- title
- source_type
- source_uri
- tags
- chunk_count
- chunk previews

全文を返すと長すぎるので、最初は preview でよいです。

## Step 5: research_add_text tool を作る

agent が整理したメモを Research Note に保存できるようにする tool です。

ただし、自動保存は危険です。最初は agent mode では使わず、将来のために用意するだけでもよいです。

引数です。

```text
title: 資料タイトル
content: 保存する本文
tags: 任意
```

安全策です。

- 長すぎる content は拒否する。
- source_type は `agent_note` などにする。
- 将来はユーザー確認を挟む。

## Step 6: context.add_llm_tools で登録する

plugin の `__init__` で登録します。

```python
self.context.add_llm_tools(
    ResearchSearchTool(...),
    ResearchGetDocumentTool(...),
)
```

`research_add_text` は最初から登録するか迷うところです。安全を優先するなら、まずは検索系 tool だけ登録します。

## Step 7: ToolSet で使う準備をする

次の Phase の `/research agent` では、必要な tool だけを `ToolSet` に入れます。

そのため、tool 名を決めておきます。

```text
research_search
research_get_document
research_add_text
```

名前は短く、用途が分かるものにします。

## 動作確認

tool は直接チャットで呼ぶものではありません。

まずは登録されているか log で確認します。

次に、簡単なテスト用コマンドを一時的に作ってもよいです。

```text
/research tooltest attention
```

このコマンドの中で `ResearchSearchTool.call(...)` 相当の処理を呼び、結果を表示します。

または、次の Phase の `/research agent` で実際に使って確認します。

## よくある失敗

### tool が store を読めない

tool class に store を渡しているか確認します。

### tool の返却が長すぎる

LLM tool の返却は短くします。本文全文ではなく preview と ID を返し、必要なら `research_get_document` を呼ばせます。

### command と tool で検索結果が違う

検索処理を2箇所に書いている可能性があります。共通 helper に寄せます。

### LLM が tool を使わない

tool description に「研究資料に関する質問では使う」と明記します。agent prompt 側でも使うように指示します。

## この Phase の完了条件

- `research_search` tool がある。
- `research_get_document` tool がある。
- tool が `context.add_llm_tools()` で登録される。
- tool 返却が短い JSON 文字列になっている。
- command と tool が同じ検索 helper を使う。
- 次の `/research agent` で渡せる状態になっている。

## 実装例

### tool_utils.py

command と tool の共通検索関数です。

```python
async def search_research_store(
    store,
    query: str,
    top_k: int,
    embedding_provider=None,
    keyword_weight: float = 0.4,
    embedding_weight: float = 0.6,
    min_score: float = 0.05,
) -> list[dict]:
    # Keep command and tool retrieval behavior identical.
    data = store.load_store()
    query_embedding = None
    if embedding_provider:
        query_embedding = await embedding_provider.get_embedding(query)

    return hybrid_search_chunks(
        query=query,
        documents=data["documents"],
        chunks=data["chunks"],
        query_embedding=query_embedding,
        top_k=top_k,
        keyword_weight=keyword_weight,
        embedding_weight=embedding_weight,
        min_score=min_score,
    )


def compact_search_results(results: list[dict], preview_chars: int = 300) -> dict:
    # Tool output should be short enough for the LLM to read.
    compact = []
    for result in results:
        chunk = result["chunk"]
        document = result["document"]
        compact.append(
            {
                "doc_id": chunk.get("doc_id"),
                "chunk_id": chunk.get("id"),
                "title": document.get("title", ""),
                "score": round(float(result.get("hybrid_score", 0.0)), 4),
                "reason": result.get("match_reason", ""),
                "preview": str(chunk.get("content", ""))[:preview_chars],
            }
        )
    return {"results": compact}
```

### tools/research_search.py

実際の `FunctionTool` への変換部分は AstrBot の実装に合わせて調整します。

```python
import json

from astrbot.api import logger

from ..tool_utils import compact_search_results, search_research_store


class ResearchSearchTool:
    name = "research_search"
    description = "Search saved Research Note documents and return cited chunks."

    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query or research question."},
            "top_k": {"type": "integer", "description": "Maximum number of chunks to return."},
        },
        "required": ["query"],
    }

    def __init__(self, store, config, get_embedding_provider):
        self.store = store
        self.config = config
        self.get_embedding_provider = get_embedding_provider

    async def call(self, query: str, top_k: int | None = None) -> str:
        # Return JSON so the LLM can parse fields reliably.
        logger.info("research_search tool called: %s", query)
        results = await search_research_store(
            store=self.store,
            query=query,
            top_k=top_k or int(self.config.get("top_k", 5)),
            embedding_provider=self.get_embedding_provider(),
            keyword_weight=float(self.config.get("keyword_weight", 0.4)),
            embedding_weight=float(self.config.get("embedding_weight", 0.6)),
            min_score=float(self.config.get("min_score", 0.05)),
        )
        return json.dumps(compact_search_results(results), ensure_ascii=False)
```

### tools/research_get_document.py

Document 全文ではなく、metadata と chunk preview を返します。

```python
import json


class ResearchGetDocumentTool:
    name = "research_get_document"
    description = "Get metadata and chunk previews for a saved Research Note document."

    parameters = {
        "type": "object",
        "properties": {"doc_id": {"type": "string", "description": "Document ID."}},
        "required": ["doc_id"],
    }

    def __init__(self, store, preview_chars: int = 300):
        self.store = store
        self.preview_chars = preview_chars

    async def call(self, doc_id: str) -> str:
        # Avoid returning full long documents through tool output.
        data = self.store.load_store()
        document = next((doc for doc in data["documents"] if doc.get("id") == doc_id), None)
        if not document:
            return json.dumps({"error": "document_not_found", "doc_id": doc_id}, ensure_ascii=False)

        chunks = [chunk for chunk in data["chunks"] if chunk.get("doc_id") == doc_id]
        return json.dumps(
            {
                "document": document,
                "chunks": [
                    {
                        "chunk_id": chunk.get("id"),
                        "index": chunk.get("index"),
                        "preview": str(chunk.get("content", ""))[: self.preview_chars],
                    }
                    for chunk in chunks
                ],
            },
            ensure_ascii=False,
        )
```

### plugin で登録する形

```python
def _register_research_tools(self):
    # Register read-only tools first. Add write tools later with confirmation.
    self.research_search_tool = ResearchSearchTool(
        self.store,
        self.config,
        self._get_embedding_provider,
    )
    self.research_get_document_tool = ResearchGetDocumentTool(self.store)

    self.context.add_llm_tools(
        self.research_search_tool,
        self.research_get_document_tool,
    )
```
