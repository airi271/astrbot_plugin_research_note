# Code English Glossary

このファイルは、コードの中に出てくる英語を読むための用語集です。

プログラミングでは英語の単語がたくさん出ます。全部を英語として完璧に読める必要はありません。まずは「この単語はコードの中で何を表しているか」を覚えれば十分です。

## まず覚える読み方

コードの英語は、普通の英文とは少し違います。

たとえば以下です。

```python
def load_notes():
    ...
```

これは英文ではありません。開発者は以下のように読みます。

```text
load: 読み込む
notes: ノート、資料メモ
load_notes: ノートを読み込む処理
```

コードの名前は、だいたい以下の形です。

```text
動詞 + 名詞
```

例です。

```text
load_notes: ノートを読み込む
save_notes: ノートを保存する
search_notes: ノートを検索する
build_prompt: プロンプトを組み立てる
```

## よく出る動詞

### load

意味: 読み込む。

```python
notes = self._load_notes()
```

読み方: 保存されている資料を読み込んで `notes` に入れる。

### save

意味: 保存する。

```python
self._save_notes(notes)
```

読み方: `notes` をファイルに保存する。

### add

意味: 追加する。

```python
async def research_add(self, event, content: str):
```

読み方: 研究資料を追加するコマンド。

### append

意味: リストの最後に追加する。

```python
notes.append(note)
```

読み方: `notes` の最後に `note` を追加する。

### list

意味: 一覧表示する。またはリスト型。

```python
async def research_list(...):
```

これは「資料一覧を表示するコマンド」です。

```python
notes: list[dict]
```

これは「辞書が入ったリスト」という型です。

### ask

意味: 質問する。

```python
async def research_ask(self, event, question: str):
```

読み方: Research Note に質問するコマンド。

### clear

意味: 消す、空にする。

```python
async def research_clear(...):
```

読み方: 保存済み資料を空にするコマンド。

### delete

意味: 削除する。

`clear` は全体を空にする感じ、`delete` は特定の1件を削除する感じで使われることが多いです。

### remove

意味: 取り除く。

`delete` と似ていますが、「リストや文字列から取り除く」という場面でよく出ます。

### get

意味: 取得する。

```python
event.get_sender_name()
```

読み方: 送信者名を取得する。

### set

意味: 設定する、セットする。

```python
self.config = config
```

直接 `set` という単語がなくても、「値を入れる」ことを set と言います。

### build

意味: 組み立てる、作る。

```python
prompt = self._build_answer_prompt(question, matched_notes)
```

読み方: 質問と関連資料から、LLM に渡すプロンプトを組み立てる。

### create

意味: 作成する。

`build` は部品から組み立てる感じ、`create` は新しく作る感じです。

### generate

意味: 生成する。

```python
llm_resp = await self.context.llm_generate(...)
```

読み方: LLM に回答を生成させる。

### search

意味: 検索する。

```python
matched_notes = self._search_notes(question, notes, top_k=3)
```

読み方: 質問に合う資料を検索する。

### match

意味: 一致する、合う。

```python
matched_notes
```

意味: 質問に合った資料。

### filter

意味: 条件で絞る。

AstrBot の `filter` は、どのメッセージやイベントに反応するかを決めるものです。

```python
@filter.command("research_hello")
```

### handle

意味: 処理する、対応する。

Mnemosyne には以下のような名前があります。

```python
handle_query_memory
```

読み方: 記憶検索の処理を担当する。

### init / initialize

意味: 初期化する。

```python
def __init__(self, context):
```

`__init__` は Python の特別な初期化メソッドです。

### terminate

意味: 終了する、停止する。

```python
async def terminate(self):
```

プラグインが停止されるときに呼ばれます。

### return

意味: 返す、戻る。

```python
return []
```

読み方: 空のリストを返す。

### yield

意味: 途中で値を渡す。

AstrBot では、返信結果を AstrBot に渡すために使います。

```python
yield event.plain_result("Hello")
```

## よく出る名詞

### note

意味: ノート、メモ、資料1件。

Research Note では、1つの保存資料を `note` と呼びます。

### notes

