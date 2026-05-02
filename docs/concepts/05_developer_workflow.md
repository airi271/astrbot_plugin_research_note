# Developer Workflow

このファイルでは、本物の開発者に近づくための作業方法を説明します。

## 開発者は何をしているのか

開発者は、ただコードを書く人ではありません。

実際には以下を繰り返します。

```text
理解する
小さく設計する
少し書く
動かす
壊れた原因を読む
直す
整理する
記録する
```

Research Note の開発でも同じです。

## コードを読む順番

知らないコードを読むとき、上から全部読む必要はありません。

おすすめ順です。

1. ファイル名を見る。
2. import を見る。
3. クラス名を見る。
4. `__init__` を見る。
5. デコレータ付き関数を見る。
6. ユーザー操作に近い関数から見る。
7. その関数が呼んでいる補助関数を見る。

AstrBot プラグインなら、まず以下を探します。

```python
@register(...)
@filter.command(...)
@filter.command_group(...)
@filter.on_llm_request()
```

これらが入口です。

## なぜこのコードが急に出てくるのかを調べる方法

たとえば急に以下が出てきたとします。

```python
yield event.plain_result(text)
```

調べる順番です。

1. `event` はどこから来たか見る。
2. 関数の引数を見る。
3. `AstrMessageEvent` という型を見る。
4. AstrBot の docs で `plain_result` を探す。
5. 他のプラグインで同じ書き方を探す。

つまり、急に出てきたように見えるコードも、だいたい以下のどれかから来ています。

- import したもの。
- 関数の引数。
- `self` に保存したもの。
- 親クラスから受け継いだもの。
- フレームワークが渡してくれるもの。

## 変更前に考えること

コードを書く前に、以下を1分だけ考えます。

```text
どのコマンドの話か
入力は何か
保存する必要があるか
LLM を呼ぶ必要があるか
ユーザーへの返事は何か
失敗したときは何を返すか
```

これを考えると、無駄なコードが減ります。

## 小さく変更する

悪い進め方です。

```text
一気に add/list/ask/embedding/PDF まで作る
```

良い進め方です。

```text
help だけ作る
動かす
add の形だけ作る
動かす
JSON 保存だけ作る
動かす
```

小さい変更なら、壊れた場所が分かりやすいです。

## git diff を読む

変更後は以下を見ます。

```bash
git diff
```

見るポイントです。

- 意図しないファイルを変えていないか。
- 消すつもりのないコードを消していないか。
- 追加したコードが多すぎないか。
- コメントや文字列に誤字がないか。

`git diff` を読む習慣は、開発者として非常に大事です。

## エラーを読む

エラーは下から読みます。

例です。

```text
Traceback (most recent call last):
  File "main.py", line 52, in research_add
    json.dump(notes, f)
NameError: name 'json' is not defined
```

見る場所です。

- `NameError`: エラーの種類。
- `name 'json' is not defined`: json が定義されていない。
- `main.py`, line 52: 自分のファイルの場所。

この場合、`import json` を忘れている可能性が高いです。

## ログを使う

処理の途中を確認したいときはログを使います。

```python
logger.info(f"Loaded {len(notes)} notes")
```

ただし、資料本文や個人情報をそのままログに出すのは注意します。

良いログです。

```python
logger.info(f"Matched {len(matched_notes)} notes")
```

危険なログです。

```python
logger.info(f"Full prompt: {prompt}")
```

学習中のテストデータならよいですが、本物の資料では注意します。

## 調べ方

分からないことが出たら、以下の順番で調べます。

1. このリポジトリ内で同じ書き方を探す。
2. AstrBot docs を読む。
3. Mnemosyne の似た処理を見る。
4. Python 公式ドキュメントや信頼できる解説を見る。
5. 小さい実験コードを書く。

たとえば `@filter.command_group` が分からないなら、Mnemosyne の `@filter.command_group("memory")` を見ると理解しやすいです。

## コードを写すときの注意

コードを写すこと自体は悪くありません。ただし、写した後に以下を確認します。

- 変数名を説明できるか。
- その関数がいつ呼ばれるか説明できるか。
- エラー時にどこを直すか想像できるか。
- 自分のプラグイン名やコマンド名に合っているか。

写して動かし、意味を確認し、少し変える。この繰り返しで開発力がつきます。

## おすすめ学習テーマ

Research Note と並行して勉強するとよいテーマです。

1. Python のクラスと `self`。
2. Python のファイル読み書き。
3. JSON。
4. 例外処理。
5. 非同期処理の基本。
6. Git の `status`、`diff`、`add`、`commit`。
7. HTTP API の基本。
8. LLM の prompt engineering。
9. RAG の基本。
10. embedding とベクトル検索。

## 今は深追いしなくてよいテーマ

最初から深追いすると遠回りになるものです。

- Docker の詳細。
- Kubernetes。
- 高度なデータベース設計。
- Web フロントエンド。
- 認証認可の高度な設計。
- CI/CD。
- 大規模分散システム。

これらは後で必要になったときに学べばよいです。
