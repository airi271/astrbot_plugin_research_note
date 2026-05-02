# 01 Hello World: テンプレートを Research Note 用に変える

このステップでは、現在の Hello World テンプレートを Research Note のプラグインとして認識しやすい形に変えます。

先に読むと理解しやすい補助資料です。

- `../concepts/01_python_for_plugins.md`: `import`、クラス、`self`、デコレータ。
- `../concepts/02_astrbot_plugin_terms.md`: `Star`、`Context`、`event`、`filter`。
- `../concepts/03_yield_async_event.md`: なぜ `yield event.plain_result(...)` を使うのか。

## 目的

まず AstrBot がこのプラグインを読み込み、簡単なコマンドに返事できる状態を作ります。

ここでは保存や検索は作りません。

## 変更するファイル

```text
main.py
metadata.yaml
```

## 理解するコード

現在の `main.py` には以下があります。

```python
@register("helloworld", "YourName", "一个简单的 Hello World 插件", "1.0.0")
class MyPlugin(Star):
```

これは、AstrBot にプラグイン情報を伝える部分です。

Research Note では、たとえば以下のような意味に変えます。

```python
@register(
    "research_note",
    "airi271",
    "Research note assistant for source-grounded question answering.",
    "0.1.0",
)
class ResearchNotePlugin(Star):
```

実際に変更するときは、既存のスタイルに合わせればよいです。

## クラス名

`MyPlugin` でも動きますが、学習しやすくするために `ResearchNotePlugin` のように名前を変えると読みやすいです。

```python
class ResearchNotePlugin(Star):
```

クラス名はユーザーから見えるコマンド名ではありません。Python のコードを読む人のための名前です。

## 最初のコマンド

最初は `/research_hello` のような単純なコマンドにします。

```python
@filter.command("research_hello")
async def research_hello(self, event: AstrMessageEvent):
    """Research Note の動作確認コマンド。"""
    user_name = event.get_sender_name()
    yield event.plain_result(f"Research Note is ready, {user_name}!")
```

ここで重要なのは以下です。

- `@filter.command("research_hello")` でコマンド名を決める。
- 関数の最初の引数は `self`。
- 次の引数は `event`。
- `yield event.plain_result(...)` で返信する。

## 使わない変数は消してよい

テンプレートには以下があります。

```python
message_str = event.message_str
message_chain = event.get_messages()
logger.info(message_chain)
```

学習用にはよいですが、最小の確認では不要です。使わない変数があると混乱するので、最初は消しても構いません。

## metadata.yaml

`metadata.yaml` はプラグインの表示情報です。

確認する項目は以下です。

- `name`: `astrbot_plugin_research_note`
- `display_name`: `Research Note`
- `desc`: プラグインの説明。
- `version`: `v0.1.0` など。
- `author`: 作者名。
- `repo`: GitHub URL。

ここはすでに Research Note 用になっているので、大きく変えなくてよいです。

## 動作確認

AstrBot を起動します。

```bash
source /home/ayaka/.virtualenvs/.venv/bin/activate
cd /home/ayaka/codding/astrbotpj/AstrBot
python main.py
```

チャットで以下を送ります。

```text
/research_hello
```

期待する結果です。

```text
Research Note is ready, <ユーザー名>!
```

## よくある失敗

### コマンドが反応しない

確認することです。

- AstrBot を再起動したか。
- プラグインが有効になっているか。
- コマンド名を間違えていないか。
- `@filter.command("research_hello")` の文字列と送ったコマンドが一致しているか。

### 起動時に SyntaxError が出る

確認することです。

- 括弧を閉じ忘れていないか。
- 文字列の引用符が閉じているか。
- インデントがずれていないか。

### ImportError が出る

確認することです。

- `from astrbot.api.event import filter, AstrMessageEvent` があるか。
- `from astrbot.api.star import Context, Star, register` があるか。

## このステップの完了条件

- `main.py` が Research Note 用の名前になっている。
- `/research_hello` が返事する。
- AstrBot 起動時にプラグインエラーが出ない。

## コードを詳しく読む

最小の AstrBot プラグインは、だいたい以下の形です。

```python
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register


@register("research_note", "airi271", "Research note assistant", "0.1.0")
class ResearchNotePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("research_hello")
    async def research_hello(self, event: AstrMessageEvent):
        user_name = event.get_sender_name()
        yield event.plain_result(f"Research Note is ready, {user_name}!")
```

1行ずつ意味を見ます。

```python
from astrbot.api.event import filter, AstrMessageEvent
```

`filter` は、コマンドやイベントを登録するために使います。`AstrMessageEvent` は、ユーザーから届いたメッセージ情報を持つ型です。

```python
from astrbot.api.star import Context, Star, register
```

`Star` は AstrBot プラグインの親クラスです。`Context` は AstrBot 本体とやり取りする窓口です。`register` は、このクラスがプラグインであることを AstrBot に知らせます。

```python
@register("research_note", "airi271", "Research note assistant", "0.1.0")
```

`@register` はデコレータです。デコレータは、関数やクラスに追加情報や機能を付ける Python の仕組みです。ここでは、プラグイン名、作者、説明、バージョンを登録しています。

```python
class ResearchNotePlugin(Star):
```

`Star` を継承しています。継承とは「AstrBot プラグインとして必要な基本機能を受け継ぐ」という意味です。

```python
def __init__(self, context: Context):
    super().__init__(context)
```

`__init__` はインスタンスが作られたときに呼ばれる初期化関数です。`super().__init__(context)` は、親クラス `Star` の初期化も実行するために必要です。

```python
@filter.command("research_hello")
```

この下の関数を `/research_hello` コマンドとして登録します。

```python
async def research_hello(self, event: AstrMessageEvent):
```

`async def` は非同期関数です。AstrBot では、メッセージ処理や LLM 呼び出しなど待ち時間がある処理を扱うため、非同期関数を使います。

```python
yield event.plain_result(...)
```

AstrBot に「このテキストを返信してください」と渡しています。普通の Python では `return` をよく使いますが、AstrBot のコマンドハンドラでは `yield` で結果を返す形がよく使われます。

## 周辺知識: デコレータ

`@filter.command("research_hello")` のような `@` から始まるものをデコレータと呼びます。

難しく考える必要はありません。最初はこう覚えます。

```text
@filter.command("名前")
次の関数を、その名前のコマンドとして AstrBot に登録する
```

つまり、以下の関数は、ただの Python 関数ではなく AstrBot のコマンドになります。

```python
@filter.command("research_hello")
async def research_hello(...):
    ...
```

## 周辺知識: self とは何か

クラスの中の関数には、最初の引数に `self` が出てきます。

```python
async def research_hello(self, event):
```

`self` は「このプラグイン自身」です。後で `self.notes_file`、`self.config`、`self.context` のように、プラグインが持つ情報にアクセスするために使います。

最初はこう覚えてください。

```text
self は、このプラグインの中で共有するデータや機能にアクセスするためのもの
```

## 開発者の考え方

このステップの目的は、便利な機能を作ることではありません。「AstrBot が自分のコードを呼んでくれる」ことを確認することです。

アプリ開発では、最初に入口を確認します。入口が動かなければ、保存も検索も LLM も動きません。

このステップで見るべき成功はこれです。

```text
自分が書いた関数が、チャットのコマンドから呼ばれた
```