意味: `note` の複数形。資料リスト。

```python
notes = self._load_notes()
```

### content

意味: 内容、本文。

`/research add` の後ろに書いた資料本文です。

### question

意味: 質問。

`/research ask` の後ろに書いた質問文です。

### answer

意味: 回答。

```python
answer = llm_resp.completion_text
```

### prompt

意味: LLM に渡す指示文。

```python
prompt = self._build_answer_prompt(question, matched_notes)
```

### response / resp

意味: 応答、返答。

`resp` は `response` の略です。

### request / req

意味: リクエスト、要求。

`req` は `request` の略です。

### event

意味: イベント、起きたこと。

AstrBot では、ユーザーからメッセージが来たことを表します。

### context

意味: 文脈、状況、接続窓口。

AstrBot の `Context` は、プラグインが AstrBot 本体とやり取りするための窓口です。

### config

意味: 設定。

```python
self.config.get("top_k", 3)
```

### provider

意味: 提供者。

LLM provider は、LLM 機能を提供するものです。

Embedding provider は、embedding 機能を提供するものです。

### source

意味: 情報源、根拠資料。

```python
source_ids = ", ".join(note["id"] for note in matched_notes)
```

### id

意味: 識別子。

```python
"id": "note_001"
```

どの資料か区別するための名前です。

### path

意味: ファイルやディレクトリの場所。

### file

意味: ファイル。

### dir / directory

意味: ディレクトリ、フォルダ。

`dir` は `directory` の略です。

### schema

意味: 構造、設定項目の定義。

`_conf_schema.json` は、設定の形を定義するファイルです。

### metadata

意味: データについてのデータ。

`metadata.yaml` は、プラグイン名、作者、説明など、プラグインそのものの情報です。

## よく出る形容詞、状態

### current

意味: 現在の。

```python
get_current_chat_provider_id
```

読み方: 現在のチャットで使っている provider ID を取得する。

### default

意味: 初期値、指定がないときの値。

```python
self.config.get("top_k", 3)
```

ここでは `3` が default です。

### plain

意味: 普通の、装飾なしの。

```python
event.plain_result("Hello")
```

普通のテキスト返信という意味です。

### matched

意味: 一致した、合った。

```python
matched_notes
```

質問に合った資料です。

### explicit

意味: 明示的な。

Mnemosyne の `explicit memory capture` は、ユーザーが「覚えて」と明示したときに記憶する機能です。

### manual

意味: 手動の。

```python
store_manual_memory
```

手動で記憶を保存する処理です。

### async

意味: 非同期。

```python
async def research_ask(...):
```

時間がかかる処理を待てる関数です。

## 略語

### req

元の単語: request。意味: リクエスト。

### resp

元の単語: response。意味: 応答。

### config

元の単語: configuration。意味: 設定。

### init

元の単語: initialize / initialization。意味: 初期化。

### dir

元の単語: directory。意味: ディレクトリ。

### db

元の単語: database。意味: データベース。

### llm

元の単語: Large Language Model。意味: 大規模言語モデル。

### rag

元の単語: Retrieval Augmented Generation。意味: 検索で情報を追加してから生成する方法。

### id

元の単語: identifier。意味: 識別子。

## Research Note で出る名前の読み方

### research_help

```text
research: 研究
help: 助け、使い方
research_help: Research Note の使い方を表示する処理
```

### research_add

```text
research: 研究
add: 追加する
research_add: 研究資料を追加する処理
```

### research_list

```text
list: 一覧する
research_list: 研究資料の一覧を表示する処理
```

### research_ask

```text
ask: 質問する
research_ask: 研究資料に基づいて質問する処理
```

### research_clear

```text
clear: 空にする
research_clear: 保存済み資料を消す処理
```

### _load_notes

```text
load: 読み込む
notes: 資料メモたち
_load_notes: 保存済み資料を読み込む内部処理
```

### _save_notes

```text
save: 保存する
notes: 資料メモたち
_save_notes: 資料リストを保存する内部処理
```

### _search_notes

```text
search: 検索する
notes: 資料メモたち
_search_notes: 質問に合う資料を探す内部処理
```

