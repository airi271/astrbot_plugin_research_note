# 05 Agent Mode: /research agent を作る

この Phase では、`/research agent <task>` を追加します。

`/research ask` は、検索して prompt を作り、1回 LLM に聞く固定 RAG です。`/research agent` は、LLM が Research Note tools を呼びながら考える agent mode です。

## 目的

この Phase の目的は以下です。

- `/research agent <task>` コマンドを作る。
- `tool_loop_agent()` を使う。
- Research Note tools だけを agent に渡す。
- agent 用 system prompt を作る。
- `agent_max_steps` と `agent_tool_call_timeout` を設定化する。
- 保存と削除は、明示依頼がある時だけ tool を使うよう制御する。

## ask と agent の違い

`/research ask` は速くて予測しやすいです。

```text
質問
embedding 検索
回答
```

`/research agent` は遅いですが柔軟です。

```text
依頼
LLM が必要な tool を判断
research_search を呼ぶ
必要なら research_get_document や research_list_documents を呼ぶ
保存依頼が明確なら research_add_text を呼ぶ
削除依頼が明確なら research_delete_document を呼ぶ
回答する
```

最初は両方を残します。

- `/research ask`: 日常的な資料QA。
- `/research agent`: 比較、整理、複数ステップの調査、tool を使う作業。

## まだ早い場合

以下が未完成なら Phase 4 に戻ります。

- `research_search` tool がある。
- `research_get_document` tool がある。
- `research_list_documents` tool がある。
- `research_add_text` tool がある。
- `research_delete_document` tool がある。
- tool の返却が短い JSON 文字列になっている。
- `/research search` と tool が同じ検索 helper を使っている。

## 変更するファイル

```text
main.py
agent_prompts.py
_conf_schema.json
README.md
README_JP.md
```

## Step 1: 設定を追加する

`_conf_schema.json` に agent 用設定を追加します。

```json
"agent_max_steps": {
  "description": "research agent が tool を呼ぶ最大ステップ数",
  "type": "int",
  "default": 8,
  "minimum": 1,
  "maximum": 30
},
"agent_tool_call_timeout": {
  "description": "research agent の tool 呼び出し timeout 秒",
  "type": "int",
  "default": 60,
  "minimum": 5,
  "maximum": 300
}
```

最初は `max_steps=8` くらいでよいです。大きすぎると tool を呼び続けることがあります。

## Step 2: agent prompt を作る

agent 用の system prompt は重要です。

方針です。

- 保存済み資料に関する依頼では、まず `research_search` を使う。
- 必要なら `research_get_document` や `research_list_documents` を使う。
- 回答は保存済み資料と tool 結果に基づく。
- 資料にないことは推測しない。
- `research_add_text` は明示的な保存依頼がある時だけ使う。
- `research_delete_document` は明示的な削除依頼と doc_id がある時だけ使う。
- 曖昧な保存や削除は実行せず、ユーザーに確認する。

## Step 3: ToolSet を作る

`tool_loop_agent()` には `ToolSet` を渡します。

今回の実装では、登録済みの Research Note tools を tool manager から取り出します。

```python
def _get_research_tool_set(self) -> ToolSet:
    tool_manager = self.context.get_llm_tool_manager()
    tool_names = (
        "research_search",
        "research_get_document",
        "research_list_documents",
        "research_add_text",
        "research_delete_document",
    )
    tools = []
    for name in tool_names:
        tool = tool_manager.get_func(name)
        if tool:
            tools.append(tool)
    return ToolSet(tools)
```

Web Search や MCP はまだ入れません。まず Research Note tools だけで安定させます。

## Step 4: /research agent コマンドを追加する

流れです。

```text
task を取り出す
provider_id を取得する
ToolSet を作る
system_prompt を作る
tool_loop_agent を呼ぶ
completion_text を返す
```

`llm_generate()` ではなく `tool_loop_agent()` を使う点が重要です。

## Step 5: 失敗処理を入れる

agent は LLM と tool の両方を使うので、失敗箇所が増えます。

最低限扱うものです。

- provider がない。
- tool が登録されていない。
- tool 実行が timeout する。
- agent が最終回答を返さない。

ユーザー向けメッセージは短くします。

```text
Research agent の実行に失敗しました。ログを確認してください。
```

詳細は log に出します。

## 動作確認

資料を追加します。

```text
/research add Transformer は self-attention を使い、RNN より並列化しやすいです。
/research add RAG は検索した資料を LLM に渡して回答する仕組みです。
```

agent を試します。

```text
/research agent Transformer について保存済み資料を探して説明して
/research agent Transformer と RAG の違いを、保存済み資料だけで比較して
/research agent 保存済み資料の一覧を見て、何が入っているか整理して
```

安全確認です。

```text
/research agent この文章を保存して: RAG は retrieval augmented generation の略です。
/research agent doc_001 を削除して。confirm_doc_id は doc_001 です。
```

期待することです。

- agent が必要に応じて `research_search` を使う。
- 回答に source が出る。
- 資料にないことは Unknowns に出る。
- tool を何十回も呼び続けない。
- 保存や削除を勝手に実行しない。

## よくある失敗

### agent が tool を使わない

system prompt に「まず research_search を使う」と書きます。tool description も強くします。

### tool を呼び続ける

`agent_max_steps` を小さくします。system prompt に「必要以上に tool を呼ばない」と書きます。

### 回答が一般知識に寄りすぎる

system prompt に「保存済み資料に基づく」「資料にないことは分からないと書く」を入れます。

### agent が勝手に保存・削除する

system prompt に、保存と削除は明示依頼がある時だけ使うと書きます。削除 tool は `confirm_doc_id` が一致しないと削除できません。

### Web Search も使わせたくなる

まだ入れません。まず保存済み資料だけで安定させます。

## この Phase の完了条件

- `/research agent <task>` が使える。
- `tool_loop_agent()` を使っている。
- agent に渡す tool は Research Note tools のみに限定されている。
- agent が必要に応じて `research_search` を呼ぶ。
- 回答に citation がある。
- max_steps と timeout が設定化されている。
- 保存と削除は明示依頼がある場合だけ実行するよう prompt で制御されている。
- `/research ask` も引き続き動く。
