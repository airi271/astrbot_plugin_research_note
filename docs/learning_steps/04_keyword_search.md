# 04 Keyword Search: 関連資料を探す

このステップでは、保存した資料から質問に関連するものを選びます。

先に読むと理解しやすい補助資料です。

- `../concepts/01_python_for_plugins.md`: 関数、リスト、辞書、並び替えの読み方。
- `../concepts/04_rag_terms.md`: retrieval、top_k、chunk。
- `../concepts/05_developer_workflow.md`: 検索と回答の問題を分ける考え方。

## 目的

`/research ask <question>` を送ったとき、LLM を呼ぶ前に関連資料を表示できる状態を作ります。

## 変更するファイル

```text
main.py
```

## なぜ最初はキーワード検索なのか

embedding 検索は便利ですが、最初は以下の理由で後回しにします。

- embedding provider の設定が必要。
- ベクトルの意味を理解する必要がある。
- 保存形式が少し複雑になる。
- エラー原因が増える。

最初はキーワード検索で「検索してプロンプトに渡す」という流れを理解する方が早いです。

## 検索の考え方

単純な検索は以下です。

1. 質問を単語に分ける。
2. 各資料に単語が含まれているか調べる。
3. 含まれている数をスコアにする。
4. スコアが高い順に並べる。
5. 上位3件だけ使う。

## 単語に分ける関数

日本語は単語分割が難しいので、最初は簡単にします。

```python
def _tokenize(self, text: str) -> list[str]:
    normalized = text.lower().replace("\n", " ")
    tokens = []
    for token in normalized.split():
        token = token.strip(".,!?;:()[]{}<>。、！？「」『』（）")
        if token:
            tokens.append(token)
    return tokens
```

日本語の文章で空白がない場合は弱いですが、最初の学習用としては十分です。後で改善します。

## 資料にスコアを付ける

```python
def _score_note(self, question: str, note: dict) -> int:
    tokens = self._tokenize(question)
    content = str(note.get("content", "")).lower()
    score = 0
    for token in tokens:
        if token in content:
            score += 1
    return score
```

## 上位資料を選ぶ

```python
def _search_notes(self, question: str, notes: list[dict], top_k: int = 3) -> list[dict]:
    scored = []
    for note in notes:
        score = self._score_note(question, note)
        if score > 0:
            scored.append((score, note))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [note for score, note in scored[:top_k]]
```

## ask で検索結果を返す

この段階では LLM を呼ばず、検索結果を表示します。

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

    lines = ["関連資料:"]
    for note in matched_notes:
        preview = note["content"].replace("\n", " ")[:120]
        lines.append(f"- {note['id']}: {preview}")

    yield event.plain_result("\n".join(lines))
```

## 動作確認

資料を追加します。

```text
/research add Transformer は attention mechanism を使う自然言語処理モデルです。
/research add RNN は系列データを順番に処理する古いニューラルネットワークです。
```

質問します。

```text
/research ask attention とは？
```

期待する結果は、Transformer の資料が関連資料として出ることです。

## 日本語検索の注意

以下のような日本語だけの質問では、単純な空白分割が弱いです。

```text
/research ask 注意機構とは？
```

対策は後で追加できます。

- 文字単位の部分一致を使う。
- 2文字や3文字の n-gram を使う。
- embedding 検索を使う。

最初は英単語や専門用語を含めて試すと動作確認しやすいです。

## このステップの完了条件

- `/research ask <question>` で関連資料が表示される。
- 関連資料がない場合のメッセージがある。
- 資料が空の場合のメッセージがある。
- LLM を呼ばなくても検索だけ確認できる。

## コードを詳しく読む

検索は、難しく見えても基本は「点数を付けて並べる」です。

```python
def _score_note(self, question: str, note: dict) -> int:
    tokens = self._tokenize(question)
    content = str(note.get("content", "")).lower()
    score = 0
    for token in tokens:
        if token in content:
            score += 1
    return score
```

この関数は、1つの資料に対して「質問とどれくらい関係がありそうか」を点数化します。

```python
tokens = self._tokenize(question)
```

質問を検索用の単語リストに変えます。

```python
content = str(note.get("content", "")).lower()
```

資料本文を取り出します。`note.get("content", "")` は、`content` がなければ空文字を返します。`str(...)` は念のため文字列に変換しています。

```python
if token in content:
    score += 1
```

質問の単語が資料本文に含まれていれば、点数を1増やします。

## 並び替えのコード

```python
scored.sort(key=lambda item: item[0], reverse=True)
```

`scored` は以下のようなリストです。

```python
[
    (2, note_a),
    (1, note_b),
    (5, note_c),
]
```

`item[0]` はスコアです。`reverse=True` は大きい順に並べるという意味です。

並べ替えると、以下のようになります。

```python
[
    (5, note_c),
    (2, note_a),
    (1, note_b),
]
```

最後に資料だけ取り出します。

```python
return [note for score, note in scored[:top_k]]
```

これはリスト内包表記です。`scored[:top_k]` で上位だけ取り、`note` だけのリストにしています。

## 周辺知識: 検索には段階がある

検索は、最初から完璧にしません。実務でも段階があります。

1. 完全一致検索。
2. キーワード部分一致検索。
3. スコア付き検索。
4. embedding 検索。
5. embedding 検索 + rerank。
6. メタデータや引用付き検索。

今作っているのは 3 の「スコア付き検索」です。簡単ですが、RAG の仕組みを理解するには十分です。

## 周辺知識: 日本語検索が難しい理由

英語は空白で単語が分かれています。

```text
Transformer uses attention mechanism
```

日本語は空白がありません。

```text
Transformerは注意機構を使います
```

そのため、単純な `split()` だけでは日本語検索は弱いです。

ただし、研究資料には英単語、専門用語、論文タイトル、手法名が混ざることが多いので、最初の動作確認には使えます。

## 改善案を知っておく

後で改善するなら、以下があります。

- 英数字だけでなく日本語の2文字単位で検索する。
- タイトルと本文でスコアの重みを変える。
- 出現回数を数える。
- 最近追加した資料を少し優先する。
- embedding 検索にする。

ただし、今は実装しません。まずはシンプルな検索を完成させます。

## 開発者の考え方

検索機能では、いきなり LLM に渡さず、まず検索結果だけ表示するのが大事です。

理由は、回答が悪いときに原因を分けられるからです。

```text
検索結果が悪い: search の問題
検索結果は良いが回答が悪い: prompt の問題
検索結果も回答も良いが表示が悪い: output の問題
```

本物の開発では、このように問題を分解して調べます。
