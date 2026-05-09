# 04 Research Tools: Research Note を LLM tool 化する

この Phase では、Research Note の機能を AstrBot の `FunctionTool` として公開します。

現在の方針は embedding-only です。そのため、tool も keyword fallback や hybrid search を持たず、既存の embedding 検索 helper を使います。

## 目的

この Phase の目的は以下です。

- `research_search` tool を登録する。
- `research_get_document` tool を登録する。
- `research_list_documents` tool を登録する。
- `research_add_text` tool を登録する。
- `research_delete_document` tool を登録する。
- `/research search` と tool が同じ検索 helper を使う。
- tool 返却を短い JSON 文字列にする。

## 今回やらないこと

- `research_add_text` は、ユーザーが保存・記録を明確に依頼した場合だけ使う説明にします。
- `research_delete_document` は、ユーザーが削除を明確に依頼し、`confirm_doc_id` が `doc_id` と一致する場合だけ削除します。
- 自動で勝手に保存する agent 挙動は作りません。
- keyword search / hybrid search は入れません。

## まだ早い場合

以下が未完成なら Phase 3 に戻ります。

- `/research search <query>` がある。
- `search.py` に embedding-only 検索がある。
- 全 chunk に embedding が付いている。
- `/research ask` が embedding 検索だけで動く。

## 変更するファイル

```text
main.py
tool_utils.py
```

必要なら更新します。

```text
README.md
README_JP.md
```

## Step 1: 共通 helper を作る

command と tool で検索処理を2回書かないようにします。

`tool_utils.py` に置きます。

```python
async def search_research_store(
    store,
    query: str,
    top_k: int,
    embedding_provider,
    min_embedding_score: float = 0.0,
) -> tuple[dict, list[dict]]:
    ...
```

この helper は以下から使います。

- `/research search`
- `/research ask`
- `research_search` tool

## Step 2: tool 返却を短くする

LLM tool の返却は長すぎない JSON 文字列にします。

```json
{
  "results": [
    {
      "doc_id": "doc_001",
      "chunk_id": "chunk_001_000",
      "title": "Transformer memo",
      "source_uri": "",
      "score": 0.82,
      "preview": "Self-attention は..."
    }
  ]
}
```

本文全文は返しません。必要なら `research_get_document` で document metadata と chunk preview を取ります。

## Step 3: research_search tool を作る

`FunctionTool` を直接作り、handler に plugin method を渡します。

```python
FunctionTool(
    name="research_search",
    description="Search saved Research Note documents with embedding search.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "top_k": {"type": "integer"},
        },
        "required": ["query"],
    },
    handler=self._research_search_tool,
)
```

handler は JSON 文字列を返します。

```python
async def _research_search_tool(self, event, query: str, top_k: int | None = None) -> str:
    _, results = await search_research_store(...)
    return json.dumps(compact_search_results(results), ensure_ascii=False)
```

## Step 4: research_get_document tool を作る

`research_get_document` は document metadata と chunk preview を返します。

引数です。

```text
doc_id: document ID
```

返す情報です。

- document metadata
- chunk_count
- chunk previews
- each chunk has embedding or not

全文を返すと tool output が長くなるため、preview に留めます。

## Step 5: research_list_documents tool を作る

保存済み document の一覧を返します。

返す情報です。

- doc_id
- title
- source_type
- tags
- chunk_count
- created_at

## Step 6: research_add_text tool を作る

ユーザーが「保存して」「覚えて」「メモして」と明確に依頼した場合に、LLM が資料を追加できる tool です。

引数です。

```text
content: 保存する本文
title: 任意のタイトル
tags: 任意のタグ
```

保存時は `/research add` と同じ処理を使い、全 chunk の embedding 作成に成功した場合だけ保存します。

## Step 7: research_delete_document tool を作る

削除は危険なので、二重指定にします。

```text
doc_id: 削除対象
confirm_doc_id: doc_id と完全一致した場合だけ削除
```

一致しない場合は削除せず、error JSON を返します。

## Step 8: context.add_llm_tools で登録する

plugin の `__init__` で登録します。

```python
self.context.add_llm_tools(
    FunctionTool(... research_search ...),
    FunctionTool(... research_get_document ...),
    FunctionTool(... research_list_documents ...),
    FunctionTool(... research_add_text ...),
    FunctionTool(... research_delete_document ...),
)
```

同じ名前の tool がある場合、AstrBot 側で置き換えられます。

## 動作確認

tool は通常チャットで直接呼ぶものではありません。

確認方法です。

- plugin 起動時の log に `added LLM tool: research_search` が出る。
- plugin 起動時の log に `added LLM tool: research_get_document` が出る。
- plugin 起動時の log に `added LLM tool: research_list_documents` が出る。
- plugin 起動時の log に `added LLM tool: research_add_text` が出る。
- plugin 起動時の log に `added LLM tool: research_delete_document` が出る。
- `/research search <query>` が今まで通り動く。
- 次の Phase の `/research agent` から `ToolSet` に渡せる。

## よくある失敗

### tool が長い本文を返しすぎる

`preview` だけ返します。全文は返しません。

### command と tool で検索結果が違う

`search_research_store()` を両方から使っているか確認します。

### embedding provider がない

embedding-only 方針なので、tool も error JSON を返します。

```json
{"error": "embedding_provider_missing"}
```

### research_add_text が勝手に保存する

tool description に「Only use this when the user clearly asks to save or remember text」と書きます。Phase 5 の agent prompt でも勝手に保存しないようにします。

### research_delete_document が誤削除する

`confirm_doc_id` が `doc_id` と完全一致しない限り削除しません。Phase 5 の agent prompt でも勝手に削除しないようにします。

### LLM が tool を使わない

tool description に「stored research materials に関する質問で使う」と書きます。Phase 5 の agent prompt でも使うように指示します。

## この Phase の完了条件

- `research_search` tool が登録される。
- `research_get_document` tool が登録される。
- `research_list_documents` tool が登録される。
- `research_add_text` tool が登録される。
- `research_delete_document` tool が登録される。
- tool 返却が短い JSON 文字列になっている。
- `/research search` と tool が同じ `search_research_store()` を使う。
- `research_add_text` は明示的な保存依頼のときだけ使う説明になっている。
- `research_delete_document` は二重確認がないと削除しない。
