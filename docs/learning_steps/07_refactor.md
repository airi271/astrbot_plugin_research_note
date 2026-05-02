# 07 Refactor: コードを分ける

このステップでは、長くなった `main.py` を役割ごとに分けます。

先に読むと理解しやすい補助資料です。

- `../concepts/01_python_for_plugins.md`: import、クラス、関数、ファイル分割。
- `../concepts/05_developer_workflow.md`: リファクタリングと `git diff` の読み方。

## 目的

コードを読みやすくし、次の embedding 対応に進みやすくします。

## まだ早い場合

`main.py` が短く、まだ理解しやすいなら、このステップは後回しでよいです。

分割の目安は以下です。

- `main.py` が 200 行を超えた。
- JSON 保存関数が増えて読みにくい。
- 検索関数を変更するたびにコマンド部分まで気になる。
- プロンプト文が長くなってきた。

## 推奨ファイル構成

```text
astrbot_plugin_research_note/
  main.py
  store.py
  search.py
  prompts.py
  metadata.yaml
  _conf_schema.json
```

役割は以下です。

- `main.py`: AstrBot の `@register`、コマンド、イベントだけ。
- `store.py`: JSON の読み書き。
- `search.py`: キーワード検索や将来の embedding 検索。
- `prompts.py`: LLM に渡すプロンプト作成。

## store.py に移すもの

保存関係を移します。

```python
import json
from pathlib import Path


class NoteStore:
    def __init__(self, notes_file: Path):
        self.notes_file = notes_file
        self.notes_file.parent.mkdir(parents=True, exist_ok=True)

    def load_notes(self) -> list[dict]:
        if not self.notes_file.exists():
            return []
        with self.notes_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []

    def save_notes(self, notes: list[dict]) -> None:
        with self.notes_file.open("w", encoding="utf-8") as f:
            json.dump(notes, f, ensure_ascii=False, indent=2)
```

`main.py` では以下のように使います。

```python
from .store import NoteStore

self.store = NoteStore(self.notes_file)
notes = self.store.load_notes()
self.store.save_notes(notes)
```

## search.py に移すもの

検索関係を移します。

```python
def tokenize(text: str) -> list[str]:
    normalized = text.lower().replace("\n", " ")
    tokens = []
    for token in normalized.split():
        token = token.strip(".,!?;:()[]{}<>。、！？「」『』（）")
        if token:
            tokens.append(token)
    return tokens


def search_notes(question: str, notes: list[dict], top_k: int = 3) -> list[dict]:
    tokens = tokenize(question)
    scored = []
    for note in notes:
        content = str(note.get("content", "")).lower()
        score = sum(1 for token in tokens if token in content)
        if score > 0:
            scored.append((score, note))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [note for score, note in scored[:top_k]]
```

## prompts.py に移すもの

プロンプト作成を移します。

```python
def build_answer_prompt(
    question: str,
    notes: list[dict],
    max_note_chars: int = 1200,
    strict_grounding: bool = True,
) -> str:
    note_blocks = []
    for note in notes:
        content = str(note.get("content", ""))[:max_note_chars]
        note_blocks.append(f"[{note['id']}]\n{content}")

    grounding_rule = (
        "資料に書かれていないことは、推測せず『資料からは分かりません』と答えてください。"
        if strict_grounding
        else "資料を優先し、不足する部分は一般知識で補っても構いません。"
    )

    return f"""あなたは研究補助AIです。
以下の資料だけを根拠にして、ユーザーの質問に日本語で答えてください。
{grounding_rule}

資料:
{chr(10).join(note_blocks)}

質問:
{question}
"""
```

## 分割時の注意

相対 import を使います。

```python
from .store import NoteStore
from .search import search_notes
from .prompts import build_answer_prompt
```

直接 `python main.py` で実行するファイルではないので、AstrBot プラグインでは相対 import が自然です。

## 動作確認

分割した後、以前と同じ確認をします。

```text
/research help
/research add Transformer は attention を使います。
/research list
/research ask attention とは？
/research clear --confirm
```

分割前と同じ動きをすれば成功です。

## よくある失敗

### ImportError が出る

`from store import ...` ではなく `from .store import ...` にします。

### 関数名が変わって呼べない

移動前と移動後で名前が一致しているか確認します。

### 循環 import になる

`store.py` や `search.py` から `main.py` を import しないようにします。

## このステップの完了条件

- `main.py` が AstrBot の入口として読みやすい。
- 保存処理が `store.py` にある。
- 検索処理が `search.py` にある。
- プロンプト作成が `prompts.py` にある。
- 分割前と同じ動作をする。

## コードを詳しく読む

リファクタリングとは、外から見た動作を変えずに、内部のコードを読みやすく直すことです。

つまり、以下は変えてはいけません。

```text
/research add の使い方
/research list の表示
/research ask の結果
/research clear の動作
```

変えるのは、コードの置き場所です。

## なぜファイルを分けるのか

`main.py` に全部書くと、最初は分かりやすいです。しかし、機能が増えると次の問題が出ます。

- どこに保存処理があるか探しにくい。
- 検索だけ直したいのに LLM 部分も目に入る。
- プロンプト文が長くてコマンド処理が読みにくい。
- バグの範囲を絞りにくい。

そこで役割ごとに分けます。

```text
main.py: AstrBot との接続
store.py: 保存
search.py: 検索
prompts.py: プロンプト
```

## import の意味

```python
from .store import NoteStore
```

先頭の `.` は「同じプラグインパッケージ内の」という意味です。

AstrBot プラグインでは、`main.py` は単体スクリプトではなくパッケージの一部として読み込まれるため、相対 import を使います。

## クラスにするか関数にするか

`store.py` はクラスに向いています。

```python
class NoteStore:
    def __init__(self, notes_file: Path):
        self.notes_file = notes_file
```

理由は、保存先ファイルという状態を持つからです。

`search.py` は最初は関数で十分です。

```python
def search_notes(question: str, notes: list[dict], top_k: int = 3) -> list[dict]:
```

理由は、検索は入力を受け取って結果を返すだけで、状態を持たなくてもよいからです。

## 周辺知識: 凝集度

開発では「関係あるものを近くに置く」ことが大事です。これを凝集度が高いと言います。

良い分け方です。

```text
store.py に保存関係だけある
search.py に検索関係だけある
prompts.py にプロンプト関係だけある
```

悪い分け方です。

```text
utils.py に保存、検索、プロンプト、LLM、削除が全部ある
```

`utils.py` は便利そうですが、何でも置き場になりやすいので注意します。

## 周辺知識: リファクタリングの安全な進め方

一気に全部分けると壊れやすいです。

おすすめ順です。

1. `store.py` だけ作る。
2. 動作確認する。
3. `search.py` だけ作る。
4. 動作確認する。
5. `prompts.py` だけ作る。
6. 動作確認する。

小さく分けて確認すると、どこで壊れたか分かります。

## 開発者の考え方

リファクタリングは「きれいにするため」だけではありません。次の機能を安全に追加するためです。

たとえば embedding 検索を追加するとき、検索処理が `search.py` に分かれていれば、`main.py` を大きく壊さずに変更できます。

本物の開発者は、今の機能だけでなく、次に変更しやすい形も考えます。
