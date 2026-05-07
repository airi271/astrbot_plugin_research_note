# 05 LLM Answer: 資料を LLM に渡して回答する

このステップでは、検索した資料を LLM に渡して、資料に基づく回答を返します。

先に読むと理解しやすい補助資料です。

- `../concepts/02_astrbot_plugin_terms.md`: Provider、LLMResponse、Context。
- `../concepts/03_yield_async_event.md`: `await` と非同期処理。
- `../concepts/04_rag_terms.md`: RAG、prompt、grounding、hallucination。

## 目的

`/research ask <question>` を根拠付きの最小QAにします。

流れは以下です。

```text
質問を受け取る
JSON から資料を読む
関連資料を検索する
資料と質問をプロンプトにまとめる
LLM に渡す
回答と使用資料を返す
```

## 変更するファイル

```text
main.py
```

## LLM 呼び出しの基本

AstrBot では、現在の会話で使っている LLM provider を取得してから `llm_generate` を呼べます。

```python
provider_id = await self.context.get_current_chat_provider_id(
    umo=event.unified_msg_origin
)
llm_resp = await self.context.llm_generate(
    chat_provider_id=provider_id,
    prompt=prompt,
)
```

`llm_resp.completion_text` に回答テキストが入ります。

## プロンプトを作る関数

まず資料と質問からプロンプトを作ります。

```python
def _build_answer_prompt(self, question: str, notes: list[dict]) -> str:
    note_blocks = []
    for note in notes:
        content = str(note.get("content", ""))[:1200]
        note_blocks.append(f"[{note['id']}]\n{content}")

    sources = "\n\n".join(note_blocks)
    return f"""あなたは研究補助AIです。
以下の資料だけを根拠にして、ユーザーの質問に日本語で答えてください。
資料に書かれていないことは、推測せず「資料からは分かりません」と答えてください。
回答の最後に、使用した資料IDを短く示してください。

資料:
{sources}

質問:
{question}
"""
```

ポイントは以下です。

- 「資料だけを根拠に」と明示する。
- 「分からない」と答える条件を書く。
- 資料IDを含める。
- 長すぎる資料は切り詰める。

## ask を LLM 対応にする

```python
@research_group.command("ask")
async def research_ask(self, event: AstrMessageEvent, question: str):
    """資料に基づいて質問します。"""
    question = question.strip()
    if not question:
        yield event.plain_result("質問を入力してください。")
        return

    notes = self._load_notes()
    if not notes:
        yield event.plain_result("保存済み資料がありません。先に /research add で資料を追加してください。")
        return

    matched_notes = self._search_notes(question, notes, top_k=3)
    if not matched_notes:
        yield event.plain_result("関連する資料が見つかりませんでした。")
        return

    prompt = self._build_answer_prompt(question, matched_notes)

    provider_id = await self.context.get_current_chat_provider_id(
        umo=event.unified_msg_origin
    )
    if not provider_id:
        yield event.plain_result("利用可能な LLM provider が見つかりません。")
        return

    llm_resp = await self.context.llm_generate(
        chat_provider_id=provider_id,
        prompt=prompt,
    )

    answer = llm_resp.completion_text if llm_resp else "回答を生成できませんでした。"
    source_ids = ", ".join(note["id"] for note in matched_notes)
    yield event.plain_result(f"{answer}\n\n使用資料: {source_ids}")
```

## 動作確認

資料を追加します。

```text
/research add Transformer は attention mechanism を使い、入力系列内の重要な要素に重みを付けて処理するモデルです。
```

質問します。

```text
/research ask Transformer は何を使いますか？
```

期待する回答です。

```text
Transformer は attention mechanism を使います。

使用資料: note_001
```

文章は LLM によって変わります。重要なのは、登録資料に基づいて答えていることです。

## よくある失敗

### LLM provider が見つからない

AstrBot 側で LLM provider が設定されているか確認します。

### 回答が資料にないことまで言う

プロンプトを強くします。

```text
資料に明示されていない内容は、絶対に補完しないでください。
```

### プロンプトが長すぎる

資料を切り詰めます。

```python
content = content[:1200]
```

後で `max_note_chars` として設定化します。

## このステップの完了条件

- `/research ask <question>` が LLM 回答を返す。
- 回答に使用資料 ID が出る。
- 資料がない場合、関連資料がない場合、LLM provider がない場合のメッセージがある。
- 最小の根拠付き QA として使える。

## コードを詳しく読む

LLM 回答の中心はこの流れです。

```python
prompt = self._build_answer_prompt(question, matched_notes)
provider_id = await self.context.get_current_chat_provider_id(
    umo=event.unified_msg_origin
)
llm_resp = await self.context.llm_generate(
    chat_provider_id=provider_id,
    prompt=prompt,
)
answer = llm_resp.completion_text
```

1つずつ見ます。

```python
prompt = self._build_answer_prompt(question, matched_notes)
```

質問と関連資料を使って、LLM に渡す長い指示文を作っています。

```python
provider_id = await self.context.get_current_chat_provider_id(
    umo=event.unified_msg_origin
)
```

今の会話で使われている LLM provider の ID を取得しています。`umo` は unified message origin の略で、会話を識別する情報です。

```python
llm_resp = await self.context.llm_generate(...)
```

AstrBot 経由で LLM にリクエストしています。`await` が付いているのは、LLM の回答には時間がかかるからです。

```python
answer = llm_resp.completion_text
```

LLM の返答テキストを取り出しています。

## 周辺知識: await とは何か

`await` は「時間がかかる処理の完了を待つ」という意味です。

LLM 呼び出し、ネットワーク通信、ファイル操作、データベース処理などは時間がかかることがあります。

```python
llm_resp = await self.context.llm_generate(...)
```

これは「LLM の回答が返るまで待ち、返ってきたら `llm_resp` に入れる」という意味です。

`await` を使う関数は、基本的に `async def` で定義されている必要があります。

## 周辺知識: プロンプト設計

RAG では、検索よりプロンプトが重要になることがあります。

悪いプロンプトです。

```text
以下を参考に答えて。
```

これだと、LLM が資料にないことを勝手に補う可能性があります。

良いプロンプトです。

```text
以下の資料だけを根拠にして答えてください。
資料に書かれていないことは「資料からは分かりません」と答えてください。
```

これにより、「資料に基づく回答」に近づきます。

## 周辺知識: RAG の責任分担

RAG は Retrieval Augmented Generation の略です。

Research Note では以下の対応になります。

```text
Retrieval: JSON から関連資料を検索する
Augmented: 検索結果をプロンプトに追加する
Generation: LLM が回答を生成する
```

回答が悪いときは、この3つのどこが悪いかを分けて考えます。

## LLM に渡しているものを確認する

開発中は、実際に作られた `prompt` をログに出すと理解が深まります。

```python
logger.info(prompt)
```

ただし、資料に個人情報や秘密情報が含まれる場合、ログに出すのは危険です。学習中のテストデータだけにします。

## 開発者の考え方

LLM は魔法ではありません。LLM に良い回答をさせるには、良い材料と良い指示が必要です。

Research Note では、開発者の仕事は以下です。

- 必要な資料を選ぶ。
- 不要な資料を入れすぎない。
- 資料の境界を分かりやすくする。
- 資料にないことを答えないよう指示する。
- 回答の根拠をユーザーに示す。

この考え方ができると、単なる API 呼び出しではなく、研究補助ツールとして設計できるようになります。
