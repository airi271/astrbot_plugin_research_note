# 08 Embedding Next: embedding 検索へ進む

このステップは、JSON 保存とキーワード検索の最小版が完成してから進みます。

先に読むと理解しやすい補助資料です。

- `../concepts/02_astrbot_plugin_terms.md`: embedding provider、Provider。
- `../concepts/03_yield_async_event.md`: embedding API を `await` する理由。
- `../concepts/04_rag_terms.md`: embedding、vector、cosine similarity、vector database。

## 目的

キーワード一致ではなく、意味の近さで資料を検索できるようにします。

## まだ進まなくてよい条件

以下が未完成なら、このステップはまだ早いです。

- `/research add` が安定して動く。
- `/research list` が安定して動く。
- `/research ask` がキーワード検索で動く。
- LLM 回答が返る。
- エラー時のログを読める。

## embedding とは

embedding は、文章を数字のリストに変換したものです。

例です。

```text
"Transformer は attention を使う"
```

が、以下のような数字になります。

```text
[0.012, -0.392, 0.884, ...]
```

意味が近い文章は、数字の並びも近くなります。これを使うと、同じ単語が入っていなくても関連資料を探せます。

## Mnemosyne で見る場所

以下を読みます。

```text
/home/ayaka/codding/astrbotpj/AstrBot/data/plugins/astrbot_plugin_mnemosyne/main.py
/home/ayaka/codding/astrbotpj/AstrBot/data/plugins/astrbot_plugin_mnemosyne/core/memory_operations.py
```

見るポイントです。

- `embedding_provider_id`
- `self.context.get_all_embedding_providers()`
- `embedding_provider.get_embedding(...)`
- 検索前に query を embedding 化している部分。

## 最初の実装方針

最初から Milvus は使いません。JSON に embedding も保存します。

資料の保存形式を以下のようにします。

```json
{
  "id": "note_001",
  "content": "資料本文",
  "created_at": "2026-05-02T12:00:00",
  "embedding": [0.01, -0.03, 0.22]
}
```

## embedding provider を取得する

最小版では、AstrBot に設定済みの最初の embedding provider を使います。

```python
def _get_embedding_provider(self):
    providers = self.context.get_all_embedding_providers()
    if not providers:
        return None
    return providers[0]
```

## 資料追加時に embedding を保存する

`/research add` の中で以下を行います。

```python
embedding = None
embedding_provider = self._get_embedding_provider()
if embedding_provider:
    embedding = await embedding_provider.get_embedding(content)
```

note に保存します。

```python
note = {
    "id": self._next_note_id(notes),
    "content": content,
    "created_at": datetime.now().isoformat(timespec="seconds"),
    "embedding": embedding,
}
```

## コサイン類似度

ベクトル同士の近さを測る代表的な方法です。

```python
import math


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
```

## 質問時に embedding 検索する

```python
embedding_provider = self._get_embedding_provider()
if not embedding_provider:
    matched_notes = search_notes(question, notes, top_k=top_k)
else:
    query_embedding = await embedding_provider.get_embedding(question)
    matched_notes = search_notes_by_embedding(query_embedding, notes, top_k=top_k)
```

embedding provider がない場合は、キーワード検索に戻すと安全です。

## embedding 検索関数

```python
def search_notes_by_embedding(
    query_embedding: list[float],
    notes: list[dict],
    top_k: int = 3,
) -> list[dict]:
    scored = []
    for note in notes:
        note_embedding = note.get("embedding")
        if not isinstance(note_embedding, list):
            continue
        score = cosine_similarity(query_embedding, note_embedding)
        if score > 0:
            scored.append((score, note))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [note for score, note in scored[:top_k]]
```

## 既存資料の問題

embedding 対応前に保存した資料には `embedding` がありません。

対応案は2つです。

- 古い資料はキーワード検索で使う。
- `/research reindex` コマンドを作って embedding を作り直す。

