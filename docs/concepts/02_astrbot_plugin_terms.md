# AstrBot Plugin Terms

このファイルでは、AstrBot プラグイン開発で出てくる用語を説明します。

## AstrBot

AstrBot は、複数のチャットプラットフォームで動く AI bot フレームワークです。

あなたが作る Research Note は、AstrBot の中で動く追加機能です。

## Plugin / Star

AstrBot では、プラグインを `Star` と呼ぶことがあります。

コードでは以下のように書きます。

```python
class ResearchNotePlugin(Star):
```

これは「Research Note は AstrBot プラグインです」という意味です。

## main.py

AstrBot プラグインでは、`main.py` が入口です。

AstrBot はプラグインを読み込むとき、基本的にこのファイルを見ます。

そのため、最初に作るべきファイルは `main.py` です。

## metadata.yaml

プラグインの情報を書くファイルです。

```yaml
name: astrbot_plugin_research_note
display_name: Research Note
desc: Research Note plugin for AstrBot
version: v1.0.0
author: airi271
```

これはコードの動作そのものより、AstrBot WebUI やプラグイン管理で表示される情報に関係します。

## _conf_schema.json

プラグインの設定項目を定義するファイルです。

たとえば以下です。

```json
{
  "top_k": {
    "description": "質問時に使う関連資料の数",
    "type": "int",
    "default": 3
  }
}
```

AstrBot はこのファイルを読んで、設定画面や設定値を作ります。

## @register

`@register` は、クラスを AstrBot プラグインとして登録します。

```python
@register("research_note", "airi271", "Research note assistant", "0.1.0")
class ResearchNotePlugin(Star):
```

これがないと、AstrBot がプラグインとして認識できない可能性があります。

## Context

`Context` は、プラグインから AstrBot 本体の機能を使うための窓口です。

```python
def __init__(self, context: Context):
    super().__init__(context)
```

後で以下のようなことに使います。

- 現在の LLM provider を取得する。
- LLM を呼び出す。
- embedding provider を取得する。
- AstrBot の設定や機能にアクセスする。

## event

`event` は、ユーザーから届いたメッセージに関する情報です。

```python
async def research_help(self, event: AstrMessageEvent):
```

`event` から取れるものの例です。

```python
event.get_sender_name()
event.message_str
event.unified_msg_origin
```

意味は以下です。

- `get_sender_name()`: 送信者名。
- `message_str`: ユーザーが送った文字列。
- `unified_msg_origin`: 会話を識別する ID。

## filter

`filter` は、どのイベントやコマンドに反応するかを定義するために使います。

```python
@filter.command("research_hello")
```

これは `/research_hello` に反応します。

```python
@filter.command_group("research")
```

これは `/research ...` の親コマンドを作ります。

```python
@filter.on_llm_request()
```

これは LLM にリクエストを送る直前に呼ばれます。

## command

ユーザーが明示的に送る命令です。

例です。

```text
/research help
/research add 資料本文
/research ask 質問
```

コマンドは、ユーザーが「今この機能を使いたい」と明示する操作です。

## event hook

イベントフックは、AstrBot の処理の途中に自動で呼ばれる関数です。

例です。

```python
@filter.on_llm_request()
async def on_request(self, event, req):
    ...
```

これはユーザーが明示的に `/on_request` と送るものではありません。AstrBot が LLM に送る前に自動で呼びます。

## Provider

Provider は、LLM や embedding などのサービス提供元です。

LLM provider は、文章を生成します。

Embedding provider は、文章をベクトルに変換します。

Research Note では、最初は LLM provider を使います。後で embedding provider を使います。

## ProviderRequest

LLM に送るリクエスト情報です。

`@filter.on_llm_request()` で受け取ることがあります。

中には以下のような情報があります。

- `req.prompt`: ユーザーの質問。
- `req.system_prompt`: システム指示。
- `req.contexts`: 会話履歴。

Mnemosyne はこの `req.prompt` や `req.system_prompt` に長期記憶を追加しています。

## LLMResponse

LLM から返ってきた回答です。

```python
llm_resp.completion_text
```

で回答テキストを取り出せます。

## plain_result

ユーザーに普通のテキストを返すための結果です。

```python
yield event.plain_result("Hello")
```

これは「チャットに `Hello` と送ってください」という意味です。

## なぜ AstrBot 独自の形があるのか

普通の Python スクリプトなら `print()` で画面に出せます。

しかし AstrBot はチャット bot です。返事はターミナルではなく、チャットに送る必要があります。

そのため、`print()` ではなく以下を使います。

```python
yield event.plain_result("返信内容")
```

AstrBot がこの結果を受け取り、実際のチャットプラットフォームへ送信します。
