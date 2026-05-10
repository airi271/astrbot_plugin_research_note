# Architecture Overview

![Architecture](https://img.shields.io/badge/Diagram-Architecture-0969da)
![RAG](https://img.shields.io/badge/Flow-Fixed%20RAG-1a7f37)
![Agent](https://img.shields.io/badge/Flow-Agent%20Modes-8250df)
![Storage](https://img.shields.io/badge/Backend-JSON%20%2F%20SQLite-bf8700)

このページでは、Research Note Plugin の構造と処理の流れを図で説明します。

プログラミングに詳しくない方でも追えるように、「何を入力し、どこに保存し、どの資料を使って AI が答えるのか」を中心に説明します。

> **このページの読み方**
>
> まず全体像で plugin の位置づけを確認し、その後に Fixed RAG、Import、Storage、Agent、Multi-Agent の順で読むと、実際の動きが追いやすくなります。

## Diagram Index

| 図 | 何が分かるか | 対応する主なコマンド |
| --- | --- | --- |
| [全体像](#全体像) | plugin、保存先、LLM、外部 tool の関係 | 全体 |
| [Fixed RAG](#fixed-rag) | 検索してから回答する基本 flow | `/research ask`, `/research search` |
| [Import And Storage](#import-and-storage) | 資料を取り込み、chunk と embedding を作る流れ | `/research add`, `/research import` |
| [Storage Backend](#storage-backend) | JSON / SQLite の保存先と backup | `/research backup` |
| [Agent Modes](#agent-modes) | agent / web / mcp の違い | `/research agent*` |
| [Multi-Agent](#multi-agent) | Retriever / Reader / Writer / Critic の役割 | `/research agent_multi` |

## 全体像

> **見るポイント:** Research Note は、チャット、保存済み資料、LLM、外部 tool の間に入り、資料に基づく調査 flow を作ります。

![Research Note Architecture](./research_note_architecture.svg)

<span style="color:#0969da"><strong>この図は、Research Note Plugin 全体の構成を示したものです。</strong></span>

左側の `User Side` は、ユーザーが Slack や Telegram などから `/research ...` というコマンドを送る入口です。

中央の `AstrBot Core` は、チャットから来たコマンドを plugin に渡す部分です。Research Note は AstrBot の plugin として動いています。

中央右の `Research Note Plugin` が、この plugin の本体です。ここで資料の追加、資料の検索、質問への回答、import、agent 実行などを処理します。

右上の `LLM Providers` は、回答文を生成する chat model と、文章を検索用のベクトルに変換する embedding model です。

左下の `Research Storage` は、保存済み資料の置き場所です。現在は `research_notes.json` または `research_notes.sqlite3` を選べます。

右下の `External Research` は、Web Search、ページ抽出、AstrBot Knowledge Base、ファイル読み取り、Python 実行などの外部 tool です。常にすべてを使うのではなく、設定で許可したものだけを agent に渡します。

<span style="color:#1a7f37"><strong>この図で一番大事なのは、Research Note が「資料を保存する場所」と「資料に基づいて AI に答えさせる入口」の両方を担当している点です。</strong></span>

## Fixed RAG

> **見るポイント:** agent のように自由に tool を選ぶのではなく、検索してから回答する決まった流れです。

![Fixed RAG Flow](./flow_fixed_rag.svg)

<span style="color:#0969da"><strong>この図は、`/research ask` と `/research search` の動きです。</strong></span>

`/research search <query>` は、AI に回答文を作らせず、保存済み資料の中から近い chunk を探して表示します。

`/research ask <question>` は、まず保存済み資料から近い chunk を探し、その結果を AI に渡して回答を生成します。

検索では `embedding` を使います。embedding とは、文章の意味を数字のリストに変換したものです。似た意味の文章は、数字の距離も近くなります。

<span style="color:#cf222e"><strong>この plugin は keyword fallback を使いません。</strong></span> 単語の一致だけで無理に探すのではなく、embedding が作れない場合や保存済み chunk に embedding がない場合は、エラーとして分かるようにしています。

各ノードの意味です。

- <strong>`User command`</strong>: ユーザーが `/research ask ...` または `/research search ...` を送ります。
- <strong>`Extract query`</strong>: `/research ask` などの命令部分を除いて、本当に調べたい文章だけを取り出します。
- <strong>`Embedding model`</strong>: 質問文を embedding という数字のリストに変換します。
- <strong>`Load chunks`</strong>: JSON または SQLite に保存されている Document / Chunk を読みます。
- <strong>`Embedding search`</strong>: 質問の embedding と chunk の embedding を比べて、意味が近い資料を探します。
- <strong>`Search output`</strong>: `/research search` の場合は、ここで score、title、doc_id、chunk_id を表示して終わります。
- <strong>`Context pack`</strong>: `/research ask` の場合は、見つかった資料を短く整え、AI に渡す参考資料セットを作ります。
- <strong>`LLM prompt`</strong>: AI に「この資料に基づいて答えて」「参考文献を付けて」「分からないことは不明点にして」と指示します。
- <strong>`Grounded answer`</strong>: AI が根拠付きで回答し、本文中に `[1]` のような番号を付け、最後に参考文献を出します。

`/research ask` の最後では、AI に `参考文献` と `不明点` を含む prompt を渡します。これにより、根拠がある内容と分からない内容を分けて答えさせます。

<span style="color:#8250df"><strong>この流れはもっとも基本的な使い方です。</strong></span> agent より単純で、動作を予測しやすいです。

## Import And Storage

> **見るポイント:** 保存前に preview / confirm を挟み、保存する時は Document / Chunk / embedding をまとめて作ります。

![Import and Storage Flow](./flow_import_storage.svg)

<span style="color:#0969da"><strong>この図は、資料を保存する流れです。</strong></span>

`/research add <text>` は、ユーザーが貼り付けた文章をそのまま保存するコマンドです。

`/research import text <text>` と `/research import url <url>` は、いきなり保存せず、まず preview を作ります。preview では、タイトル、取得元、保存される内容の一部、chunk 数の目安を確認できます。

URL import では、Slack や Markdown 形式の URL も通常の URL に直してから取得します。HTML ページの場合は、title と本文に近い text を取り出します。

preview 後に <strong>`/research import confirm <pending_id>` を実行した時だけ</strong>、資料として保存されます。confirm するまでは `pending_imports.json` に一時的に置かれます。

保存時には、まず Document を作ります。Document は資料1件分の情報で、`doc_001` のような ID、title、source_uri、作成日時などを持ちます。

次に本文を Chunk に分けます。Chunk は検索しやすい短い文章の単位です。長い資料をそのまま扱うより、chunk に分ける方が根拠の位置を示しやすくなります。

その後、<span style="color:#1a7f37"><strong>すべての chunk に embedding を作ります。</strong></span> 全 chunk の embedding 作成に成功した場合だけ保存します。途中で失敗した場合は、その資料は保存しません。

保存先は設定により JSON または SQLite です。どちらを選んでも、plugin のコマンドの使い方は同じです。

## Storage Backend

> **見るポイント:** コマンドの使い方は同じまま、保存先だけを JSON または SQLite に切り替えます。

![Storage Backend Flow](./flow_storage_backend.svg)

<span style="color:#0969da"><strong>この図は、資料の保存先を選ぶ流れです。</strong></span>

plugin 起動時に `storage_backend` を読みます。設定がない場合は `json` です。

`storage_backend` が `json` の場合、保存先は以下です。

```text
data/research_notes.json
```

JSON は普通のテキストファイルなので、人間が中身を直接確認しやすいです。資料数が少ないうちは分かりやすい保存方法です。

`storage_backend` が `sqlite` の場合、保存先は以下です。

```text
data/research_notes.sqlite3
```

SQLite は1つのデータベースファイルです。現在の実装では `documents` table と `chunks` table に、Document と Chunk の JSON を保存します。

JSON と SQLite は内部の保存方法が違いますが、plugin からは同じ `load_store`、`save_store`、`create_backup` で扱います。そのため、<strong>`/research add` や `/research ask` の使い方は変わりません。</strong>

`/research backup` を実行すると、現在使っている backend の backup が `data/backups` に作られます。

## Agent Modes

> **見るポイント:** 3つの agent は順番に動くものではなく、ユーザーが選んだ mode だけが実行されます。

![Agent Modes Flow](./flow_agent_modes.svg)

<span style="color:#0969da"><strong>この図は、3種類の agent mode の違いを示しています。</strong></span>

`/research agent <task>` は、Research Note 内の tool だけを使う agent です。保存済み資料の検索、document の確認、一覧表示、明示された場合の保存や削除ができます。

`/research agent_web <task>` は、Research Note tools に加えて、許可済み Web Search tool を使える agent です。設定の `enable_web_research` が true の時だけ使えます。

`/research agent_mcp <task>` は、Research Note tools に加えて、許可済み MCP tool や AstrBot builtin tool を使える agent です。設定の `enable_mcp_research` が true の時だけ使えます。

<span style="color:#cf222e"><strong>3つの agent は順番に実行されるものではありません。</strong></span> ユーザーが選んだコマンドに応じて、どれか1つの mode が動きます。

agent の中では <strong>`tool_loop_agent`</strong> が使われます。これは、AI が「資料を探す必要がある」と判断した時に `research_search` などの tool を呼び、その結果を見て回答を作るための仕組みです。

外部 tool は便利ですが、ファイルや外部 API に触れる可能性があります。そのため Web/MCP 系は通常 agent とは分け、<strong>設定で許可したものだけ</strong>を渡します。

保存と削除は安全ルールがあります。`research_add_text` はユーザーが明確に保存を頼んだ時だけ使い、`research_delete_document` は `doc_id` と `confirm_doc_id` が一致した時だけ削除します。

## Multi-Agent

> **見るポイント:** 1つの回答をいきなり作るのではなく、調査、読解、執筆、批判的確認を役割分担します。

![Multi-Agent Flow](./flow_multi_agent.svg)

<span style="color:#0969da"><strong>この図は、`/research agent_multi <task>` の動きです。</strong></span>

<strong>Multi-Agent</strong> は、1つの AI にすべてを任せるのではなく、<span style="color:#8250df"><strong>役割を分けて順番に処理</strong></span>します。

最初の <strong>`Retriever`</strong> は、調査材料を集める役割です。ここだけ `tool_loop_agent` を使い、Research Note tools、許可済み builtin tools、MCP tools、必要なら作成系 tools を使えます。

次の `Reader` は、Retriever が集めた材料を読み、重要な主張、比較点、矛盾、不明点を整理します。

次の `Writer` は、Reader の整理をもとに draft answer を作ります。

次の `Critic` は、draft answer に根拠不足、引用不足、資料にない断定、矛盾の見落としがないか確認します。

最後の `Final Writer` は、Critic の指摘を反映して最終回答を作ります。

この flow は `Retriever -> Reader -> Writer -> Critic -> Final Writer` の順番です。

`show_multi_agent_trace` を true にすると、最終回答だけでなく、途中の Retriever、Reader、Draft、Critique も出力に含まれます。

`enable_multi_agent_creation_tools` が true の場合、Python 実行やファイル作成などの creation tools も Retriever に追加できます。強力な機能なので、必要な時だけ使う想定です。

## 実装との照合メモ

このページの図は、以下の実装に合わせています。

- Commands: `main.py` の `/research add/list/show/ask/agent/agent_web/agent_mcp/agent_multi/import/search/delete/reindex/backup/clear`
- Tools: `research_search`、`research_get_document`、`research_list_documents`、`research_add_text`、`research_delete_document`
- Search: `search.py` と `tool_utils.py` の embedding-only cosine similarity
- Storage: `store.py` の `NoteStore` と `SQLiteNoteStore`
- Import: `pending_imports.py` と `importers/url_importer.py`
- Agent prompts: `agent_prompts.py`

## 守っている方針

- 保存済み資料は Document と Chunk に分けます。
- 保存する chunk には embedding を作ります。
- 検索は embedding-only です。
- Web/MCP/tool の外部情報は、保存済み資料と区別します。
- 外部情報は勝手に保存せず、import confirm または明示的な保存依頼を使います。
- 削除は確認付きで行います。