### _build_answer_prompt

```text
build: 組み立てる
answer: 回答
prompt: LLM への指示文
_build_answer_prompt: 回答用のプロンプトを組み立てる内部処理
```

### matched_notes

```text
matched: 合った
notes: 資料メモたち
matched_notes: 質問に合った資料リスト
```

### source_ids

```text
source: 情報源
ids: 識別子たち
source_ids: 回答に使った資料 ID 一覧
```

## AstrBot で出る名前の読み方

### AstrMessageEvent

```text
Astr: AstrBot の Astr
Message: メッセージ
Event: 起きたこと
AstrMessageEvent: AstrBot に届いたメッセージイベント
```

### MessageEventResult

```text
Message: メッセージ
Event: イベント
Result: 結果
MessageEventResult: メッセージイベントへの返答結果
```

### plain_result

```text
plain: 普通の
result: 結果
plain_result: 普通のテキスト返信結果
```

### command_group

```text
command: コマンド
group: グループ
command_group: 複数のサブコマンドをまとめる親コマンド
```

### on_llm_request

```text
on: 何かが起きたとき
llm: 大規模言語モデル
request: リクエスト
on_llm_request: LLM へリクエストする直前に呼ばれる処理
```

### on_llm_response

```text
on: 何かが起きたとき
llm: 大規模言語モデル
response: 応答
on_llm_response: LLM から応答が返った後に呼ばれる処理
```

### unified_msg_origin

```text
unified: 統一された
msg: message の略、メッセージ
origin: 起点、出どころ
unified_msg_origin: AstrBot が統一形式で持つ会話の識別子
```

## Python でよく出る英語

### open

意味: 開く。

```python
self.notes_file.open("r", encoding="utf-8")
```

### exists

意味: 存在する。

```python
self.notes_file.exists()
```

### parent

意味: 親。

```python
Path(__file__).parent
```

`main.py` の親ディレクトリです。

### strip

意味: 前後の空白を取り除く。

```python
content = content.strip()
```

### lower

意味: 小文字にする。

```python
text.lower()
```

### replace

意味: 置き換える。

```python
content.replace("\n", " ")
```

改行を空白に置き換えます。

### split

意味: 分割する。

```python
text.split()
```

空白で分割します。

### join

意味: 結合する。

```python
"\n".join(lines)
```

文字列リストを改行で結合します。

### sort

意味: 並び替える。

```python
scored.sort(key=lambda item: item[0], reverse=True)
```

### key

意味: 並び替えや辞書のキー。

`sort` の `key` は「何を基準に並べるか」です。

### reverse

意味: 逆順。

```python
reverse=True
```

大きい順に並べたいときによく使います。

## 英語の名前を読むコツ

### snake_case を分解する

Python では単語を `_` でつなぐことが多いです。

```python
matched_notes
```

これは以下に分けます。

```text
matched + notes
```

### 長い名前は分解する

```python
get_current_chat_provider_id
```

分解します。

```text
get: 取得する
current: 現在の
chat: チャット
provider: 提供者
id: 識別子
```

全体の意味です。

```text
現在のチャットで使っている provider の ID を取得する
```

### `_` で始まる関数は内部用

```python
def _load_notes(self):
```

先頭の `_` は「このクラスやモジュールの内部で使う」という意味の慣習です。

### 複数形に注意する

```python
note
notes
```

`note` は1件、`notes` は複数件です。

## 最初に覚える英単語リスト

優先度が高い順です。

1. get: 取得する。
2. set: 設定する。
3. load: 読み込む。
4. save: 保存する。
5. add: 追加する。
6. list: 一覧。
7. ask: 質問する。
8. clear: 空にする。
9. delete: 削除する。
10. search: 検索する。
11. build: 組み立てる。
12. generate: 生成する。
13. request: リクエスト。
14. response: 応答。
15. event: イベント。
16. context: 文脈、窓口。
17. config: 設定。
18. provider: 提供者。
19. prompt: LLM への指示文。
20. source: 情報源。

この20個が読めるだけで、AstrBot プラグインのコードはかなり読みやすくなります。
