# 06 Config And Safety: 設定と安全処理を入れる

このステップでは、動いた最小版を少し安全で使いやすくします。

先に読むと理解しやすい補助資料です。

- `../concepts/01_python_for_plugins.md`: `dict.get`、例外処理、型ヒント。
- `../concepts/02_astrbot_plugin_terms.md`: `_conf_schema.json`、AstrBotConfig。
- `../concepts/05_developer_workflow.md`: 安全な変更、エラーの読み方。

## 目的

以下を追加します。

- `_conf_schema.json` で設定を持つ。
- `top_k` を設定できる。
- 1件の資料の最大文字数を設定できる。
- 空文字や長すぎる入力を処理する。
- 削除は `--confirm` 必須にする。

## 変更するファイル

```text
main.py
_conf_schema.json
```

## 設定ファイルを作る

プラグイン直下に `_conf_schema.json` を作ります。

```json
{
  "top_k": {
    "description": "質問時に使う関連資料の数",
    "type": "int",
    "default": 3,
    "minimum": 1,
    "maximum": 10
  },
  "max_note_chars": {
    "description": "1件の資料からプロンプトに入れる最大文字数",
    "type": "int",
    "default": 1200,
    "minimum": 100,
    "maximum": 10000
  },
  "max_add_chars": {
    "description": "1回で追加できる資料の最大文字数",
    "type": "int",
    "default": 8000,
    "minimum": 100,
    "maximum": 50000
  },
  "strict_grounding": {
    "description": "資料にないことを推測しないよう強く指示する",
    "type": "bool",
    "default": true
  }
}
```

## config を受け取る

`main.py` で `AstrBotConfig` を import します。

```python
from astrbot.api import AstrBotConfig, logger
```

`__init__` を変更します。

```python
def __init__(self, context: Context, config: AstrBotConfig):
    super().__init__(context)
    self.config = config
```

既存の `logger` import と重複しないように注意します。

## 設定を使う

`ask` の検索件数を設定から取ります。

```python
top_k = int(self.config.get("top_k", 3))
matched_notes = self._search_notes(question, notes, top_k=top_k)
```

プロンプトに入れる資料の長さも設定から取ります。

```python
max_note_chars = int(self.config.get("max_note_chars", 1200))
content = str(note.get("content", ""))[:max_note_chars]
```

## 長すぎる add を防ぐ

```python
max_add_chars = int(self.config.get("max_add_chars", 8000))
if len(content) > max_add_chars:
    yield event.plain_result(f"資料が長すぎます。最大 {max_add_chars} 文字までです。")
    return
```

## strict_grounding を使う

プロンプト作成時に、設定で指示を切り替えます。

```python
if self.config.get("strict_grounding", True):
    grounding_rule = "資料に書かれていないことは、推測せず『資料からは分かりません』と答えてください。"
else:
    grounding_rule = "資料を優先し、不足する部分は一般知識で補っても構いません。"
```

## JSON 読み込みを少し安全にする

JSON ファイルが壊れたときに、プラグイン全体が落ちないようにします。

```python
def _load_notes(self) -> list[dict]:
    if not self.notes_file.exists():
        return []
    try:
        with self.notes_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        logger.error("research_notes.json is broken.", exc_info=True)
        return []

    if not isinstance(data, list):
        return []
    return data
```

## clear は確認必須にする

削除は必ず確認を要求します。

```python
if confirm != "--confirm":
    yield event.plain_result("本当に削除する場合は /research clear --confirm を実行してください。")
    return
```

## 動作確認

以下を確認します。

```text
/research add 
/research clear
/research clear --confirm
/research ask unknown
```

期待することです。

- 空の追加で落ちない。
- `clear` は確認なしでは削除しない。
- 関連資料なしでも落ちない。
- 設定ファイルを追加してもプラグインが起動する。

## このステップの完了条件

- `_conf_schema.json` がある。
- `top_k` が設定から読まれる。
- `max_note_chars` が設定から読まれる。
- 長すぎる入力を拒否できる。
- JSON が壊れても最低限落ちない。

## コードを詳しく読む

設定を受け取るには、`__init__` の形を変えます。

```python
def __init__(self, context: Context, config: AstrBotConfig):
    super().__init__(context)
    self.config = config
```

`config` は AstrBot が `_conf_schema.json` を読んで作った設定です。

```python
self.config = config
```

こうしておくと、別のメソッドでも `self.config.get(...)` で設定を読めます。

## `get` の意味

```python
top_k = int(self.config.get("top_k", 3))
```

これは「設定に `top_k` があればそれを使い、なければ `3` を使う」という意味です。

`dict.get(key, default)` は Python でよく使います。

```python
value = data.get("name", "unknown")
```

`data["name"]` と違い、キーがなくてもエラーになりません。

## 入力チェックの意味

以下は、空の資料を保存しないためのチェックです。

```python
content = content.strip()
if not content:
    yield event.plain_result("追加する資料テキストを入力してください。")
    return
```

`strip()` は前後の空白や改行を削ります。

`if not content:` は、空文字なら True になります。

## 長さ制限の意味

```python
if len(content) > max_add_chars:
    yield event.plain_result(f"資料が長すぎます。最大 {max_add_chars} 文字までです。")
    return
```

長すぎる入力を許すと、以下の問題が起きます。

- JSON ファイルが大きくなる。
- LLM に渡すプロンプトが長くなりすぎる。
- 処理が遅くなる。
- エラー時の原因調査が難しくなる。

制限は不親切ではなく、アプリを安定させるために必要です。

## 例外処理の意味

```python
try:
    with self.notes_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
except json.JSONDecodeError:
    logger.error("research_notes.json is broken.", exc_info=True)
    return []
```

`try` の中でエラーが起きたら、`except` に移動します。

ここでは JSON が壊れていた場合、プラグイン全体を落とさずに空リストを返しています。

`exc_info=True` は、エラーの詳細な traceback をログに出すためです。

## 周辺知識: 安全な削除

削除系コマンドは、必ず確認を入れるのが基本です。

悪い例です。

```text
/research clear
```

これだけで全削除されると、打ち間違いでデータが消えます。

良い例です。

```text
/research clear --confirm
```

明示的な確認を要求すると、事故が減ります。

## 周辺知識: 設定にするかコードに書くか

最初はコードに直接書いてよいです。

```python
top_k = 3
```

ただし、ユーザーや環境によって変えたい値は設定にします。

設定に向いているものです。

- 検索件数。
- 最大文字数。
- 厳密に資料だけで答えるか。
- 保存ファイル名。

設定に向かないものです。

- 関数名。
- データ構造の根本。
- 内部処理の細かすぎる値。

## 開発者の考え方

動くだけのコードと、使い続けられるコードは違います。

使い続けられるコードには以下があります。

- 入力チェックがある。
- エラー時に落ちにくい。
- 危険操作に確認がある。
- ユーザーが設定を変えられる。
- ログで原因を追える。

このステップは、初心者から開発者に近づくためにとても重要です。
