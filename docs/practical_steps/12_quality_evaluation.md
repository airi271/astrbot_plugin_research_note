# 12 Quality Evaluation: 検索と回答品質を評価する

この Phase では、Research Note が研究補助として信頼できるかを測る仕組みを作ります。

機能が増えるほど、「なんとなく良さそう」では危険です。検索変更や prompt 変更で品質が上がったのか下がったのかを確認できるようにします。

## 目的

この Phase の目的は以下です。

- 小さな評価データセットを作る。
- 質問、期待 source、期待回答の要点を保存する。
- keyword、embedding、hybrid の検索結果を比較する。
- citation の正しさを確認しやすくする。
- hallucination しやすい質問をテストする。

## なぜ評価が必要か

RAG は、コードが動いても品質が良いとは限りません。

よくある問題です。

- 検索結果が関係ない。
- 正しい chunk が検索されない。
- LLM が source にないことを言う。
- citation が間違っている。
- prompt を変えたら前より悪くなる。

評価データがあると、変更の良し悪しを比べられます。

## まだ早い場合

以下が未完成なら Phase 3 以降に戻ります。

- `/research search` がある。
- citation がある。
- source に `doc_id/chunk_id` が出る。
- 複数の検索方式がある、または比較したい検索方式がある。

## 変更するファイル

新しく作る候補です。

```text
evals/README.md
evals/dataset.json
evals/run_eval.py
evals/manual_checklist.md
```

plugin 本体に入れず、まずは開発用ファイルとして置くのが安全です。

## Step 1: 評価データセットを作る

最初は5問で十分です。

例です。

```json
[
  {
    "id": "q001",
    "question": "Transformer は何を使いますか？",
    "expected_sources": ["doc_001/chunk_001"],
    "answer_points": ["self-attention または attention を使う"],
    "must_not_include": ["CNN が中心"]
  }
]
```

最初から自動採点を完璧にしなくてよいです。手動確認しやすい形を作ることが大事です。

## Step 2: 検索評価を作る

LLM 回答の前に、検索だけ評価します。

見るものです。

- top_1 に期待 source があるか。
- top_3 に期待 source があるか。
- score が低すぎないか。
- 関係ない chunk が混ざっていないか。

出力例です。

```text
q001: PASS top_1=doc_001/chunk_001
q002: FAIL expected=doc_003/chunk_002 got=doc_002/chunk_001
```

検索評価は LLM を使わないので安定しています。

## Step 3: 回答評価を作る

回答評価は難しいです。

最初は半自動でよいです。

見るものです。

- citation があるか。
- expected_sources が Sources に含まれるか。
- answer_points の内容が含まれるか。
- must_not_include が含まれないか。
- Unknowns が必要な質問で出るか。

## Step 4: hallucination 質問を入れる

資料に答えがない質問を入れます。

例です。

```json
{
  "id": "q_hallucination_001",
  "question": "この資料の実験で使われた GPU は何ですか？",
  "expected_sources": [],
  "answer_points": ["資料からは分かりません"],
  "must_not_include": ["A100", "V100", "RTX"]
}
```

研究補助では、分からないことを分からないと言えるかが重要です。

## Step 5: 検索方式を比較する

keyword、embedding、hybrid を比べます。

出力例です。

```text
query: 外部資料を使って回答する方法
keyword top_3: doc_002/chunk_001, ...
embedding top_3: doc_004/chunk_002, ...
hybrid top_3: doc_002/chunk_001, doc_004/chunk_002, ...
```

これを見ると、重みをどう調整すべきか分かります。

## Step 6: manual checklist を作る

自動評価だけでは足りません。

手動チェック項目です。

- 回答は資料に基づいているか。
- citation は本文の近くにあるか。
- Sources は実際に使った資料か。
- Unknowns は適切か。
- Web情報と保存済み資料が混ざっていないか。
- 回答が長すぎないか。

## Step 7: regression を見る

prompt や search を変える前後で評価を実行します。

```text
変更前: q001-q005 すべて PASS
変更後: q003 が FAIL
```

こうなったら、変更が悪影響を出した可能性があります。

## 動作確認

評価データを作ります。

```text
evals/dataset.json
```

検索評価を実行します。

```bash
python evals/run_eval.py --mode search
```

回答評価を実行します。

```bash
python evals/run_eval.py --mode answer
```

最初は script がなくても、手動で `/research search` と `/research ask` を実行し、結果を表にしてもよいです。

## よくある失敗

### 評価データを大きくしすぎる

最初は5問で十分です。続けられる量にします。

### 自動採点を完璧にしようとする

LLM回答の自動採点は難しいです。まず source と禁止語の確認だけでよいです。

### 良い回答なのに FAIL になる

評価データの `answer_points` が狭すぎる可能性があります。表現ゆれを許します。

### 検索評価と回答評価を混ぜる

まず検索だけ評価します。検索が悪いと回答も悪くなります。

## この Phase の完了条件

- `evals/dataset.json` がある。
- 代表的な質問が5件以上ある。
- hallucination 質問がある。
- 検索結果を比較できる。
- citation の手動チェック項目がある。
- prompt や search 変更前後で regression を確認できる。
