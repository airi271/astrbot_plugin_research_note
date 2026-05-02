# Yield, Async, Event

このファイルでは、AstrBot で急に出てくる `yield`、`async`、`await`、イベント処理を説明します。

## なぜ AstrBot では `yield` を使うのか

AstrBot のコマンド関数では、以下のように返信します。

```python
yield event.plain_result("Hello")
```

普通の Python なら `return "Hello"` でよさそうに見えます。

しかし AstrBot では、1つのコマンド処理から複数の結果を順番に返せるようにするため、`yield` が使われます。

イメージです。

```python
@filter.command("demo")
async def demo(self, event):
    yield event.plain_result("まず確認します")
    yield event.plain_result("次に処理します")
    yield event.plain_result("完了しました")
```

このように、1回のコマンドで複数メッセージを返すことができます。

## `return` と `yield` の違い

`return` は、関数を終了して1つの値を返します。

```python
def add(a, b):
    return a + b
```

`yield` は、値を途中で外に渡し、必要ならその後も処理を続けられます。

```python
def numbers():
    yield 1
    yield 2
    yield 3
```

AstrBot のコマンドでは、`yield event.plain_result(...)` によって、返信結果を AstrBot に渡します。

## 途中で止めるときは `return`

返信には `yield` を使いますが、処理を止めるには `return` を使います。

```python
if not content:
    yield event.plain_result("資料を入力してください。")
    return
```

これは以下の意味です。

```text
資料が空なら、メッセージを返して、この関数をここで終了する
```

## なぜ `async def` を使うのか

AstrBot の処理には、時間がかかるものが多いです。

- LLM API を呼ぶ。
- embedding API を呼ぶ。
- ネットワーク越しにメッセージを送る。
- データベースに接続する。

この間、プログラム全体を止めないようにするため、非同期処理を使います。

非同期関数は以下です。

```python
async def research_ask(self, event, question: str):
    ...
```

## `await` とは何か

`await` は、非同期処理の完了を待つために使います。

```python
llm_resp = await self.context.llm_generate(
    chat_provider_id=provider_id,
    prompt=prompt,
)
```

これは「LLM の回答が返るまで待つ」という意味です。

`await` を使えるのは、基本的に `async def` の中だけです。

## 同期処理と非同期処理

同期処理は、上から順番に終わるまで待ちます。

```python
result = slow_function()
print(result)
```

非同期処理は、待ち時間をうまく扱います。

```python
result = await slow_async_function()
print(result)
```

初心者のうちは、こう覚えれば十分です。

```text
LLM、ネットワーク、DB、AstrBot API には await が必要なことが多い
```

## event-driven とは何か

AstrBot はイベント駆動です。

イベント駆動とは、「何かが起きたときに、その処理が呼ばれる」仕組みです。

例です。

```text
ユーザーが /research help を送る
AstrBot が research_help を呼ぶ
research_help が返信を yield する
AstrBot がチャットに返信する
```

自分で `research_help()` を直接呼ぶわけではありません。AstrBot が呼びます。

## コマンドとイベントフックの違い

コマンドは、ユーザーが明示的に呼びます。

```text
/research ask Transformer とは？
```

イベントフックは、AstrBot の処理途中で自動的に呼ばれます。

```python
@filter.on_llm_request()
async def query_memory(self, event, req):
    ...
```

Mnemosyne は、ユーザーが `/memory search` と言わなくても、LLM に送る前に自動で記憶検索します。これはイベントフックを使っているからです。

## なぜ `print()` ではなく `event.plain_result()` なのか

`print()` はターミナルに出力します。

```python
print("Hello")
```

でも、ユーザーが見ているのはチャット画面です。

チャットに返すには、AstrBot に「この内容を返信して」と渡す必要があります。

```python
yield event.plain_result("Hello")
```

## よくある混乱

### `yield` と `return` のどちらを使うのか

ユーザーに返事するなら `yield event.plain_result(...)`。

処理を止めるなら `return`。

### `await` をどこに付けるのか

非同期関数を呼ぶときに付けます。

例です。

```python
provider_id = await self.context.get_current_chat_provider_id(...)
```

### 関数を自分で呼んでいないのになぜ動くのか

`@filter.command(...)` で AstrBot に登録しているからです。AstrBot が必要なタイミングで呼びます。
