# 10 Research Outputs: 研究成果物を出力する

この Phase では、単なる質問回答ではなく、研究ブリーフ、アウトライン、比較表、主張抽出などの成果物を作れるようにします。

研究補助プラグインの価値は「資料に基づいて考える」だけでなく、「資料に基づいて使えるノートを作る」ことです。

## 目的

この Phase の目的は以下です。

- `/research brief <topic>` を作る。
- `/research outline <topic>` を作る。
- `/research compare <query>` を作る。
- `/research claims <doc_id>` を作る。
- Markdown 出力を整える。
- すべての成果物に source を付ける。

## まだ早い場合

以下が未完成なら Phase 5 以前に戻ります。

- `/research ask` が citation 付きで答える。
- `/research search` で source を確認できる。
- `/research agent` が安定している。
- chunk 単位の根拠がある。

## 変更するファイル

```text
main.py
prompts.py
search.py
```

新しく作る候補です。

```text
output_prompts.py
formatters.py
```

## Step 1: 出力タイプを分ける

同じ質問でも、出力形式が違います。

```text
brief: 短い研究メモ
outline: 章立て
compare: 比較表
claims: 主張、根拠、限界の抽出
```

出力タイプごとに prompt を分けます。1つの巨大 prompt に全部入れない方が読みやすいです。

## Step 2: brief を作る

`/research brief <topic>` は短い研究ブリーフを作ります。

出力例です。

```text
# Brief: Attention Mechanism

## Summary
...

## Key Points
- ... [doc_001/chunk_002]

## Unknowns
- ...

## Sources
- doc_001/chunk_002: Transformer memo
```

brief は短く、読み返しやすいことが大事です。

## Step 3: outline を作る

`/research outline <topic>` は発表や文章の章立てを作ります。

出力例です。

```text
# Outline

1. Introduction
2. Background
3. Main Mechanism
4. Comparison
5. Limitations
6. Conclusion

Sources:
- ...
```

outline では、根拠がある章と根拠が足りない章を分けると便利です。

## Step 4: compare を作る

`/research compare <query>` は複数資料の比較表を作ります。

出力例です。

```text
| 観点 | Transformer | RNN | Source |
| --- | --- | --- | --- |
| 並列化 | しやすい | しにくい | doc_001/chunk_002 |
```

比較表では、source 列を必ず入れます。

## Step 5: claims を作る

`/research claims <doc_id>` は1つの資料から主張を抽出します。

出力例です。

```text
# Claims: doc_001

## Claims
- Transformer uses self-attention. [doc_001/chunk_001]

## Evidence
- ...

## Limitations
- 資料からは不明: 実験条件の詳細
```

claims は論文読みや資料整理に役立ちます。

## Step 6: 共通の source formatter を作る

毎回 source 表示を書くと重複します。

`formatters.py` にまとめます。

```python
def format_sources(results: list[dict]) -> str:
    ...
```

これを brief、outline、compare、claims で使います。

## Step 7: 保存済み資料だけか一般知識込みかを分ける

研究補助では、資料に基づく出力と一般知識込みの出力を混ぜない方がよいです。

最初は保存済み資料だけにします。

```text
この出力は保存済み資料だけに基づいています。
```

一般知識込みを許す場合は、設定や command で明示します。

```text
/research brief --allow-general <topic>
```

これは後回しでよいです。

## 動作確認

資料を複数追加します。

```text
/research add Transformer は self-attention を使います。
/research add RNN は系列を順番に処理します。
```

試します。

```text
/research brief attention
/research outline Transformer の説明
/research compare Transformer と RNN
/research claims doc_001
```

期待することです。

- Markdown として読みやすい。
- source がある。
- 資料にない点は Unknowns に出る。

## よくある失敗

### きれいだが根拠がない文章になる

prompt に source 必須と書きます。source がない項目は Unknowns に移すよう指示します。

### compare 表が崩れる

Markdown table は崩れやすいです。最初は bullet list でもよいです。

### claims が多すぎる

最大件数を設定します。例: `max_claims=10`。

## この Phase の完了条件

- `/research brief` が使える。
- `/research outline` が使える。
- `/research compare` が使える。
- `/research claims` が使える。
- すべての出力に source がある。
- Unknowns が表示される。

