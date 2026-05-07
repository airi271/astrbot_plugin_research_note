# Research Note for AstrBot

Research Note is a source-grounded research assistant plugin for [AstrBot](https://github.com/AstrBotDevs/AstrBot). It lets you save research notes or source excerpts, retrieve relevant materials, and ask questions that are answered with explicit source references.

This plugin is being developed toward a lightweight source-grounded research workflow inside AstrBot: collect materials in chat, search them, ask grounded questions, and gradually extend the system with chunking, citations, tools, MCP, web research, and multi-agent workflows.

## Features

- Save research materials with `/research add <text>`.
- List stored materials with `/research list`.
- Ask source-grounded questions with `/research ask <question>`.
- Use keyword search as a safe fallback.
- Use embedding search when an AstrBot embedding provider is available.
- Configure search and safety options through `_conf_schema.json`.
- Follow the practical roadmap toward document/chunk storage, citation quality, tool use, MCP, and multi-agent research workflows.

## Current Status

Research Note is currently an early `v0.1.0` plugin. The minimal RAG flow works, but the plugin is still evolving toward a more practical research assistant.

Implemented core flow:

```text
Add material -> Store in JSON -> Search relevant notes -> Build prompt -> Ask LLM -> Return answer with source IDs
```

Planned practical improvements are documented in:

```text
PRACTICAL_ROADMAP.md
docs/practical_steps/README.md
```

An architecture overview is available here:

```text
docs/practical_steps/architecture_overview.md
```

## Commands

```text
/research help
/research add <text>
/research list
/research ask <question>
/research clear --confirm
```

## Configuration

The plugin currently supports these configuration items:

- `top_k`: Number of relevant materials used for answering.
- `max_note_chars`: Maximum characters included from each note in the prompt.
- `max_add_chars`: Maximum characters allowed in one `/research add` call.
- `strict_grounding`: Whether to strongly restrict answers to stored sources.

## Development Roadmap

The next practical milestones are:

- Clean up the learning-stage implementation.
- Move from note-level storage to document and chunk storage.
- Improve hybrid search and citation quality.
- Expose Research Note as AstrBot `FunctionTool`s.
- Add `/research agent` with `tool_loop_agent()`.
- Add import, web research, MCP, and multi-agent workflows after the core source-grounded flow is stable.

## English Description

Research Note is a source-grounded research assistant plugin for AstrBot. It helps users collect research materials, retrieve relevant notes, and ask questions answered with explicit source references. The long-term goal is to provide a practical research workflow inside AstrBot by combining local research storage, citation-aware RAG, AstrBot tools, MCP integrations, web research, and multi-agent assistance.

## Japanese Description

Research Note は、AstrBot 上で動く根拠付き研究補助プラグインです。研究メモや資料抜粋を保存し、関連する内容を検索し、根拠資料を示しながら質問に回答することを目指します。長期的には、ローカルの研究資料管理、引用付き RAG、AstrBot の Tool、MCP 連携、Web 調査、Multi-Agent を組み合わせ、実用的な研究支援ワークフローを AstrBot 内で実現することを目標にしています。

## Documentation

- [AstrBot Repository](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot Plugin Development Docs (English)](https://docs.astrbot.app/en/dev/star/plugin-new.html)
- [AstrBot Plugin Development Docs (Chinese)](https://docs.astrbot.app/dev/star/plugin-new.html)
