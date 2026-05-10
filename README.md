# Research Note for AstrBot

![AstrBot Plugin](https://img.shields.io/badge/AstrBot-Plugin-0969da)
![Source Grounded](https://img.shields.io/badge/Source--Grounded-RAG-1a7f37)
![Embedding Search](https://img.shields.io/badge/Search-Embedding--Only-8250df)
![Storage](https://img.shields.io/badge/Storage-JSON%20%2F%20SQLite-bf8700)

> **A source-grounded research assistant plugin for AstrBot.**
>
> Save research materials, retrieve relevant chunks, and ask questions while keeping answers tied to explicit source references.

Research Note is a source-grounded research assistant plugin for [AstrBot](https://github.com/AstrBotDevs/AstrBot). It helps turn chat-based research into a reusable workflow: collect materials, split them into searchable chunks, retrieve relevant evidence, and generate answers that point back to saved sources.

Saved materials are represented as **Documents** and **Chunks**. Retrieval is **embedding-only**, so missing embeddings are treated as visible problems instead of silently falling back to keyword search.

## Languages

| Language | README | Architecture Guide |
| --- | --- | --- |
| English | [README.md](./README.md) | [architecture_overview_en.md](./docs/practical_steps/architecture_overview_en.md) |
| Japanese | [README_JP.md](./README_JP.md) | [architecture_overview.md](./docs/practical_steps/architecture_overview.md) |
| Chinese | [README_CN.md](./README_CN.md) | [architecture_overview_zh.md](./docs/practical_steps/architecture_overview_zh.md) |

## Quick Links

| What You Want To Read | Link |
| --- | --- |
| Architecture and feature-level flow diagrams | [Architecture Guide](./docs/practical_steps/architecture_overview_en.md) |
| Practical development roadmap | [PRACTICAL_ROADMAP.md](./PRACTICAL_ROADMAP.md) |
| Phase-by-phase practical notes | [docs/practical_steps/README.md](./docs/practical_steps/README.md) |

## Why It Matters

| Research Problem | What Research Note Provides |
| --- | --- |
| Research notes disappear inside chat history | Save materials as Documents and Chunks for later retrieval. |
| AI answers are hard to verify | Keep answers linked to doc_id, chunk_id, title, and source_uri. |
| Keyword search misses related passages | Use embedding-based semantic search over saved chunks. |
| Web/tool results get mixed with stored evidence | Separate stored evidence from external evidence. |
| One-shot answers are not enough for review | Use multi-agent flows for retrieval, reading, drafting, and critique. |

## What This Plugin Solves

Research Note is designed for <span style="color:#8250df"><strong>research material management</strong></span>, <span style="color:#0969da"><strong>semantic retrieval</strong></span>, and <span style="color:#1a7f37"><strong>source-grounded answering</strong></span> inside AstrBot. Notes, article excerpts, web page text, and project references can be saved as reusable research materials instead of being lost in chat history.

Large language models can produce fluent but weakly grounded answers. In research contexts, the risk is not only incorrect output, but also <span style="color:#cf222e"><strong>AI hallucination</strong></span>: plausible statements that are not supported by the materials. Research Note follows the idea of <strong>Retrieval-Augmented Generation (RAG)</strong>: retrieve saved chunks first, place them into the prompt context, and then ask the LLM to answer from that context.

For research work, <strong>evidence traceability</strong>, <strong>citation</strong>, and <strong>source attribution</strong> are as important as answer fluency. Research Note includes doc_id / chunk_id, title, and source_uri in search results and answers, making it easier to check which statement came from which source. This supports <span style="color:#cf222e"><strong>hallucination mitigation</strong></span>, source review, literature comparison, and follow-up verification.

Key benefits:

- <strong>Document / Chunk Management</strong>: Store long materials as documents and retrieval-friendly chunks.
- <strong>Semantic Search</strong>: Use embedding-based semantic search instead of relying on keyword matching.
- <strong>Grounded Answering</strong>: Build a context pack from saved chunks before asking the LLM to answer.
- <strong>Citation Support</strong>: Keep doc_id / chunk_id in outputs for easier source attribution.
- <strong>Retrieval Check</strong>: Use `/research search` to inspect retrieval results before asking the LLM.
- <strong>Import Control</strong>: Preview and confirm text or URL imports before saving them.
- <strong>Evidence Separation</strong>: Keep external evidence from Web/MCP/AstrBot tools separate from stored evidence.
- <strong>Multi-Agent Review</strong>: Use Retriever, Reader, Writer, and Critic roles for staged research workflows.
- <strong>Storage Backend</strong>: Choose JSON or SQLite storage with the same command interface.

<span style="color:#0969da"><strong>The value of this plugin is not merely that it generates answers. Its value is that it structures the research process around retrievable sources, citations, and verification.</strong></span> It helps use conversational AI as a continuous source-grounded research workflow rather than a one-off Q&A interface.

## Architecture

![Research Note Architecture](./docs/practical_steps/research_note_architecture.svg)

[Open the architecture guide and flow diagrams](./docs/practical_steps/architecture_overview_en.md)

## Features

- Save research materials with `/research add <text>`.
- Import text or HTML pages with preview and confirmation.
- Store materials as Documents and searchable Chunks.
- List stored materials with `/research list`.
- Inspect a stored document with `/research show <doc_id>`.
- Ask source-grounded questions with `/research ask <question>`.
- Run explicit web-assisted research with `/research agent_web <task>` when enabled.
- Run explicit MCP / AstrBot-tool-assisted research with `/research agent_mcp <task>` when enabled.
- Run staged multi-agent research with `/research agent_multi <task>` when enabled.
- Use embedding search through an AstrBot embedding provider.
- Store data in either JSON or SQLite with the same command interface.
- Create a local storage backup with `/research backup`.
- Register LLM tools: `research_search`, `research_get_document`, `research_list_documents`, `research_add_text`, and `research_delete_document`.
- Configure search and safety options through `_conf_schema.json`.

## Current Status

Research Note is currently an early `v0.1.0` plugin. The minimal Document / Chunk RAG flow works, and the plugin is evolving toward a more practical research assistant.

Implemented core flow:

```text
Add material -> Split into chunks -> Store in JSON or SQLite -> Search relevant chunks -> Build prompt -> Ask LLM -> Return answer with source IDs
```

## Commands

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

Short aliases are also available: `/research import_text <text>`, `/research import_url <url>`, and `/research import_confirm <pending_id>`.

## Configuration

The plugin currently supports these configuration items:

- `top_k`: Number of relevant materials used for answering.
- `max_note_chars`: Maximum characters included from each matched chunk in the prompt.
- `max_add_chars`: Maximum characters allowed in one `/research add` call.
- `chunk_size`: Approximate character length of each stored chunk.
- `chunk_overlap`: Character overlap between neighboring chunks.
- `min_embedding_score`: Minimum embedding similarity score required for retrieval.
- `max_context_chars`: Maximum total context characters passed to the LLM.
- `agent_max_steps`: Maximum number of agent tool-calling steps.
- `agent_tool_call_timeout`: Timeout seconds for each agent tool call.
- `enable_web_research`: Whether `/research agent_web` can use allowed Web Search tools.
- `allowed_web_tools`: Web Search tool names passed to `/research agent_web`.
- `enable_mcp_research`: Whether `/research agent_mcp` can use allowed MCP and AstrBot builtin tools.
- `allowed_mcp_tools`: MCP tool names passed to `/research agent_mcp`.
- `allowed_builtin_tools`: AstrBot builtin tool names passed to `/research agent_mcp`.
- `allow_all_builtin_tools`: Whether `/research agent_mcp` receives every AstrBot builtin tool.
- `denied_builtin_tools`: Builtin tool names excluded even when all builtin tools are enabled.
- `enable_multi_agent`: Whether `/research agent_multi` runs the staged Retriever/Reader/Writer/Critic flow.
- `multi_agent_retriever_max_steps`: Maximum tool-calling steps for the multi-agent Retriever.
- `show_multi_agent_trace`: Whether `/research agent_multi` includes intermediate role outputs.
- `storage_backend`: Storage backend for Research Note data. Use `json` or `sqlite`; default is `json`.
- `enable_multi_agent_creation_tools`: Whether `/research agent_multi` can use Python and file creation tools.
- `multi_agent_creation_tools`: Creation tool names added to `/research agent_multi`.
- `max_import_chars`: Maximum text characters kept from an import preview.
- `import_preview_chars`: Maximum characters shown in an import preview.
- `import_url_timeout`: Timeout seconds for URL import fetching.
- `strict_grounding`: Whether to strongly restrict answers to stored sources.
- `show_debug_prompt`: Whether to include the generated LLM prompt in `/research ask` output.

## Documentation

- [AstrBot Repository](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot Plugin Development Docs (English)](https://docs.astrbot.app/en/dev/star/plugin-new.html)
- [AstrBot Plugin Development Docs (Chinese)](https://docs.astrbot.app/dev/star/plugin-new.html)