## 実装例

### formatters.py

source 表示は共通化します。

```python
def format_sources(results: list[dict]) -> str:
    # Deduplicate source lines while preserving order.
    seen = set()
    lines = []
    for result in results:
        chunk = result["chunk"]
        document = result["document"]
        source_id = f"{chunk.get('doc_id')}/{chunk.get('id')}"
        if source_id in seen:
            continue
        seen.add(source_id)
        lines.append(f"- {source_id}: {document.get('title', '')}")
    return "\n".join(lines)


def format_context_blocks(results: list[dict]) -> str:
    # Use compact source blocks for output-generation prompts.
    blocks = []
    for result in results:
        chunk = result["chunk"]
        document = result["document"]
        source_id = f"{chunk.get('doc_id')}/{chunk.get('id')}"
        blocks.append(f"[{source_id}] {document.get('title', '')}\n{chunk.get('content', '')}")
    return "\n\n".join(blocks)
```

### output_prompts.py

出力タイプごとに prompt を分けます。

```python
def build_brief_prompt(topic: str, context_blocks: str) -> str:
    # Brief is a short reusable research memo.
    return f"""保存済み資料だけに基づいて、短い研究ブリーフを Markdown で作ってください。
各 key point には [doc_id/chunk_id] citation を付けてください。
資料にない点は Unknowns に書いてください。

Topic:
{topic}

Sources:
{context_blocks}

Format:
# Brief: {topic}

## Summary

## Key Points

## Unknowns

## Sources
"""


def build_compare_prompt(query: str, context_blocks: str) -> str:
    # Compare should keep a Source column or source bullet for every claim.
    return f"""保存済み資料だけに基づいて比較表を作ってください。
根拠がない観点は Unknowns に移してください。

Query:
{query}

Sources:
{context_blocks}

Format:
| 観点 | A | B | Source |
| --- | --- | --- | --- |

Unknowns:
- ...
"""
```

### /research brief

```python
@research_group.command("brief")
async def research_brief(self, event: AstrMessageEvent, topic: str = ""):
    # Brief reuses retrieval, then asks the LLM for a structured Markdown output.
    topic = self._extract_research_tail(event) or topic.strip()
    if not topic:
        yield event.plain_result("brief の topic を入力してください。")
        return

    results = await search_research_store(
        store=self.store,
        query=topic,
        top_k=int(self.config.get("top_k", 5)),
        embedding_provider=self._get_embedding_provider(),
    )
    if not results:
        yield event.plain_result("関連する資料が見つかりませんでした。")
        return

    prompt = build_brief_prompt(topic, format_context_blocks(results))
    provider_id = await self.context.get_current_chat_provider_id(
        umo=event.unified_msg_origin
    )
    llm_resp = await self.context.llm_generate(chat_provider_id=provider_id, prompt=prompt)
    yield event.plain_result(llm_resp.completion_text if llm_resp else "brief を生成できませんでした。")
```

### /research claims

```python
@research_group.command("claims")
async def research_claims(self, event: AstrMessageEvent, doc_id: str = ""):
    # Claims extraction is useful for reading papers and long notes.
    doc_id = doc_id.strip()
    if not doc_id:
        yield event.plain_result("doc_id を入力してください。")
        return

    data = self.store.load_store()
    chunks = [chunk for chunk in data["chunks"] if chunk.get("doc_id") == doc_id]
    if not chunks:
        yield event.plain_result("指定された document の chunk が見つかりません。")
        return

    context_blocks = "\n\n".join(
        f"[{doc_id}/{chunk.get('id')}]\n{chunk.get('content', '')}" for chunk in chunks
    )
    prompt = f"""以下の資料から主要な主張を最大10件抽出してください。
各主張に citation を付け、限界や不明点も出してください。

{context_blocks}
"""
    provider_id = await self.context.get_current_chat_provider_id(
        umo=event.unified_msg_origin
    )
    llm_resp = await self.context.llm_generate(chat_provider_id=provider_id, prompt=prompt)
    yield event.plain_result(llm_resp.completion_text if llm_resp else "claims を生成できませんでした。")
```
