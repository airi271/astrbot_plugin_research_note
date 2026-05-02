# Python For Plugins

このファイルでは、AstrBot プラグインを書くために必要な Python の基礎だけを説明します。

データ分析で Python を使ったことがあっても、アプリ開発では見慣れない書き方が出てきます。特に、クラス、デコレータ、非同期、ファイル分割、型ヒントに慣れる必要があります。

## import

`import` は、他のファイルやライブラリの機能を使うための文です。

```python
import json
from pathlib import Path
from astrbot.api.event import filter, AstrMessageEvent
```

意味は以下です。

- `import json`: Python 標準の JSON 処理を使う。
- `from pathlib import Path`: ファイルパスを扱う `Path` を使う。
- `from astrbot.api.event import filter`: AstrBot のコマンド登録機能を使う。

急にコードに `json.dump` や `Path(...)` が出てくるのは、上で import しているからです。

## 変数

変数は値に名前を付けたものです。

```python
content = "Transformer は attention を使う"
top_k = 3
```

開発では、変数名を見て役割が分かることが大事です。

良い例です。

```python
question = "Transformer とは？"
matched_notes = self._search_notes(question, notes)
```

悪い例です。

```python
x = "Transformer とは？"
y = self._search_notes(x, z)
```

動きは同じでも、読みやすさが違います。

## 関数

関数は、処理に名前を付けたものです。

```python
def _load_notes(self) -> list[dict]:
    ...
```

この関数名から、「ノートを読み込む処理」だと分かります。

関数を見るときは、以下を確認します。

```text
何を受け取るか
何を返すか
中で何をするか
```

例です。

```python
def _search_notes(self, question: str, notes: list[dict], top_k: int = 3) -> list[dict]:
```

これは以下の意味です。

- `question`: 質問文を受け取る。
- `notes`: 資料リストを受け取る。
- `top_k`: 何件返すかを受け取る。指定がなければ3。
- `-> list[dict]`: 辞書のリストを返す。

## 型ヒント

型ヒントは、変数や関数がどんな値を扱うかのメモです。

```python
content: str
top_k: int
notes: list[dict]
```

意味は以下です。

- `str`: 文字列。
- `int`: 整数。
- `list[dict]`: 辞書が入ったリスト。

型ヒントは、Python の実行に必ず必要なものではありません。ただし、コードを読む人にとって非常に役立ちます。

## クラス

クラスは、データと処理をまとめる設計図です。

AstrBot プラグインはクラスとして書きます。

```python
class ResearchNotePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
```

`ResearchNotePlugin` は自分のプラグインです。

`Star` は AstrBot プラグインの基本クラスです。

`ResearchNotePlugin(Star)` は、「AstrBot プラグインとしての性質を持つ ResearchNotePlugin を作る」という意味です。

## self

`self` は、このプラグイン自身を表します。

```python
self.notes_file = self.data_dir / "research_notes.json"
```

こうすると、別のメソッドからも `self.notes_file` として使えます。

`self` が付いていない変数は、その関数の中だけで使う一時的な変数です。

```python
notes = self._load_notes()
```

`notes` はこの関数の中だけです。

```python
self.config = config
```

`self.config` はプラグイン全体で使えます。

## メソッド

クラスの中にある関数をメソッドと呼びます。

```python
class ResearchNotePlugin(Star):
    async def research_help(self, event):
        ...
```

`research_help` は `ResearchNotePlugin` のメソッドです。

## デコレータ

`@` から始まる行をデコレータと呼びます。

```python
@filter.command("research_hello")
async def research_hello(self, event):
    ...
```

これは「下の関数を `/research_hello` コマンドとして登録する」という意味です。

最初は、デコレータを「AstrBot への登録ラベル」と考えると分かりやすいです。

## 辞書

辞書は、キーと値のセットです。

```python
note = {
    "id": "note_001",
    "content": "資料本文",
}
```

取り出すときは以下です。

```python
note["id"]
note.get("content", "")
```

`note["id"]` は、キーがないとエラーになります。

`note.get("content", "")` は、キーがなければ空文字を返します。

## リスト

リストは複数の値を順番に持ちます。

```python
notes = [note_1, note_2, note_3]
```

追加するときは以下です。

```python
notes.append(note)
```

最初の10件だけ見るときは以下です。

```python
notes[:10]
```

## pathlib.Path

ファイルパスは文字列でも扱えますが、開発では `Path` が便利です。

```python
self.data_dir = Path(__file__).parent / "data"
```

`/` でパスをつなげられます。

```python
self.notes_file = self.data_dir / "research_notes.json"
```

## 例外処理

エラーが起きるかもしれない処理には `try` / `except` を使います。

```python
try:
    data = json.load(f)
except json.JSONDecodeError:
    return []
```

これは「JSON 読み込みに失敗したら、プラグインを落とさず空リストを返す」という意味です。

## まず勉強するとよい Python 範囲

Research Note のために優先して勉強するとよいものです。

1. 関数。
2. 辞書とリスト。
3. クラスと `self`。
4. ファイル読み書き。
5. JSON。
6. 例外処理。
7. `async` / `await`。
8. 型ヒント。

逆に、最初は深追いしなくてよいものです。

- メタクラス。
- 高度な継承。
- デザインパターン全般。
- 並列処理の細かい理論。
- パッケージ公開の詳細。
