# 03 JSON Storage: 資料を保存する

このステップでは、`/research add` で受け取った資料を JSON ファイルに保存します。

先に読むと理解しやすい補助資料です。

- `../concepts/01_python_for_plugins.md`: 辞書、リスト、JSON、`Path`、例外処理。
- `../concepts/05_developer_workflow.md`: 小さく変更して確認する方法。

## 目的

AstrBot を再起動しても資料が残る状態を作ります。

## 変更するファイル

最初は以下だけでよいです。

```text
main.py
```

後で `store.py` に分けますが、最初は1ファイルで理解します。

## 保存データの形

最初はこの形で十分です。

```json
{
  "id": "note_001",
  "content": "資料本文",
  "created_at": "2026-05-02T12:00:00"
}
```

資料全体はリストで保存します。

```json
[
  {
    "id": "note_001",
    "content": "資料本文",
    "created_at": "2026-05-02T12:00:00"
  }
]
```

## 保存ファイル

最初はプラグイン内に `data/research_notes.json` を作ると分かりやすいです。

```text
astrbot_plugin_research_note/data/research_notes.json
```

本格的には AstrBot のデータディレクトリを使う方がよいですが、初心者の最初の実装では「どこに保存されたか分かる」ことを優先します。

## 必要な import

`main.py` の上の方に追加します。

```python
import json
from datetime import datetime
from pathlib import Path
```

## 保存先パスを持つ

`__init__` で保存先を作ります。

```python
def __init__(self, context: Context):
    super().__init__(context)
    self.data_dir = Path(__file__).parent / "data"
    self.data_dir.mkdir(parents=True, exist_ok=True)
    self.notes_file = self.data_dir / "research_notes.json"
```

意味は以下です。

- `Path(__file__).parent`: 今の `main.py` があるディレクトリ。
- `/ "data"`: その下の `data` ディレクトリ。
- `mkdir(..., exist_ok=True)`: ディレクトリがなければ作る。あれば何もしない。

## JSON を読む関数

まず読み込み関数を作ります。

```python
def _load_notes(self) -> list[dict]:
    if not self.notes_file.exists():
        return []
    with self.notes_file.open("r", encoding="utf-8") as f:
        return json.load(f)
```

初心者向けには、最初はこれで十分です。後で JSON が壊れた場合の処理を足します。

## JSON に書く関数

```python
def _save_notes(self, notes: list[dict]) -> None:
    with self.notes_file.open("w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)
```

`ensure_ascii=False` は、日本語を読みやすく保存するためです。

## ID を作る

最初は件数から ID を作ればよいです。

```python
def _next_note_id(self, notes: list[dict]) -> str:
    return f"note_{len(notes) + 1:03d}"
```

この方法は、削除後に ID が重複する可能性があります。最初は学習用として許容し、後で改善します。

## add を保存対応にする

```python
@research_group.command("add")
async def research_add(self, event: AstrMessageEvent, content: str):
    """資料を追加します。"""
    content = content.strip()
    if not content:
        yield event.plain_result("追加する資料テキストを入力してください。")
        return

    notes = self._load_notes()
    note = {
        "id": self._next_note_id(notes),
        "content": content,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    notes.append(note)
    self._save_notes(notes)

    yield event.plain_result(f"資料を保存しました: {note['id']}")
```

## list を保存対応にする

```python
@research_group.command("list")
async def research_list(self, event: AstrMessageEvent):
    """保存済み資料を表示します。"""
    notes = self._load_notes()
    if not notes:
        yield event.plain_result("保存済み資料はありません。")
        return

    lines = ["保存済み資料:"]
    for note in notes[:10]:
        preview = note["content"].replace("\n", " ")[:60]
        lines.append(f"- {note['id']}: {preview}")

    yield event.plain_result("\n".join(lines))
```

## clear を保存対応にする

```python
@research_group.command("clear")
async def research_clear(self, event: AstrMessageEvent, confirm: str | None = None):
    """保存済み資料を削除します。"""
    if confirm != "--confirm":
        yield event.plain_result("削除するには /research clear --confirm を実行してください。")
        return

    self._save_notes([])
    yield event.plain_result("保存済み資料をすべて削除しました。")
```

