# 02 Command Group: `/research` コマンド群を作る

このステップでは、Research Note の基本操作を `/research ...` にまとめます。

先に読むと理解しやすい補助資料です。

- `../concepts/02_astrbot_plugin_terms.md`: command、command group、event。
- `../concepts/03_yield_async_event.md`: `yield` と `return` の使い分け。
- `../concepts/05_developer_workflow.md`: インターフェースを先に決める考え方。

## 目的

最終的に以下の形にします。

```text
/research help
/research add <text>
/research list
/research ask <question>
/research clear
```

この段階では、まだ JSON 保存や LLM 呼び出しは作らなくてもよいです。まずコマンドの形だけを作ります。

## 変更するファイル

```text
main.py
```

## コマンドグループとは

`/research add`、`/research ask` のように、同じ親コマンドの下に複数のサブコマンドを作る仕組みです。

Mnemosyne では以下のように使っています。

```python
@filter.command_group("memory")
def memory_group(self):
    pass
```

Research Note では以下のようにします。

```python
@filter.command_group("research")
def research_group(self):
    """Research Note commands."""
    pass
```

## help コマンド

最初に作るべきは help です。使い方が自分でも確認できるからです。

例です。

```python
@research_group.command("help")
async def research_help(self, event: AstrMessageEvent):
    """Research Note の使い方を表示します。"""
    text = """Research Note commands:
/research add <text> - 資料を追加
/research list - 資料一覧
/research ask <question> - 資料に基づいて質問
/research clear --confirm - 全資料を削除
"""
    yield event.plain_result(text)
```

## add コマンドの形

この段階では保存せず、受け取った文字を返すだけでよいです。

```python
@research_group.command("add")
async def research_add(self, event: AstrMessageEvent, content: str):
    """資料を追加します。"""
    yield event.plain_result(f"資料を受け取りました: {content[:50]}")
```

`content: str` が、ユーザーが `/research add` の後ろに書いた文字列です。

## list コマンドの形

この段階では固定文でよいです。

```python
@research_group.command("list")
async def research_list(self, event: AstrMessageEvent):
    """保存済み資料を表示します。"""
    yield event.plain_result("まだ資料保存は実装していません。")
```

## ask コマンドの形

この段階では LLM を呼ばず、質問を受け取るだけでよいです。

```python
@research_group.command("ask")
async def research_ask(self, event: AstrMessageEvent, question: str):
    """資料に基づいて質問します。"""
    yield event.plain_result(f"質問を受け取りました: {question}")
```

## clear コマンドの形

削除系は危険なので、最初から `--confirm` を要求する癖をつけます。

```python
@research_group.command("clear")
async def research_clear(self, event: AstrMessageEvent, confirm: str | None = None):
    """保存済み資料を削除します。"""
    if confirm != "--confirm":
        yield event.plain_result("削除するには /research clear --confirm を実行してください。")
        return
    yield event.plain_result("削除処理はまだ実装していません。")
```

## 動作確認

AstrBot を再起動して、以下を順番に試します。

```text
/research help
/research add Transformer は注意機構を使うモデルです
/research list
/research ask Transformer とは？
/research clear
/research clear --confirm
```

## よくある失敗

### `research_group` が見つからない

`@research_group.command(...)` は、`research_group` の定義より下に書く必要があります。

### 引数つきコマンドが失敗する

`content: str` や `question: str` を忘れている可能性があります。

### `return` の後に返信しようとしている

`return` した後のコードは実行されません。削除確認のような分岐では、返信してから `return` します。

## このステップの完了条件

- `/research help` が使える。
- `/research add <text>` が使える。
- `/research list` が使える。
- `/research ask <question>` が使える。
- `/research clear` と `/research clear --confirm` の動きが違う。

## コードを詳しく読む

コマンドグループの基本形は以下です。

```python
@filter.command_group("research")
def research_group(self):
    """Research Note commands."""
    pass
```

これは `/research` という親コマンドを作ります。`pass` は「ここでは何もしない」という Python の文です。コマンドグループの本体は空でよく、下にサブコマンドを登録します。

```python
@research_group.command("help")
async def research_help(self, event: AstrMessageEvent):
    ...
```

これは `/research help` を作ります。`research_group.command("help")` なので、親が `/research`、子が `help` です。

```python
@research_group.command("add")
async def research_add(self, event: AstrMessageEvent, content: str):
    ...
```

これは `/research add <content>` を作ります。`content: str` は、コマンドの後ろにあるテキストを受け取ります。

たとえば以下を送るとします。

```text
/research add Transformer は attention を使う
```

このとき、だいたい以下のように渡されます。

```text
content = "Transformer は attention を使う"
```

## `yield` と `return` の使い分け

コマンドでユーザーに返事するときは `yield event.plain_result(...)` を使います。

```python
yield event.plain_result("保存しました")
```

処理を途中で止めたいときは `return` を使います。

```python
if not content:
    yield event.plain_result("資料を入力してください。")
    return
```

この場合、「資料を入力してください」と返信してから、そこで処理を止めます。

## 周辺知識: 関数の引数

以下の関数を見ます。

```python
async def research_clear(self, event: AstrMessageEvent, confirm: str | None = None):
```

`confirm: str | None = None` は、「文字列か None が入る。何も指定されなければ None」という意味です。

つまり、以下なら `confirm` は `None` です。

```text
/research clear
```

以下なら `confirm` は `"--confirm"` です。

```text
/research clear --confirm
```

この差を使って、危険な削除を防ぎます。

## 周辺知識: なぜ help を先に作るのか

本物の開発では、使い方が分からない機能は自分でもテストしづらいです。

`/research help` を先に作ると、以下のメリットがあります。

- 自分が作る予定のコマンドを整理できる。
- 動作確認の入口になる。
- 後でユーザーにも説明しやすい。
- README を書くときの材料になる。

## 開発者の考え方

このステップは「機能の中身」ではなく「インターフェース」を作っています。

インターフェースとは、ユーザーがどう操作するかです。

先にインターフェースを決めると、実装が楽になります。

```text
/research add は保存する
/research list は一覧する
/research ask は質問する
/research clear は削除する
```

これが決まると、次に必要な処理も自然に決まります。
