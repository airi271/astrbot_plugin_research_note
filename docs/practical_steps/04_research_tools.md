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
