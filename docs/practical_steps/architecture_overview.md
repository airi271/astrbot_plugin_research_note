# Architecture Overview

このファイルは、Research Note Plugin を中心にした AstrBot アプリ全体の構造を視覚化したものです。

画像ファイルです。

```text
docs/practical_steps/research_note_architecture.svg
```

Markdown 上では以下のように表示できます。

![Research Note Architecture](./research_note_architecture.svg)

## 図の読み方

左から右へ、ユーザーの入力が Research Note Plugin に届き、保存済み資料を検索し、LLM へ渡って回答が返る流れです。

中心にあるのは `Research Note Plugin` です。

- `Commands`: `/research add`、`/research ask`、`/research search` など、人間が直接使う入口です。
- `Agent Mode`: `/research agent` で `tool_loop_agent()` を使う入口です。
- `Search Layer`: keyword、embedding、hybrid search を担当します。
- `Prompt Layer`: citation、Sources、Unknowns を含む prompt を作ります。
- `Research Tools`: `research_search`、`research_get_document`、`research_add_text` など、LLM や agent が呼ぶ tool です。

## 通常の流れ

基本の `/research ask` はこの流れです。

```text
User
Chat Platform
AstrBot Core
Research Note Commands
Search Layer
Research Storage
Prompt Layer
LLM Provider
Answer with Sources
```

これは一番安定した固定 RAG です。まずここを強くします。

## Agent の流れ

`/research agent` はこの流れです。

```text
User
AstrBot Core
Research Note Agent Mode
ToolSet
research_search / research_get_document
LLM Provider
Final Answer
```

Agent mode は LLM が必要に応じて tool を呼びます。便利ですが、通常の `/research ask` より複雑です。

## 外部調査の流れ

Phase 6 以降では、外部情報を扱います。

```text
Import URL / Web Search / MCP Tool
Preview
User Confirm
Document + Chunk
Research Storage
```

重要なのは、外部情報を勝手に永続保存しないことです。preview と confirm を挟みます。

## Multi-Agent の流れ

Phase 9 以降では、研究作業を分担します。

```text
Retriever: 検索と context pack 作成
Reader: 資料要約
Critic: 根拠不足や矛盾の指摘
Writer: 最終回答や研究ノート作成
```

Multi-Agent は後半の機能です。先に chunk、citation、tool 化、agent mode を安定させます。

## Phase との対応

- Phase 1-5: Research Note Plugin の中心部分を強くする。
- Phase 6-8: Import、Web Search、MCP で外部情報を扱う。
- Phase 9: Multi-Agent で役割分担する。
- Phase 10: brief、outline、compare、claims を出力する。
- Phase 11: JSON から SQLite / Milvus など保存 backend を強化する。
- Phase 12: 検索と回答品質を評価する。

## 実装で守ること

- まず `/research ask` を安定させる。
- 長文は Document と Chunk に分ける。
- 回答には必ず source を付ける。
- Web Search と MCP は allowlist で制限する。
- 外部情報は勝手に保存しない。
- Multi-Agent は必要になってから入れる。
