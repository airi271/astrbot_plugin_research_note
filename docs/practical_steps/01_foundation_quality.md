# 01 Foundation Quality: 実用品質の土台作り

この Phase では、学習用に動いている Research Note を、壊れにくい実用品質へ近づけます。

新機能を大きく増やす前に、今ある機能を安全にします。ここを飛ばすと、後で chunk 化、tool 化、agent 化をしたときにバグの原因が分かりにくくなります。

## 目的

この Phase の目的は以下です。

- 使わないテンプレートコードを消す。
- 資料追加時の embedding 作成順を正しくする。
- JSON 保存を壊れにくくする。
- ID が重複しないようにする。
- 資料の表示、削除、再 indexing をできるようにする。
- debug 用 prompt を通常回答に出さないようにする。

## まだ早い場合

以下ができていない場合は、先に `docs/learning_steps` に戻ります。

- `/research add <text>` が動く。
- `/research list` が動く。
- `/research ask <question>` が動く。
- `store.py`、`search.py`、`prompts.py` に分割済み。
- `_conf_schema.json` がある。

## 変更するファイル

主に触るファイルです。

```text
main.py
store.py
search.py
prompts.py
_conf_schema.json
```

テストがあるなら、後で以下も触ります。

```text
tests または test_*.py
```

## 最初に確認すること

作業前に、現在の状態を確認します。

```bash
git status
```

次に、いま動くコマンドを確認します。

```text
/research help
/research add Transformer は attention を使います。
/research list
/research ask attention とは？
```

この Phase は「動作を大きく変えない安全化」です。作業前に動いていたものが、作業後も動くことが大事です。

## Step 1: テンプレートコードを消す

現在の `main.py` には、学習用の `helloworld` と `research_hellow` が残っています。

実用プラグインでは不要なので消します。

消すものです。

- `from click import prompt`
- `import json` など未使用 import
- `@filter.command("helloworld")`
- `@filter.command("research_hellow")`
- 使っていない `MessageEventResult`

消す理由です。

- コマンド一覧が分かりやすくなる。
- どれが本番機能か迷わなくなる。
- lint や format の警告が減る。

## Step 2: add の embedding 作成順を直す

今の実装では、`content` を取り出す前に embedding を作ろうとしています。

悪い順番です。

```python
embedding_provider = self._get_embedding_provider()
if embedding_provider:
    embedding = await embedding_provider.get_embedding(content)
content = self._extract_research_tail(event)
```

`content` がまだ正しく決まっていないので、先に本文を取り出します。

良い順番です。

```python
content = self._extract_research_tail(event)
if not content:
    yield event.plain_result("追加する資料テキストを入力してください。")
    return

embedding = None
embedding_provider = self._get_embedding_provider()
if embedding_provider:
    embedding = await embedding_provider.get_embedding(content)
```

考え方です。

```text
入力を読む
入力を検証する
必要なら embedding を作る
保存する
```

この順番は、今後の import や chunk 化でも同じです。

## Step 3: provider_id 取得のエラーを扱う

`get_current_chat_provider_id` は provider がない場合に例外を出す可能性があります。

`if not provider_id` だけでは足りないことがあります。

安全な形の例です。

```python
try:
    provider_id = await self.context.get_current_chat_provider_id(
        umo=event.unified_msg_origin
    )
except Exception:
    logger.error("Failed to get current chat provider.", exc_info=True)
    yield event.plain_result("利用可能な LLM provider が見つかりません。")
    return
```

実用プラグインでは、ユーザーには短いメッセージを返し、詳細は log に残します。

## Step 4: store.py の logger 引数をなくす

今の `load_notes` は `logger` を引数で受け取っています。

```python
def load_notes(self, logger) -> list[dict]:
```

これは毎回 `logger` を渡す必要があり、呼び出し側が少し面倒です。

store.py で `astrbot.api.logger` を import するか、壊れた場合は例外を出さず空リストを返す形にします。

例です。

```python
from astrbot.api import logger

def load_notes(self) -> list[dict]:
    if not self.notes_file.exists():
        return []
    try:
        with self.notes_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        logger.error("research_notes.json is broken.", exc_info=True)
        return []
    return data if isinstance(data, list) else []
```

呼び出し側はこうなります。

```python
notes = self.store.load_notes()
```

