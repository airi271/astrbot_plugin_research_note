# 09 Multi-Agent: 研究作業を分担する

この Phase では、研究補助を複数の専門 agent に分けます。

最初から Multi-Agent にすると複雑すぎます。ここまでに検索、citation、tool、agent mode が安定してから進みます。

実装済みの方針です。

```text
/research agent_multi <task>
```

`agent_multi` は `enable_multi_agent` が `true` のときだけ動きます。Retriever には `agent_mcp` と同じ強い toolset を渡し、Reader / Writer / Critic / Final Writer は固定 flow で順番に実行します。

`enable_multi_agent_creation_tools` が `true` の場合、Retriever には Python 実行、file write、download などの作成系 tool も追加されます。グラフ、図、ファイル成果物の作成が必要な研究タスクではこの mode を使います。

## 目的

この Phase の目的は以下です。

- 研究作業を役割ごとに分ける。
- Retriever Agent を作る。
- Reader Agent を作る。
- Critic Agent を作る。
- Writer Agent を作る。
- Python などの作成系 tool を使ってグラフや成果物を作れるようにする。
- 最初は plugin 内の固定 flow として subagent role を実装する。
- うまく動いたら AstrBot SubAgent Orchestrator へ寄せる。

## なぜ Multi-Agent にするのか

1つの agent に全部やらせると、役割が混ざります。

```text
検索する
読む
比較する
批判する
書く
```

これを分けると、各 agent の prompt が短くなり、責任が明確になります。

ただし、agent が増えると遅くなります。まずは必要な場面だけ使います。

## まだ早い場合

以下が未完成なら Phase 5 以降に戻ります。

- `/research agent` が安定している。
- `research_search` tool が使える。
- citation が出る。
- agent の tool 呼び出しを log で追える。
- Web や MCP を使う場合でも allowlist がある。

## 変更するファイル

```text
main.py
agent_prompts.py
_conf_schema.json
```

新しく作る候補です。

```text
agents/retriever.py
agents/reader.py
agents/critic.py
agents/writer.py
```

## Step 1: 最初は固定 flow で作る

AstrBot の Multi-Agent 例では、SubAgent 自体を `FunctionTool` として作れます。ただし最初は plugin 内で固定 flow にした方が安定します。

考え方です。

```text
Retriever が tool_loop_agent で Research Pack を作る
Reader が Research Pack を読む
Writer が draft answer を書く
Critic が根拠不足や citation 不足を確認する
Final Writer が最終回答に修正する
```

AstrBot の SubAgent Orchestrator 設定に寄せるのは後でよいです。

## Step 2: Retriever Agent を作る

Retriever の役割は検索だけです。

やることです。

- query を受け取る。
- `research_search` を使う。
- 必要なら `agent_mcp` と同じ toolset で Web、Knowledge Base、ファイル、MCP を使う。
- 必要なら Python / file / download tool でグラフや成果物を作る。
- 関連 chunk を選ぶ。
- context pack を返す。

やらないことです。

- 最終回答を書く。
- 一般知識を補う。
- 保存、削除、書き込み、外部送信を勝手に行う。

返却例です。

```json
{
  "context": [
    {"doc_id": "doc_001", "chunk_id": "chunk_002", "content": "..."}
  ]
}
```

## Step 3: Reader Agent を作る

Reader の役割は資料を読むことです。

やることです。

- document または chunks を要約する。
- 重要な主張を抜き出す。
- 分からない点を出す。

やらないことです。

- 最終的な文章をきれいに書く。
- 外部検索する。

## Step 4: Critic Agent を作る

Critic の役割は検証です。

見る観点です。

- 回答が資料に基づいているか。
- citation があるか。
- 資料にないことを断定していないか。
- 複数資料の矛盾を見落としていないか。

Critic は最終回答を書かず、問題点を返します。

例です。

```text
問題点:
- doc_002/chunk_001 にない内容を断定している。
- Transformer と RNN の比較で RNN 側の根拠が不足している。
```

## Step 5: Writer Agent を作る

Writer の役割は成果物を作ることです。

やることです。

- 最終回答を書く。
- 比較表を作る。
- brief や outline を整える。
- Sources と Unknowns を付ける。

Writer は、Retriever や Reader の結果を使って書きます。

## Step 6: 最初の Multi-Agent flow

実装では固定の流れにしています。

```text
ユーザー task
Retriever: 関連 chunk を集める
Reader: chunk を要約する
Writer: 回答案を書く
Critic: 回答案を確認する
Writer: 必要なら修正して最終回答
```

完全に LLM に委任するより、最初は plugin 側で流れを決める方が安定します。

## Step 7: AstrBot SubAgent Orchestrator は後で使う

AstrBot には SubAgent Orchestrator があります。

設定で `transfer_to_*` tool を作り、Main LLM が subagent に委任できます。

ただし最初は plugin 内で固定 flow を作る方が理解しやすいです。動いたら、役割を AstrBot の SubAgent 設定に移すことを検討します。

## 動作確認

比較タスクを試します。

```text
/research agent_multi Transformer と RAG の違いを、保存済み資料だけで比較して
```

