# 09 Multi-Agent: 研究作業を分担する

この Phase では、研究補助を複数の専門 agent に分けます。

最初から Multi-Agent にすると複雑すぎます。ここまでに検索、citation、tool、agent mode が安定してから進みます。

## 目的

この Phase の目的は以下です。

- 研究作業を役割ごとに分ける。
- Retriever Agent を作る。
- Reader Agent を作る。
- Critic Agent を作る。
- Writer Agent を作る。
- 最初は plugin 内の `FunctionTool` として subagent を実装する。
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
tools/*.py
agent_prompts.py
```

新しく作る候補です。

```text
agents/retriever.py
agents/reader.py
agents/critic.py
agents/writer.py
```

## Step 1: 最初は agent-as-tool で作る

AstrBot の Multi-Agent 例では、SubAgent 自体を `FunctionTool` として作れます。

考え方です。

```text
Main agent が RetrieverAgentTool を呼ぶ
RetrieverAgentTool 内で tool_loop_agent を呼ぶ
結果を Main agent に返す
```

最初はこれで十分です。AstrBot の SubAgent Orchestrator 設定に寄せるのは後でよいです。

## Step 2: Retriever Agent を作る

Retriever の役割は検索だけです。

やることです。

- query を受け取る。
- `research_search` を使う。
- 関連 chunk を選ぶ。
- context pack を返す。

やらないことです。

- 最終回答を書く。
- 一般知識を補う。
- Web を勝手に見る。

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

最初は固定の流れで十分です。

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

ただし最初は plugin 内で agent-as-tool を作る方が理解しやすいです。動いたら、役割を AstrBot の SubAgent 設定に移すことを検討します。

## 動作確認

比較タスクを試します。

```text
/research agent_multi Transformer と RAG の違いを、保存済み資料だけで比較して
```

期待することです。

- Retriever が資料を集める。
- Writer が比較表を作る。
- Critic が根拠不足を指摘する。
- 最終回答に Sources と Unknowns がある。

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
- 少なくとも Retriever + Writer の flow が動く。
- Critic が根拠不足を指摘できる。
- Multi-Agent mode は通常 `/research agent` と分かれている。
- 単一 agent より複雑な比較や整理で役立つ。

## 実装例

最初は完全な自律 Multi-Agent ではなく、plugin 側で固定 flow を組む方が安定します。

### agent_prompts.py

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

```python
async def run_simple_multi_agent(self, event, task: str) -> str:
    # Fixed flow is easier to debug than fully autonomous agent delegation.
    results = await search_research_store(
        store=self.store,
        query=task,
        top_k=int(self.config.get("top_k", 5)),
        embedding_provider=self._get_embedding_provider(),
    )
    context_blocks = format_context_blocks(results)

    provider_id = await self.context.get_current_chat_provider_id(
        umo=event.unified_msg_origin
    )

    reader_resp = await self.context.llm_generate(
        chat_provider_id=provider_id,
        prompt=build_reader_prompt(task, context_blocks),
    )
    reader_notes = reader_resp.completion_text if reader_resp else ""

    writer_resp = await self.context.llm_generate(
        chat_provider_id=provider_id,
        prompt=build_writer_prompt(task, reader_notes),
    )
    draft = writer_resp.completion_text if writer_resp else ""

    critic_resp = await self.context.llm_generate(
        chat_provider_id=provider_id,
        prompt=build_critic_prompt(task, draft, context_blocks),
    )
    critique = critic_resp.completion_text if critic_resp else ""

    final_resp = await self.context.llm_generate(
        chat_provider_id=provider_id,
        prompt=f"""次の draft と critique を使って最終回答を改善してください。

Draft:
{draft}

Critique:
{critique}
""",
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

    try:
        answer = await self.run_simple_multi_agent(event, task)
    except Exception:
        logger.error("Multi-agent flow failed.", exc_info=True)
        yield event.plain_result("Multi-agent flow の実行に失敗しました。")
        return

    yield event.plain_result(answer)
```