## 動作確認

以下を試します。

```text
/research list
/research add Transformer は自然言語処理で使われるニューラルネットワーク構造です。
/research list
```

次に AstrBot を再起動して、もう一度以下を試します。

```text
/research list
```

再起動後も資料が表示されれば成功です。

## よくある失敗

### JSON ファイルが見つからない

`self.data_dir.mkdir(...)` を `__init__` に入れているか確認します。

### 日本語が `\u30...` のようになる

`json.dump(..., ensure_ascii=False)` になっているか確認します。

### JSONDecodeError が出る

JSON ファイルを手で編集して壊した可能性があります。学習中は `data/research_notes.json` を削除して再作成してもよいです。

## このステップの完了条件

- `/research add <text>` で資料が保存される。
- `/research list` で資料が表示される。
- AstrBot を再起動しても資料が残る。
- `/research clear --confirm` で資料を消せる。

## コードを詳しく読む

保存処理で一番重要なのは、メモリとファイルの違いです。

Python のリストに資料を入れただけでは、AstrBot を再起動すると消えます。

```python
notes = []
notes.append(note)
```

これはメモリ上にあるだけです。再起動後も残したいなら、ファイルに書く必要があります。

```python
self._save_notes(notes)
```

## `Path` の意味

```python
self.data_dir = Path(__file__).parent / "data"
```

`__file__` は、今実行されている Python ファイルの場所です。ここでは `main.py` です。

`Path(__file__).parent` は、`main.py` があるディレクトリです。

`/ "data"` は、パスをつなげています。文字列の割り算ではありません。`pathlib.Path` では `/` を使ってパスを結合できます。

結果として、以下のような場所になります。

```text
astrbot_plugin_research_note/data
```

## JSON の読み込み

```python
def _load_notes(self) -> list[dict]:
    if not self.notes_file.exists():
        return []
    with self.notes_file.open("r", encoding="utf-8") as f:
        return json.load(f)
```

この関数は「保存済み資料を Python のリストとして返す」役割です。

```python
if not self.notes_file.exists():
    return []
```

ファイルがまだない場合は、資料が0件という意味で空リストを返します。

```python
with self.notes_file.open("r", encoding="utf-8") as f:
```

ファイルを読み込みモードで開きます。`with` を使うと、処理が終わったあと自動でファイルを閉じます。

```python
return json.load(f)
```

JSON ファイルの中身を Python のリストや辞書に変換します。

## JSON の書き込み

```python
def _save_notes(self, notes: list[dict]) -> None:
    with self.notes_file.open("w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)
```

この関数は「Python のリストを JSON ファイルに保存する」役割です。

`"w"` は書き込みモードです。既存ファイルがあれば上書きします。

`ensure_ascii=False` は日本語をそのまま保存するためです。

`indent=2` は人間が読みやすいように整形するためです。

## なぜ `_load_notes` のように `_` を付けるのか

Python では、関数名の先頭に `_` を付けると「内部用」という意味になります。

```python
def _load_notes(self):
```

これは厳密な禁止ではありませんが、他の開発者に「この関数はプラグイン内部で使うものです」と伝える習慣です。

## 周辺知識: 辞書とリスト

資料1件は辞書です。

```python
note = {
    "id": "note_001",
    "content": "資料本文",
    "created_at": "2026-05-02T12:00:00",
}
```

資料全体はリストです。

```python
notes = [note_1, note_2, note_3]
```

つまり Research Note の保存データは「辞書のリスト」です。

## 開発者の考え方

保存処理では、常にこの3つを考えます。

```text
作成: add で1件増やす
読取: list や ask で読む
削除: clear で消す
```

これは CRUD と呼ばれる考え方の一部です。

- Create: 作る
- Read: 読む
- Update: 更新する
- Delete: 削除する

Research Note の最小版では、Create、Read、Delete だけで始めます。Update は後で資料編集機能が欲しくなったら追加します。
