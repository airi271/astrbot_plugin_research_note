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

## 実装例

ここからは、迷ったときにそのまま近い形で使えるコード例です。

この Phase は「大きな設計変更」ではなく、「今ある note-level RAG を壊れにくくする」段階です。Document / Chunk 化は Phase 2 で行うので、ここでは JSON の `note` 形式を維持します。

### main.py の形

`main.py` は AstrBot との接続、コマンド、入力チェックだけを担当します。

重要な点です。

- `helloworld` などのテンプレートコマンドは消します。
- `/research add` は本文を取り出してから embedding を作ります。
- `/research show note_001` と `/research show 001` の両方を受けられるようにします。
- `/research delete note_001 --confirm` の順番にします。
- `/research reindex` で既存 note の embedding を作り直します。
- debug prompt は `show_debug_prompt` が true のときだけ表示します。

```python
from datetime import datetime
from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .prompts import build_answer_prompt
from .search import search_notes, search_notes_by_embedding
from .store import NoteStore


@register(
    "ResearchNote",
    "airi271",
    "Research note assistant for source-grounded question answering.",
    "0.1.0",
)
class ResearchNotePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.data_dir = Path(__file__).parent / "data"
        self.notes_file = self.data_dir / "research_notes.json"
        self.store = NoteStore(self.notes_file)

    def _next_note_id(self, notes: list[dict]) -> str:
        max_num = 0
        for note in notes:
            note_id = str(note.get("id", ""))
            if not note_id.startswith("note_"):
                continue
            try:
                max_num = max(max_num, int(note_id.removeprefix("note_")))
            except ValueError:
                continue
        return f"note_{max_num + 1:03d}"

    def _normalize_note_id(self, note_id: str) -> str:
        note_id = note_id.strip()
        if not note_id:
            return ""
        if note_id.startswith("note_"):
            return note_id
        return f"note_{note_id}"

    def _extract_research_tail(self, event: AstrMessageEvent) -> str:
        raw_text = event.message_str.strip().removeprefix("/").strip()
        for prefix in (
            "research add",
            "research ask",
            "research show",
            "research delete",
        ):
            if raw_text.startswith(prefix):
                return raw_text[len(prefix) :].strip()
        return ""

    def _get_embedding_provider(self):
        providers = self.context.get_all_embedding_providers()
        if not providers:
            return None
        return providers[0]

    async def initialize(self):
        """Optional async initialization hook."""

    @filter.command_group("research")
    def research_group(self):
        """Research Note commands."""
        pass
```

`help` は、実際に使えるコマンドだけを表示します。

```python
    @research_group.command("help")
    async def research_help(self, event: AstrMessageEvent):
        """Research Note の使い方を表示します。"""
        text = """Research Note commands:
    /research add <text> - 資料を追加
    /research list - 資料一覧
    /research show <note_id> - 指定した資料を表示
    /research ask <question> - 資料に基づいて質問
    /research delete <note_id> --confirm - 指定した資料を削除
    /research reindex - 既存資料の embedding を再作成
    /research clear --confirm - 全資料を削除
    /research help - このヘルプを表示
    """
        yield event.plain_result(text)
```

`add` は、本文チェック、長さチェック、embedding 作成、保存の順にします。

```python
    @research_group.command("add")
    async def research_add(self, event: AstrMessageEvent, content: str = ""):
        """資料を追加します。"""
        content = self._extract_research_tail(event) or content.strip()
        if not content:
            yield event.plain_result("追加する資料テキストを入力してください。")
            return

        max_add_chars = int(self.config.get("max_add_chars", 8000))
        if len(content) > max_add_chars:
            yield event.plain_result(f"資料が長すぎます。最大 {max_add_chars} 文字までです。")
            return

        embedding = None
        embedding_provider = self._get_embedding_provider()
        if embedding_provider:
            embedding = await embedding_provider.get_embedding(content)

        notes = self.store.load_notes()
        note = {
            "id": self._next_note_id(notes),
            "content": content,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "embedding": embedding,
        }
        notes.append(note)
        self.store.save_notes(notes)

        yield event.plain_result(f"資料を保存しました: {note['id']}")
```

`show` は、存在確認、metadata、embedding の有無を出します。

```python
    @research_group.command("show")
    async def research_show(self, event: AstrMessageEvent, note_id: str = ""):
        """保存済み資料を表示します。"""
        note_id = self._normalize_note_id(note_id or self._extract_research_tail(event))
        if not note_id:
            yield event.plain_result("資料IDを指定してください。")
            return

        notes = self.store.load_notes()
        if not notes:
            yield event.plain_result("保存済み資料はありません。")
            return

        note = next((n for n in notes if n.get("id") == note_id), None)
        if not note:
            yield event.plain_result("指定された資料が見つかりません。")
            return

        has_embedding = isinstance(note.get("embedding"), list)
        yield event.plain_result(
            f"資料: {note['id']}\n"
            f"作成日時: {note.get('created_at', 'unknown')}\n"
            f"embedding: {'あり' if has_embedding else 'なし'}\n\n"
            f"内容:\n{note.get('content', '')}"
        )
```

`ask` は、embedding 検索できない場合や結果が空の場合に keyword search へ戻します。