最初は、embedding がない資料はスキップしてよいです。後で `reindex` を作ります。

## 将来 Milvus に進む条件

Milvus は以下が必要になってからでよいです。

- 資料数が多くなった。
- JSON の読み書きが遅くなった。
- embedding 検索を本格的にしたい。
- 削除や更新を安全にしたい。

Milvus に進むときは、Mnemosyne の以下を読みます。

- `memory_manager/vector_db_base.py`
- `memory_manager/vector_db/milvus_manager.py`
- `core/initialization.py`

## このステップの完了条件

- embedding provider を取得できる。
- `/research add` で embedding を保存できる。
- `/research ask` で質問 embedding を作れる。
- コサイン類似度で資料を選べる。
- embedding provider がない場合はキーワード検索に戻れる。

## コードを詳しく読む

embedding provider を取る関数です。

```python
def _get_embedding_provider(self):
    providers = self.context.get_all_embedding_providers()
    if not providers:
        return None
    return providers[0]
```

```python
providers = self.context.get_all_embedding_providers()
```

AstrBot に登録されている embedding provider の一覧を取得します。

```python
if not providers:
    return None
```

1つも設定されていない場合は `None` を返します。

```python
return providers[0]
```

最初の provider を使います。将来は `_conf_schema.json` で provider ID を選べるようにします。

## embedding を作るコード

```python
embedding = await embedding_provider.get_embedding(content)
```

`content` という文章を、数字のリストに変換しています。

LLM 呼び出しと同じく時間がかかる可能性があるため、`await` を使います。

## コサイン類似度を読む

```python
dot = sum(x * y for x, y in zip(a, b))
```

2つのベクトルの同じ位置の数字を掛け算して足しています。

```python
norm_a = math.sqrt(sum(x * x for x in a))
norm_b = math.sqrt(sum(y * y for y in b))
```

それぞれのベクトルの長さを計算しています。

```python
return dot / (norm_a * norm_b)
```

向きの近さを返します。値が大きいほど意味が近いと考えます。

数学が完全に分からなくても、最初はこう覚えて大丈夫です。

```text
cosine_similarity は、2つの文章ベクトルがどれくらい似ているかを返す関数
```

## 周辺知識: キーワード検索と embedding 検索の違い

キーワード検索は、同じ単語が含まれるかを見ます。

```text
質問: attention とは？
資料: Transformer は attention を使う
```

これは見つかりやすいです。

しかし、以下は難しいです。

```text
質問: 重要な単語に重みを付ける仕組みは？
資料: Transformer は attention を使う
```

同じ単語が少ないため、キーワード検索では弱いです。

embedding 検索は意味の近さを見るので、このような質問に強くなります。

## 周辺知識: なぜ最初から Milvus にしないのか

Milvus は本格的なベクトルDBです。便利ですが、最初は以下の難しさがあります。

- 接続設定が必要。
- collection の作成が必要。
- embedding 次元を合わせる必要がある。
- 起動や接続エラーが増える。
- データ削除や migration を考える必要がある。

JSON に embedding を保存する方法なら、ベクトル検索の考え方だけを先に学べます。

## 周辺知識: fallback の重要性

embedding provider がないときに全部失敗するのは不便です。

```python
if not embedding_provider:
    matched_notes = search_notes(question, notes, top_k=top_k)
```

このように、キーワード検索へ戻れると使いやすくなります。

本物のアプリでは、外部サービスや設定が使えない場合に備えて fallback を用意することが多いです。

## 開発者の考え方

embedding は強力ですが、問題を増やす技術でもあります。

導入するときは、以下を確認します。

- 失敗したときに分かりやすいメッセージが出るか。
- 既存のキーワード検索を壊していないか。
- embedding がない古い資料をどう扱うか。
- 保存ファイルが大きくなりすぎないか。
- provider を変更したときに古い embedding を作り直す必要があるか。

技術を足すときは、便利さだけでなく運用も考えます。これが開発者として大事な視点です。
