# 05 Agent Mode: /research agent を作る

この Phase では、`/research agent <task>` を追加します。

`/research ask` は「検索して、prompt を作って、1回 LLM に聞く」固定 RAG です。`/research agent` は、LLM が tool を呼びながら考える agent mode です。

## 目的

この Phase の目的は以下です。

- `/research agent <task>` コマンドを作る。
- `tool_loop_agent()` を使う。
- `research_search` と `research_get_document` を agent に渡す。
- agent 用 system prompt を作る。
- max_steps と tool_call_timeout を設定化する。
- 最初は Research Note tool のみに限定する。

## ask と agent の違い

`/research ask` は速くて予測しやすいです。

```text
質問
検索
回答
```

`/research agent` は遅いですが柔軟です。

```text
質問
LLM が検索が必要と判断
research_search を呼ぶ
結果を見る
必要なら research_get_document を呼ぶ
比較や整理をする
回答する
```

最初は両方を残します。

- `/research ask`: 日常的な資料QA。
- `/research agent`: 比較、整理、複数ステップの調査。

## まだ早い場合

以下が未完成なら Phase 4 に戻ります。

- `research_search` tool がある。
- `research_get_document` tool がある。
- tool の返却が短く、source 情報を含む。
- `/research search` で検索品質を確認できる。

## 変更するファイル

```text
main.py
prompts.py
_conf_schema.json
tools/*.py
```

必要なら追加します。

```text
agent_prompts.py
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

例です。

```text
あなたは Research Note の研究補助 agent です。
ユーザーの依頼が保存済み資料に関係する場合、まず research_search を使って関連資料を探してください。
回答は検索結果に基づいてください。
資料にないことは推測せず、「資料からは分かりません」と書いてください。
根拠には doc_id/chunk_id を付けてください。
必要以上に tool を呼ばないでください。
```

ポイントです。

- いつ tool を使うか書く。
- 何を根拠にするか書く。
- 分からない場合のルールを書く。
- tool を呼びすぎないように書く。

## Step 3: ToolSet を作る

`tool_loop_agent()` には `ToolSet` を渡します。

最初は Research Note の tool だけ入れます。

```python
tools = ToolSet([
    self.research_search_tool,
    self.research_get_document_tool,
])
```

Web Search や MCP はまだ入れません。最初は保存済み資料だけで安定させます。

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

イメージです。

```python
llm_resp = await self.context.tool_loop_agent(
    event=event,
    chat_provider_id=provider_id,
    prompt=task,
    system_prompt=system_prompt,
    tools=tools,
    max_steps=agent_max_steps,
    tool_call_timeout=agent_tool_call_timeout,
)
```

`llm_generate()` ではなく `tool_loop_agent()` を使う点が重要です。

## Step 5: agent 用の失敗処理を入れる

agent は LLM と tool の両方を使うので、失敗箇所が増えます。

最低限扱うものです。

- provider がない。
- tool 実行が timeout する。
- agent が最終回答を返さない。
- tool 結果が空。

ユーザー向けメッセージは短くします。

```text
Research agent の実行に失敗しました。ログを確認してください。
```

詳細は log に出します。

## Step 6: tool 呼び出しを観察する

最初は agent が本当に tool を使っているか見たいです。

方法です。

- tool の `call` 内で logger.info を出す。
- `on_using_llm_tool` hook を将来使う。
- 返答に debug 情報を出す設定を作る。

最初は tool 側の log で十分です。

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
/research agent 資料に書かれていない内容があれば Unknowns に出して
```

期待することです。

- agent が `research_search` を使う。
- 回答に source が出る。
- 資料にないことは Unknowns に出る。
- tool を何十回も呼び続けない。

## よくある失敗

### agent が tool を使わない

system prompt に「まず research_search を使う」と書きます。tool description も強くします。

### tool を呼び続ける

`agent_max_steps` を小さくします。system prompt に「必要以上に tool を呼ばない」と書きます。

### 回答が一般知識に寄りすぎる

system prompt に「保存済み資料に基づく」「資料にないことは分からないと書く」を入れます。

### Web Search も使わせたくなる

まだ入れません。まず保存済み資料だけで安定させます。

## この Phase の完了条件

- `/research agent <task>` が使える。
- `tool_loop_agent()` を使っている。
- agent に渡す tool は Research Note tool のみに限定されている。
- agent が `research_search` を呼ぶ。
- 回答に citation がある。
- max_steps と timeout が設定化されている。
- `/research ask` も引き続き動く。

## 実装例

### agent_prompts.py

agent 用 prompt は通常の `/research ask` よりも、tool をどう使うかを強く書きます。

```python
def build_research_agent_system_prompt() -> str:
    # Keep the agent focused on saved Research Note sources.
    return """あなたは Research Note の研究補助 agent です。
ユーザーの依頼が保存済み資料に関係する場合、まず research_search を使って関連資料を探してください。
必要なら research_get_document で資料の概要を確認してください。
回答は保存済み資料に基づいてください。
資料にないことは推測せず、「資料からは分かりません」と書いてください。
根拠には doc_id/chunk_id を付けてください。
必要以上に tool を呼ばないでください。
"""
```

### /research agent

`tool_loop_agent()` の引数名は AstrBot のバージョンに合わせて確認してください。構造としては以下です。

```python
@research_group.command("agent")
async def research_agent(self, event: AstrMessageEvent, task: str = ""):
    # Agent mode lets the LLM decide when to call Research Note tools.
    task = self._extract_research_tail(event) or task.strip()
    if not task:
        yield event.plain_result("agent に依頼する内容を入力してください。")
        return

    try:
        provider_id = await self.context.get_current_chat_provider_id(
            umo=event.unified_msg_origin
        )
    except Exception:
        logger.error("Failed to get current chat provider.", exc_info=True)
        yield event.plain_result("利用可能な LLM provider が見つかりません。")
        return

    tools = ToolSet([
        self.research_search_tool,
        self.research_get_document_tool,
    ])

    try:
        llm_resp = await self.context.tool_loop_agent(
            event=event,
            chat_provider_id=provider_id,
            prompt=task,
            system_prompt=build_research_agent_system_prompt(),
            tools=tools,
            max_steps=int(self.config.get("agent_max_steps", 8)),
            tool_call_timeout=int(self.config.get("agent_tool_call_timeout", 60)),
        )
    except Exception:
        logger.error("Research agent failed.", exc_info=True)
        yield event.plain_result("Research agent の実行に失敗しました。ログを確認してください。")
        return

    answer = llm_resp.completion_text if llm_resp else "Research agent は回答を生成できませんでした。"
    yield event.plain_result(answer)
```

### 設定例

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