## Step 5: atomic write にする

JSON 保存中に AstrBot が止まると、ファイルが途中までしか書かれず壊れる可能性があります。

そこで、一度 temporary file に書いてから置き換えます。

イメージです。

```python
tmp_file = self.notes_file.with_suffix(".json.tmp")
with tmp_file.open("w", encoding="utf-8") as f:
    json.dump(notes, f, ensure_ascii=False, indent=2)
tmp_file.replace(self.notes_file)
```

この方法だと、保存途中で落ちても本体ファイルが壊れにくくなります。

## Step 6: ID 生成を重複しにくくする

今の ID は `len(notes) + 1` です。

```python
return f"note_{len(notes) + 1:03d}"
```

これは資料を削除したあとに同じ ID が再利用される可能性があります。

簡単な改善案です。

```python
def _next_note_id(self, notes: list[dict]) -> str:
    max_num = 0
    for note in notes:
        note_id = str(note.get("id", ""))
        if note_id.startswith("note_"):
            try:
                max_num = max(max_num, int(note_id.removeprefix("note_")))
            except ValueError:
                continue
    return f"note_{max_num + 1:03d}"
```

将来は `uuid` や `doc_20260507_001` のような ID でもよいです。まずは今の見た目を維持して安全にします。

## Step 7: show と delete を追加する

実用では、一覧だけでは足りません。

追加するコマンドです。

```text
/research show <note_id>
/research delete <note_id> --confirm
```

`show` の役割です。

- 1件の全文または長めの preview を見る。
- created_at や embedding の有無を見る。

`delete` の役割です。

- 間違って追加した資料を消す。
- `--confirm` がない場合は削除しない。

削除は必ず確認を挟みます。

```text
/research delete note_001 --confirm
```

## Step 8: reindex を追加する

embedding 対応前に保存した資料には embedding がありません。

`/research reindex` を作ると、既存資料の embedding を作り直せます。

流れです。

```text
embedding provider を取得する
notes を読み込む
各 note の content から embedding を作る
note["embedding"] に保存する
JSON を保存する
何件更新したか返す
```

provider がない場合は、ユーザーに伝えて終了します。

```text
embedding provider が設定されていません。
```

## Step 9: debug prompt を設定で切り替える

今の `/research ask` は回答の最後に prompt を出しています。

```python
yield event.plain_result(f"{answer}\n\n使用資料: {source_ids}\n\nprompt:\n{prompt}")
```

実用では prompt は普段出さない方がよいです。

`_conf_schema.json` に追加します。

```json
"show_debug_prompt": {
  "description": "回答に実際の prompt を表示する",
  "type": "bool",
  "default": false
}
```

出力側は以下のようにします。

```python
result = f"{answer}\n\n使用資料: {source_ids}"
if self.config.get("show_debug_prompt", False):
    result += f"\n\nprompt:\n{prompt}"
yield event.plain_result(result)
```

## 動作確認

以下を順番に試します。

```text
/research help
/research add Transformer は attention を使います。
/research list
/research show note_001
/research ask attention とは？
/research delete note_001
/research delete note_001 --confirm
/research list
```

embedding provider がある場合は以下も試します。

```text
/research add RAG は検索した資料を LLM に渡して回答する仕組みです。
/research reindex
/research ask 検索して回答する仕組みは？
```

## よくある失敗

### add で空の embedding が保存される

`content = self._extract_research_tail(event)` を embedding より前に置きます。

### delete 後に同じ ID が再利用される

`len(notes) + 1` ではなく、既存 ID の最大値から次の ID を作ります。

### JSON が壊れたあと何も見えない

まず log を見ます。次に、壊れた JSON を手で直すか、backup から戻します。Phase 11 で backup 機能を作ります。

### prompt が毎回出て邪魔

`show_debug_prompt` の default を `false` にします。

## この Phase の完了条件

- 不要な hello world コマンドが消えている。
- `/research add` の embedding 作成順が正しい。
- `store.load_notes()` が logger 引数なしで呼べる。
- 保存が atomic write になっている。
- ID が削除後も重複しにくい。
- `/research show` が使える。
- `/research delete <id> --confirm` が使える。
- `/research reindex` が使える。
- prompt debug が設定で切り替えられる。
- Phase 開始前に動いていた `/research ask` が今も動く。