期待することです。

- Retriever が資料を集める。
- Writer が比較表を作る。
- Critic が根拠不足を指摘する。
- 最終回答に参考文献と Unknowns がある。

`show_multi_agent_trace` を `true` にすると、Retriever / Reader / Draft / Critique の中間結果も出力します。

## よくある失敗

### 遅すぎる

agent 数を減らします。最初は Retriever + Writer だけでもよいです。

### agent 同士で同じ検索を繰り返す

Retriever の結果を次の agent に渡し、各 agent が勝手に search しないようにします。

### Critic が厳しすぎて回答が進まない

Critic は問題点だけを短く返すようにします。

### 役割が混ざる

各 agent の prompt に「やらないこと」を書きます。

## この Phase の完了条件

- Retriever、Reader、Critic、Writer の役割が文書化されている。
- Retriever / Reader / Writer / Critic / Final Writer の flow が動く。
- Critic が根拠不足を指摘できる。
- Multi-Agent mode は通常 `/research agent` と分かれている。
- 単一 agent より複雑な比較や整理で役立つ。

## 実装例

最初は完全な自律 Multi-Agent ではなく、plugin 側で固定 flow を組む方が安定します。

### agent_prompts.py

実装では以下の prompt builder を使います。

```text
build_multi_retriever_prompt
build_multi_reader_prompt
build_multi_writer_prompt
build_multi_critic_prompt
build_multi_final_prompt
```

簡略化した例です。

```python
def build_reader_prompt(task: str, context_blocks: str) -> str:
    # Reader extracts claims and unknowns; it does not write the final answer.
    return f"""以下の資料を読み、ユーザー task に関係する主張を抽出してください。
最終回答は書かないでください。

Task:
{task}

Context:
{context_blocks}

出力:
Claims:
- ... [doc_id/chunk_id]

Unknowns:
- ...
"""


def build_writer_prompt(task: str, reader_notes: str) -> str:
    # Writer creates the user-facing output from prepared notes.
    return f"""以下の Reader notes に基づいて、ユーザーに返す最終回答を書いてください。
根拠 citation を残してください。

Task:
{task}

Reader notes:
{reader_notes}

出力:
Answer:
...

Sources:
- ...

Unknowns:
- ...
"""


def build_critic_prompt(task: str, draft_answer: str, context_blocks: str) -> str:
    # Critic only checks grounding problems and missing citations.
    return f"""次の draft answer を検証してください。
資料にない断定、citation 不足、矛盾の見落としだけを短く指摘してください。

Task:
{task}

Draft answer:
{draft_answer}

Context:
{context_blocks}

Problems:
- ...
"""
```

### 固定 flow

実装では Retriever だけ `tool_loop_agent()` を使い、`agent_mcp` と同じ強い toolset で Research Pack を作ります。その後、Reader / Writer / Critic / Final Writer は `llm_generate()` で固定順に実行します。

```python
async def run_simple_multi_agent(self, event, task: str) -> str:
    # Fixed flow is easier to debug than fully autonomous agent delegation.
    provider_id = await self.context.get_current_chat_provider_id(
        umo=event.unified_msg_origin
    )
    tools = self._get_mcp_research_tool_set()

    retriever_resp = await self.context.tool_loop_agent(
        event=event,
        chat_provider_id=provider_id,
        prompt=build_multi_retriever_prompt(task),
        system_prompt=build_mcp_research_agent_system_prompt(),
        tools=tools,
        max_steps=int(self.config.get("multi_agent_retriever_max_steps", 12)),
        tool_call_timeout=int(self.config.get("agent_tool_call_timeout", 60)),
    )
    research_pack = retriever_resp.completion_text if retriever_resp else ""

    reader_resp = await self.context.llm_generate(
        chat_provider_id=provider_id,
        prompt=build_multi_reader_prompt(task, research_pack),
    )
    reader_notes = reader_resp.completion_text if reader_resp else ""

    writer_resp = await self.context.llm_generate(
        chat_provider_id=provider_id,
        prompt=build_multi_writer_prompt(task, reader_notes),
    )
    draft = writer_resp.completion_text if writer_resp else ""

    critic_resp = await self.context.llm_generate(
        chat_provider_id=provider_id,
        prompt=build_multi_critic_prompt(task, draft, research_pack),
    )
    critique = critic_resp.completion_text if critic_resp else ""

    final_resp = await self.context.llm_generate(
        chat_provider_id=provider_id,
        prompt=build_multi_final_prompt(task, draft, critique, research_pack),
    )
    return final_resp.completion_text if final_resp else draft
```

### /research agent_multi

```python
@research_group.command("agent_multi")
async def research_agent_multi(self, event: AstrMessageEvent, task: str = ""):
    # Multi-agent mode is separate because it is slower and more expensive.
    task = self._extract_research_tail(event) or task.strip()
    if not task:
        yield event.plain_result("agent_multi に依頼する内容を入力してください。")
        return

    # 実装では enable_multi_agent を確認し、Retriever/Reader/Writer/Critic/Final Writer を固定順に実行します。
```