```python
    @research_group.command("ask")
    async def research_ask(self, event: AstrMessageEvent, question: str = ""):
        """資料に基づいて質問します。"""
        question = self._extract_research_tail(event) or question.strip()
        if not question:
            yield event.plain_result("質問を入力してください。")
            return

        notes = self.store.load_notes()
        if not notes:
            yield event.plain_result("保存済み資料がありません。先に /research add で資料を追加してください。")
            return

        top_k = int(self.config.get("top_k", 3))
        embedding_provider = self._get_embedding_provider()
        if not embedding_provider:
            matched_notes = search_notes(question, notes, top_k=top_k)
        else:
            query_embedding = await embedding_provider.get_embedding(question)
            matched_notes = search_notes_by_embedding(query_embedding, notes, top_k=top_k)
            if not matched_notes:
                matched_notes = search_notes(question, notes, top_k=top_k)

        if not matched_notes:
            yield event.plain_result("関連する資料が見つかりませんでした。")
            return

        prompt = build_answer_prompt(
            question,
            matched_notes,
            max_note_chars=int(self.config.get("max_note_chars", 1200)),
            strict_grounding=self.config.get("strict_grounding", True),
        )
        try:
            provider_id = await self.context.get_current_chat_provider_id(
                umo=event.unified_msg_origin
            )
        except Exception:
            logger.error("Failed to get current chat provider.", exc_info=True)
            yield event.plain_result("利用可能な LLM provider が見つかりません。")
            return

        llm_resp = await self.context.llm_generate(
            chat_provider_id=provider_id,
            prompt=prompt,
        )
        answer = llm_resp.completion_text if llm_resp else "回答を生成できませんでした。"
        source_ids = ", ".join(note["id"] for note in matched_notes)
        result = f"{answer}\n\n使用資料: {source_ids}"
        if self.config.get("show_debug_prompt", False):
            result += f"\n\nprompt:\n{prompt}"
        yield event.plain_result(result)
```

`delete` は、必ず `--confirm` を要求します。

```python
    @research_group.command("delete")
    async def research_delete(
        self,
        event: AstrMessageEvent,
        note_id: str = "",
        confirm: str | None = None,
    ):
        """保存済み資料を削除します。"""
        raw_tail = self._extract_research_tail(event)
        if confirm != "--confirm":
            if raw_tail.endswith("--confirm"):
                confirm = "--confirm"
            else:
                yield event.plain_result("削除するには /research delete <note_id> --confirm を実行してください。")
                return

        note_id = self._normalize_note_id(
            note_id or raw_tail.replace("--confirm", "").strip()
        )
        if not note_id:
            yield event.plain_result("資料IDを指定してください。")
            return

        notes = self.store.load_notes()
        if not notes:
            yield event.plain_result("保存済み資料はありません。")
            return

        new_notes = [note for note in notes if note.get("id") != note_id]
        if len(new_notes) == len(notes):
            yield event.plain_result("指定された資料が見つかりません。")
            return

        self.store.save_notes(new_notes)
        yield event.plain_result(f"資料を削除しました: {note_id}")
```

`reindex` は、既存 note の embedding を作り直します。

```python
    @research_group.command("reindex")
    async def research_reindex(self, event: AstrMessageEvent):
        """既存資料の embedding を再作成します。"""
        embedding_provider = self._get_embedding_provider()
        if not embedding_provider:
            yield event.plain_result("embedding provider が設定されていません。")
            return

        notes = self.store.load_notes()
        if not notes:
            yield event.plain_result("保存済み資料はありません。")
            return

        updated = 0
        for note in notes:
            content = str(note.get("content", ""))
            if not content:
                continue
            note["embedding"] = await embedding_provider.get_embedding(content)
            updated += 1

        self.store.save_notes(notes)
        yield event.plain_result(f"embedding を再作成しました: {updated} 件")
```

`clear` は全削除なので、こちらも `--confirm` を要求します。

```python
    @research_group.command("clear")
    async def research_clear(self, event: AstrMessageEvent, confirm: str | None = None):
        """保存済み資料をすべて削除します。"""
        if confirm != "--confirm":
            yield event.plain_result("削除するには /research clear --confirm を実行してください。")
            return
        self.store.save_notes([])
        yield event.plain_result("保存済み資料をすべて削除しました。")

    async def terminate(self):
        """Optional async cleanup hook."""
```

### store.py の形

`store.py` は JSON の読み書きだけを担当します。

```python
import json
from pathlib import Path

from astrbot.api import logger


class NoteStore:
    def __init__(self, notes_file: Path):
        self.notes_file = notes_file
        self.notes_file.parent.mkdir(parents=True, exist_ok=True)

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

    def save_notes(self, notes: list[dict]) -> None:
        tmp_file = self.notes_file.with_suffix(".json.tmp")
        with tmp_file.open("w", encoding="utf-8") as f:
            json.dump(notes, f, ensure_ascii=False, indent=2)
        tmp_file.replace(self.notes_file)
```

### _conf_schema.json の追加項目

`show_debug_prompt` を追加します。

```json
{
  "show_debug_prompt": {
    "description": "回答に実際の prompt を表示する",
    "type": "bool",
    "default": false
  }
}
```

既存の `_conf_schema.json` に追加するときは、前の項目の最後に `,` が必要です。

```json
  "strict_grounding": {
    "description": "資料にないことを推測しないよう強く指示する",
    "type": "bool",
    "default": true
  },
  "show_debug_prompt": {
    "description": "回答に実際の prompt を表示する",
    "type": "bool",
    "default": false
  }
```

### チェック方法

Python の構文だけなら以下で確認できます。

```bash
python3 -m py_compile main.py store.py search.py prompts.py
```

AstrBot の開発環境で `ruff` が使える場合は、以下も実行します。

```bash
ruff format main.py store.py search.py prompts.py
ruff check main.py store.py search.py prompts.py
```
