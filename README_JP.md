# Research Note for AstrBot 日本語版

Research Note は、[AstrBot](https://github.com/AstrBotDevs/AstrBot) 上で動く、根拠付きの研究補助プラグインです。研究メモや資料の抜粋を保存し、関連する内容を検索し、保存済み資料に基づいて質問に回答することを目指しています。

このプラグインは、チャットの中で資料を集め、検索し、根拠を確認しながら AI に質問できる軽量な研究支援ワークフローを作るために開発しています。保存した資料は Document と Chunk に分けて扱います。

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
- LLM tool として `research_search`、`research_get_document`、`research_list_documents`、`research_add_text`、`research_delete_document` を登録します。
- `_conf_schema.json` で検索件数や安全設定を変更できます。
- 今後、引用改善、Tool 化、MCP 連携、Multi-Agent 化へ拡張する計画です。

## 現在の状態

現在のバージョンは `v0.1.0` です。

最小構成の Document / Chunk RAG フローが動作します。RAG とは、AI が直接回答するだけでなく、先に関連資料を検索し、その資料をもとに回答する仕組みです。

現在の基本フローです。

```text
資料を追加する -> chunk に分割する -> JSON に保存する -> 関連 chunk を検索する -> プロンプトを作る -> LLM に渡す -> 使用資料 ID 付きで回答する
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

資料をすべて削除します。

```text
/research clear --confirm
```

## アーキテクチャ

Research Note を中心にした構造図です。

![Research Note Architecture](./docs/practical_steps/research_note_architecture.svg)

図の説明は以下にあります。

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
