# RAG Terms

このファイルでは、根拠付き研究補助プラグインを作るために必要な RAG 関連用語を説明します。

## 根拠付き研究補助とは何か

ここで言う根拠付き研究補助とは、以下のような機能です。

- ユーザーが資料を入れる。
- AI がその資料を読んだように質問へ答える。
- 回答が資料に基づいている。
- できれば根拠や引用を示す。

Research Note の最小版では、これを小さく作ります。

## RAG

RAG は Retrieval Augmented Generation の略です。

日本語では「検索拡張生成」と訳されることがあります。

分解すると以下です。

```text
Retrieval: 関連情報を検索する
Augmented: 検索結果を LLM の入力に追加する
Generation: LLM が回答を生成する
```

Research Note では以下になります。

```text
Retrieval: JSON から関連資料を探す
Augmented: 関連資料をプロンプトに入れる
Generation: LLM が回答を書く
```

## プロンプト

プロンプトは、LLM に渡す指示文です。

例です。

```text
以下の資料だけを根拠にして、質問に答えてください。

資料:
...

質問:
...
```

LLM はプロンプトを見て回答します。つまり、プロンプトの書き方で回答品質が変わります。

## grounding

grounding は、回答を根拠に結びつけることです。

Research Note では「登録された資料に基づいて答える」ことを意味します。

良い grounding の指示です。

```text
資料に書かれていないことは、推測せず「資料からは分かりません」と答えてください。
```

## hallucination

hallucination は、LLM が事実ではないことを本当のように答える問題です。

RAG は hallucination を減らすために使われます。ただし、RAG を使っても完全にはなくなりません。

対策です。

- 関連資料だけを入れる。
- 資料にないことは答えないよう指示する。
- 使用資料 ID を表示する。
- 長すぎる資料を入れすぎない。

## chunk

chunk は、長い資料を小さく分けた単位です。

長い論文を丸ごと1件として保存すると、検索しにくくなります。

例です。

```text
論文A chunk 1: 要旨
論文A chunk 2: 方法
論文A chunk 3: 結果
```

実用的な研究補助に近づけるなら、将来 chunk 化が重要になります。

## top_k

`top_k` は、検索結果の上位何件を使うかです。

```python
top_k = 3
```

これは「関連資料を3件使う」という意味です。

`top_k` が小さすぎると、必要な資料が入らないことがあります。

`top_k` が大きすぎると、関係ない資料まで入って回答がぼやけます。

最初は 3 が分かりやすいです。

## embedding

embedding は、文章を数字のベクトルに変換したものです。

例です。

```text
"Transformer は attention を使う"
```

が、以下のようになります。

```text
[0.01, -0.24, 0.88, ...]
```

意味が近い文章は、embedding も近くなります。

## vector

vector は数字のリストです。

```python
[0.01, -0.24, 0.88]
```

embedding は vector の一種です。

## cosine similarity

cosine similarity は、2つのベクトルがどれくらい似ているかを測る方法です。

値が大きいほど似ています。

Research Note では、質問の embedding と資料の embedding を比較するために使います。

## vector database

ベクトルDBは、embedding を保存して高速に検索するためのデータベースです。

Mnemosyne は Milvus を使っています。

Research Note では、最初は JSON で十分です。資料が増えてから Milvus を検討します。

## rerank

rerank は、一度検索した結果をさらに並べ替えることです。

たとえば embedding 検索で10件取り、LLM や別のモデルで上位3件に並べ替える、という方法があります。

最初は不要です。

## source / citation

source は回答の根拠資料です。

citation は引用です。

Research Note の最小版では、まず資料 ID を出すだけで十分です。

```text
使用資料: note_001, note_003
```

将来は、該当箇所の引用やページ番号を出せると、より実用的な研究補助になります。

## 最初に覚えるべき用語

優先度が高いものです。

1. RAG。
2. prompt。
3. retrieval。
4. top_k。
5. grounding。
6. hallucination。
7. chunk。
8. embedding。
9. vector。
10. vector database。
