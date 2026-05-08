# 08 MCP: MCP tool と安全に連携する

この Phase では、Research Note の agent mode から MCP tool を使えるようにします。

MCP は強力ですが、外部プロセス、ファイル、ブラウザ、論文検索などにつながる可能性があります。必ず allowlist と明示的な mode を使います。

## 目的

この Phase の目的は以下です。

- `allowed_mcp_tools` 設定を追加する。
- MCP tool を allowlist で選ぶ。
- `/research agent_mcp <task>` を作る。
- MCP tool の結果を保存する前に確認を挟む。
- timeout や長すぎる結果を扱う。

## MCP は Research Note が直接起動しない

AstrBot 本体は `data/mcp_server.json` から MCP server を起動します。

Research Note は、すでに AstrBot に登録された MCP tool を使います。

つまり Research Note の責任は以下です。

- どの MCP tool を agent に渡すか選ぶ。
- MCP 結果をどう扱うか決める。
- 保存する場合に確認を挟む。

MCP server の起動や接続管理は AstrBot 本体に任せます。

## まだ早い場合

以下が未完成なら Phase 7 以前に戻ります。

- `/research agent` が安定している。
- tool allowlist の考え方が入っている。
- import preview と confirm がある。
- Web や外部情報を保存済み資料と区別できる。

## 変更するファイル

```text
main.py
_conf_schema.json
```

必要なら追加します。

```text
tool_selectors.py
mcp_result_formatter.py
```

## Step 1: 設定を追加する

MCP も default off にします。

```json
"enable_mcp_research": {
  "description": "research agent で MCP tool を使う",
  "type": "bool",
  "default": false
},
"allowed_mcp_tools": {
  "description": "research agent に渡す MCP tool 名",
  "type": "list",
  "items": {"type": "string"},
  "default": []
}
```

## Step 2: allowed_mcp_tools から ToolSet を作る

`context.get_llm_tool_manager()` から tool を取得します。

考え方です。

```text
tool manager を取得
Research Note tool を ToolSet に入れる
allowed_mcp_tools の名前を順に見る
存在する tool を ToolSet に追加する
存在しない tool は log warning
```

全 MCP tool を渡してはいけません。必要なものだけ渡します。

## Step 3: agent_mcp を作る

通常の agent と分けます。

```text
/research agent <task>: Research Note tool のみ
/research agent_web <task>: Research Note + Web Search
/research agent_mcp <task>: Research Note + 許可された MCP tool
```

明示的に分ける理由です。

- 外部 tool の使用が分かりやすい。
- 間違って MCP を使うリスクを下げる。
- 問題が起きたとき切り分けやすい。

## Step 4: MCP 用 system prompt を作る

例です。

```text
必要な場合のみ、許可された MCP tool を使ってください。
MCP tool の結果は外部情報またはローカル処理結果として扱い、保存済み資料とは区別してください。
MCP tool の結果を Research Note に保存する場合は、ユーザー確認が必要です。
危険な操作、削除、書き込み、外部送信を勝手に行わないでください。
```

tool の内容によっては、さらに強い制限が必要です。

## Step 5: 結果を短くする

MCP tool は長い結果を返すことがあります。

Research Note 側では、agent に渡す前に完全には制御できない場合もありますが、次の工夫ができます。

- agent prompt で短い結果を求める。
- tool allowlist を絞る。
- `max_steps` を小さめにする。
- 保存時は preview と confirm を使う。

## Step 6: MCP 結果の保存は import に寄せる

MCP tool の結果をそのまま保存する専用機能を最初から作らなくてよいです。

まずは agent にこう返させます。

```text
この結果を保存したい場合は、内容を確認して /research import text で保存してください。
```

後で pending import に自動登録する機能を作れます。

## 動作確認

AstrBot 側で MCP server が有効な状態にします。

`allowed_mcp_tools` に1つだけ tool を入れます。

試すコマンドです。

```text
/research agent_mcp 許可された MCP tool を使って必要な情報を確認し、保存済み資料と区別して説明して
```

期待することです。

- allowlist の tool だけ使う。
- Research Note tool も使える。
- MCP 結果を保存済み資料と区別する。
- 勝手に保存しない。

## よくある失敗

### MCP tool が見つからない

AstrBot の `data/mcp_server.json`、MCP server の起動状態、tool 名を確認します。

### agent が危険な tool を使う

allowlist から外します。Research Note 側で全 tool を渡さない設計にします。

### 結果が長すぎる

より狭い tool を使うか、agent prompt に要約を指示します。

### MCP と Web Search の責任が混ざる

mode を分けます。`agent_web` と `agent_mcp` を同時に強くしすぎない方が安全です。

## この Phase の完了条件

- MCP 使用は default off。
- `allowed_mcp_tools` がある。
- `/research agent_mcp <task>` がある。
- allowlist の tool だけ ToolSet に入る。
- MCP 結果を勝手に保存しない。
- MCP 結果と保存済み資料が区別される。

## 実装例

### MCP tool selector

Web tool と同じく、allowlist だけを渡します。

```python
from astrbot.api import logger


def select_allowed_mcp_tools(context, allowed_names: list[str]) -> list:
    # MCP tools can be powerful, so never expose all of them by default.
    tool_manager = context.get_llm_tool_manager()
    selected = []
    for name in allowed_names:
        tool = tool_manager.get_tool(name)
        if tool is None:
            logger.warning("Configured MCP tool not found: %s", name)
            continue
        selected.append(tool)
    return selected
```

### MCP 用 prompt

```python
def build_mcp_research_system_prompt() -> str:
    # MCP results must be treated as external tool results until user confirms saving.
    return """あなたは Research Note の MCP research agent です。
まず research_search で保存済み資料を確認してください。
必要な場合のみ、許可された MCP tool を使ってください。
MCP tool の結果は外部情報またはローカル処理結果として扱い、保存済み資料とは区別してください。
MCP tool の結果を Research Note に保存する場合は、ユーザー確認が必要です。
危険な操作、削除、書き込み、外部送信を勝手に行わないでください。
"""
```

### /research agent_mcp

```python
@research_group.command("agent_mcp")
async def research_agent_mcp(self, event: AstrMessageEvent, task: str = ""):
    # MCP mode is explicit because tools may touch external systems or files.
    if not self.config.get("enable_mcp_research", False):
        yield event.plain_result("MCP research は設定で無効です。")
        return

    task = self._extract_research_tail(event) or task.strip()
    if not task:
        yield event.plain_result("agent_mcp に依頼する内容を入力してください。")
        return

    mcp_tools = select_allowed_mcp_tools(
        self.context,
        list(self.config.get("allowed_mcp_tools", [])),
    )
    tools = ToolSet([
        self.research_search_tool,
        self.research_get_document_tool,
        *mcp_tools,
    ])

    try:
        llm_resp = await self.context.tool_loop_agent(
            event=event,
            chat_provider_id=await self.context.get_current_chat_provider_id(
                umo=event.unified_msg_origin
            ),
            prompt=task,
            system_prompt=build_mcp_research_system_prompt(),
            tools=tools,
            max_steps=int(self.config.get("agent_max_steps", 8)),
            tool_call_timeout=int(self.config.get("agent_tool_call_timeout", 60)),
        )
    except Exception:
        logger.error("MCP research agent failed.", exc_info=True)
        yield event.plain_result("MCP research agent の実行に失敗しました。ログを確認してください。")
        return

    yield event.plain_result(llm_resp.completion_text if llm_resp else "回答を生成できませんでした。")
```
