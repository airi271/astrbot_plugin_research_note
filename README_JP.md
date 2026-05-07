# Research Note for AstrBot 日本語版

Research Note は、[AstrBot](https://github.com/AstrBotDevs/AstrBot) 上で動く、根拠付きの研究補助プラグインです。研究メモや資料の抜粋を保存し、関連する内容を検索し、保存済み資料に基づいて質問に回答することを目指しています。

このプラグインは、チャットの中で資料を集め、検索し、根拠を確認しながら AI に質問できる軽量な研究支援ワークフローを作るために開発しています。

## 主な機能

- `/research add <text>` で研究資料やメモを保存できます。
- `/research list` で保存済み資料を一覧できます。
- `/research ask <question>` で保存済み資料に基づいて質問できます。
- embedding provider がない場合でも、キーワード検索で動作します。
- embedding provider がある場合は、意味の近さによる検索も利用できます。
- `_conf_schema.json` で検索件数や安全設定を変更できます。
- 今後、Document / Chunk 管理、引用改善、Tool 化、MCP 連携、Multi-Agent 化へ拡張する計画です。

## 現在の状態

現在のバージョンは `v0.1.0` です。

最小構成の RAG フローが動作します。RAG とは、AI が直接回答するだけでなく、先に関連資料を検索し、その資料をもとに回答する仕組みです。

現在の基本フローです。

```text
資料を追加する -> JSON に保存する -> 関連資料を検索する -> プロンプトを作る -> LLM に渡す -> 使用資料 ID 付きで回答する
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
/research ask <question>
/research clear --confirm
```

## 使い方の例

資料を追加します。

```text
/research add RAG は検索した資料を LLM に渡して回答する仕組みです。
```

保存済み資料を確認します。

```text
/research list
```

資料に基づいて質問します。

```text
/research ask RAG とは何ですか？
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
- `max_note_chars`: 1件の資料からプロンプトに入れる最大文字数。
- `max_add_chars`: 1回で追加できる資料の最大文字数。
- `strict_grounding`: 資料にないことを推測しないよう強く指示するかどうか。

## 開発ロードマップ

今後の主な開発予定です。

- 学習段階の実装を整理し、保存と削除をより安全にする。
- note 単位の保存から Document / Chunk 単位の保存へ移行する。
- キーワード検索と embedding 検索を組み合わせた hybrid search を実装する。
- 回答に使った根拠資料をより分かりやすく表示する。
- Research Note の検索機能を AstrBot の `FunctionTool` として公開する。
- `/research agent` を追加し、AI が必要に応じて資料検索 tool を呼べるようにする。
- URL やファイルから資料を取り込めるようにする。
- Web Search、MCP、Multi-Agent 連携を段階的に追加する。

## 目指している方向

Research Note は、AI に自由に答えさせるだけではなく、保存済み資料を根拠にして回答する研究補助プラグインを目指しています。

重視している点です。

- 小さく動く機能から始める。
- 資料に基づく回答を優先する。
- 根拠資料を確認できるようにする。
- embedding provider がなくても最低限動くようにする。
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
