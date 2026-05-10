# Research Note for AstrBot 日本語版

![AstrBot Plugin](https://img.shields.io/badge/AstrBot-Plugin-0969da)
![Source Grounded](https://img.shields.io/badge/Source--Grounded-RAG-1a7f37)
![Embedding Search](https://img.shields.io/badge/Search-Embedding--Only-8250df)
![Storage](https://img.shields.io/badge/Storage-JSON%20%2F%20SQLite-bf8700)

> **保存した資料に基づいて検索し、根拠を確認しながら AI に質問するための Research Note plugin です。**
>
> 単発のチャット回答ではなく、資料、検索結果、引用、外部調査をつなげて扱うことを目指しています。

Research Note は、[AstrBot](https://github.com/AstrBotDevs/AstrBot) 上で動く、<span style="color:#0969da"><strong>根拠を確認しながら調査を進める</strong></span>ための研究補助プラグインです。研究メモや資料の抜粋を保存し、関連する箇所を検索し、保存済み資料に基づいて質問に回答できるようにすることを目指しています。

このプラグインは、チャットの中で資料を集め、必要な箇所を探し、根拠を確認しながら AI に質問するための軽量な研究支援ワークフローとして開発しています。保存した資料は <strong>Document</strong> と <strong>Chunk</strong> に分けて扱います。

## Quick Links

| 読みたい内容 | リンク |
| --- | --- |
| 全体構造と機能別 flow 図 | [アーキテクチャ解説](./docs/practical_steps/architecture_overview.md) |
| 実用化ロードマップ | [PRACTICAL_ROADMAP.md](./PRACTICAL_ROADMAP.md) |
| Phase別の実装メモ | [docs/practical_steps/README.md](./docs/practical_steps/README.md) |

## 何が嬉しいのか

| 課題 | Research Note でできること |
| --- | --- |
| チャットに貼った資料が流れていく | 資料を Document / Chunk として保存し、後から検索できます。 |
| AI の回答根拠が見えにくい | doc_id / chunk_id、title、source_uri を使って根拠を追いやすくします。 |
| キーワード検索だけでは関連箇所を拾いにくい | embedding-based semantic search で意味的に近い chunk を探します。 |
| Web Search と保存済み資料が混ざりやすい | external evidence と stored evidence を区別して扱います。 |
| 1回の回答だけでは検証が足りない | Multi-Agent flow で読解、執筆、critique を段階的に行えます。 |

## このプラグインが解決したいこと

Research Note は、AstrBot の会話インターフェース上で、<span style="color:#8250df"><strong>研究資料の整理</strong></span>、<span style="color:#0969da"><strong>意味検索</strong></span>、<span style="color:#1a7f37"><strong>根拠付き回答</strong></span>をまとめて扱うためのプラグインです。チャットに貼った研究メモ、論文・記事の抜粋、Webページ本文、プロジェクト資料は、そのままだと会話の流れの中に埋もれがちです。このプラグインでは、それらを後から検索・参照できる形で保存し、質問応答、比較検討、レビューに使えるようにします。

大規模言語モデルは、単独で使うと回答の根拠が見えにくくなります。特に研究や調査では、<span style="color:#cf222e"><strong>AI hallucination</strong></span>、つまり資料に基づかないもっともらしい生成を見過ごすことが問題になります。Research Note は、<strong>Retrieval-Augmented Generation、いわゆる RAG</strong> の考え方に基づき、回答前に保存済み資料を検索し、関連 chunk を prompt context として LLM に渡します。これにより、回答を保存済み資料に <strong>grounding</strong> し、生成内容と根拠資料の対応関係を追跡しやすくします。

研究・調査作業では、回答が自然であること以上に、<strong>evidence traceability</strong>、<strong>citation</strong>、<strong>source attribution</strong> が重要です。Research Note は doc_id / chunk_id、title、source_uri を回答や検索結果に含めることで、「どの記述が、どの資料の、どの部分に基づいているのか」を後から確認しやすくします。これは <span style="color:#cf222e"><strong>hallucination mitigation</strong></span>、根拠確認、再検証、文献比較、レビュー作業に役立ちます。

主な利点です。

- <strong>Document / Chunk 管理</strong>: 資料を Document と Chunk に分けて保存し、長文資料を retrieval しやすい単位で扱えます。
- <strong>Semantic Search</strong>: embedding-based semantic search により、単純なキーワード一致では拾いにくい関連箇所を検索できます。
- <strong>Grounded Answer</strong>: `/research ask` では、保存済み資料から関連 chunk を選び、grounded answer generation のための context pack を作ります。
- <strong>Citation Support</strong>: 回答や検索結果に doc_id / chunk_id を含めることで、citation と source attribution を確認しやすくします。
- <strong>Retrieval Check</strong>: `/research search` により、LLM に回答させる前に retrieval result を確認でき、検索結果が妥当かを手元で確認できます。
- <strong>Import Control</strong>: import preview / confirm により、外部テキストやURLをすぐに保存せず、内容を確認してから資料として取り込めます。
- <strong>Evidence Separation</strong>: Web Search、MCP、AstrBot builtin tools の結果を、保存済み資料と区別して扱い、external evidence と stored evidence の混同を抑えます。
- <strong>Multi-Agent Review</strong>: Multi-Agent flow では、Retriever、Reader、Writer、Critic の役割を分け、情報収集、読解、執筆、critique を段階的に進められます。
- <strong>Storage Backend</strong>: JSON / SQLite backend を選択でき、資料数が増えた場合の運用も見据えた保存方法を選べます。

<span style="color:#0969da"><strong>このプラグインの価値は、AI に回答を生成させること自体ではなく、回答の前後にある研究プロセスを扱いやすくする点にあります。</strong></span> 資料を保存し、retrieval を行い、根拠を確認し、必要に応じて外部調査や批判的検証へ進むことで、会話型AIを単発の質問応答ではなく、継続的な <strong>source-grounded research workflow</strong> として利用できます。

## 主な機能

- `/research add <text>` で研究資料やメモを保存できます。
- text や HTML ページを preview と confirm 付きで取り込めます。
- 保存した資料を Document と検索用 Chunk に分けて管理できます。
- `/research list` で保存済み資料を一覧できます。
- `/research show <doc_id>` で資料の metadata と chunk preview を確認できます。
- `/research ask <question>` で保存済み資料に基づいて質問できます。
- 有効化した場合、`/research agent_web <task>` で保存済み資料と Web Search を使った調査ができます。
- 有効化した場合、`/research agent_mcp <task>` で保存済み資料と許可済み MCP / AstrBot tools を使った調査ができます。
- 有効化した場合、`/research agent_multi <task>` で Retriever / Reader / Writer / Critic の段階的な調査 flow を使えます。
- embedding provider を使い、全 chunk を embedding 検索対象にします。
- 保存 backend は `json` または `sqlite` を選べます。
- `/research backup` で現在の保存 backend の backup を作れます。
- LLM tool として `research_search`、`research_get_document`、`research_list_documents`、`research_add_text`、`research_delete_document` を登録します。
- `_conf_schema.json` で検索件数や安全設定を変更できます。
- 今後、引用改善、Tool 化、MCP 連携、Multi-Agent 化へ拡張する計画です。

## 現在の状態

現在のバージョンは `v0.1.0` です。

最小構成の Document / Chunk RAG フローが動作します。RAG とは、AI が直接回答するだけでなく、先に関連資料を検索し、その資料をもとに回答する仕組みです。

現在の基本フローです。

```text
資料を追加する -> chunk に分割する -> JSON または SQLite に保存する -> 関連 chunk を検索する -> プロンプトを作る -> LLM に渡す -> 使用資料 ID 付きで回答する
```

実用化に向けた計画は以下にあります。

```text
PRACTICAL_ROADMAP.md
docs/practical_steps/README.md
```

アーキテクチャの概要は以下にあります。

```text
docs/practical_steps/architecture_overview.md
```

## コマンド

```text
/research help
/research add <text>
/research list
/research show <doc_id>
/research show <doc_id> <chunk_index|chunk_id>
/research show <chunk_id>
/research search <query>
/research ask <question>
/research agent <task>
/research agent_web <task>
/research agent_mcp <task>
/research agent_multi <task>
/research import text <text>
/research import url <url>
/research import confirm <pending_id>
/research delete <doc_id> --confirm
/research reindex
/research backup
/research clear --confirm
```

短縮コマンドとして `/research import_text <text>`、`/research import_url <url>`、`/research import_confirm <pending_id>` も使えます。

## 使い方の例

資料を追加します。

```text
/research add RAG は検索した資料を LLM に渡して回答する仕組みです。
```

保存済み資料を確認します。

```text
/research list
```

1件の資料を表示します。

```text
/research show doc_001
```

特定の chunk 本文を表示します。

```text
/research show doc_001 0
/research show chunk_001_000
```

embedding 検索結果を確認します。

```text
/research search RAG とは何ですか？
```

資料に基づいて質問します。

```text
/research ask RAG とは何ですか？
```

Research Note tools を使う agent に依頼します。

```text
/research agent 保存済み資料だけで RAG について整理して
```

Web Search も使う agent に依頼します。事前に `enable_web_research` を有効にしてください。

```text
/research agent_web 保存済み資料にない最新情報を調べて候補を出して
```

MCP / AstrBot tools も使う agent に依頼します。事前に `enable_mcp_research` を有効にしてください。

```text
/research agent_mcp 許可された tool を使って資料候補を探し、保存済み資料と区別して説明して
```

複数 role の固定 flow で調査します。事前に `enable_multi_agent` を有効にしてください。

```text
/research agent_multi Transformer と RAG の違いを比較して
```

text を preview してから取り込みます。

```text
/research import text RAG は検索した資料を LLM に渡して回答する仕組みです。
/research import confirm import_xxxxxxxx
```

URL を preview してから取り込みます。

```text
/research import url https://example.com
/research import confirm import_xxxxxxxx
```

指定した資料を削除します。

```text
/research delete doc_001 --confirm
```

既存資料の embedding を再作成します。

```text
/research reindex
```

現在の保存 backend の backup を作ります。

```text
/research backup
```

資料をすべて削除します。

```text
/research clear --confirm
```

## アーキテクチャ

Research Note を中心にした構造図です。

![Research Note Architecture](./docs/practical_steps/research_note_architecture.svg)

[アーキテクチャ解説と機能別 flow 図を開く](./docs/practical_steps/architecture_overview.md)

図の説明と機能別 flow 図は以下にあります。

```text
docs/practical_steps/architecture_overview.md
```

## 設定

現在の主な設定項目です。

- `top_k`: 質問時に使う関連資料の数。
- `max_note_chars`: 1件の検索結果 chunk からプロンプトに入れる最大文字数。
- `max_add_chars`: 1回で追加できる資料の最大文字数。
- `chunk_size`: 資料を分割する chunk の文字数。
- `chunk_overlap`: 隣り合う chunk で重ねる文字数。
- `min_embedding_score`: 検索結果として採用する最小 embedding score。
- `max_context_chars`: LLM に渡す検索結果全体の最大文字数。
- `agent_max_steps`: research agent が tool を呼ぶ最大ステップ数。
- `agent_tool_call_timeout`: research agent の tool 呼び出し timeout 秒。
- `enable_web_research`: `/research agent_web` で Web Search tool を使うかどうか。
- `allowed_web_tools`: `/research agent_web` に渡す Web Search tool 名。デフォルトは Tavily 系 tool です。
- `enable_mcp_research`: `/research agent_mcp` で MCP / AstrBot builtin tool を使うかどうか。
- `allowed_mcp_tools`: `/research agent_mcp` に渡す MCP tool 名。
- `allowed_builtin_tools`: `/research agent_mcp` に渡す AstrBot builtin tool 名。デフォルトは file read、grep、知識庫検索、Tavily 系 tool です。
- `allow_all_builtin_tools`: `/research agent_mcp` にすべての AstrBot builtin tool を渡すかどうか。
- `denied_builtin_tools`: 全 builtin tool 有効時でも除外する AstrBot builtin tool 名。
- `enable_multi_agent`: `/research agent_multi` で複数 role の調査 flow を使うかどうか。
- `multi_agent_retriever_max_steps`: `agent_multi` の Retriever が tool を呼ぶ最大ステップ数。
- `show_multi_agent_trace`: `agent_multi` の中間結果を出力に含めるかどうか。
- `storage_backend`: 保存 backend。`json` または `sqlite` を指定します。デフォルトは `json` です。
- `enable_multi_agent_creation_tools`: `agent_multi` に Python 実行やファイル作成 tool を追加するかどうか。
- `multi_agent_creation_tools`: `agent_multi` に追加する作成系 tool 名。
- `max_import_chars`: import で取り込む本文の最大文字数。
- `import_preview_chars`: import preview に表示する文字数。
- `import_url_timeout`: URL import の取得 timeout 秒。
- `strict_grounding`: 資料にないことを推測しないよう強く指示するかどうか。
- `show_debug_prompt`: `/research ask` の出力に実際の prompt を表示するかどうか。

## 開発ロードマップ

今後の主な開発予定です。

- 回答に使った根拠資料をより分かりやすく表示する。
- ファイルから資料を取り込めるようにする。
- 回答や保存候補の品質評価を強化する。

## 目指している方向

Research Note は、AI に自由に答えさせるだけではなく、保存済み資料を根拠にして回答する研究補助プラグインを目指しています。

重視している点です。

- 小さく動く機能から始める。
- 資料に基づく回答を優先する。
- 根拠資料を確認できるようにする。
- embedding provider を前提に、検索品質の失敗に気づきやすくする。
- AstrBot の Tool、MCP、Agent 機能と自然に連携できる構造にする。

## 関連ドキュメント

- `README.md`: 英語版 README。
- `LEARNING_ROADMAP.md`: 初期学習ロードマップ。
- `PRACTICAL_ROADMAP.md`: 実用化ロードマップ。
- `docs/learning_steps/README.md`: 初期学習ステップ。
- `docs/practical_steps/README.md`: 実用化ステップ。
- `docs/practical_steps/architecture_overview.md`: アーキテクチャ図の説明。

## 参考

- [AstrBot Repository](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot Plugin Development Docs](https://docs.astrbot.app/en/dev/star/plugin-new.html)
