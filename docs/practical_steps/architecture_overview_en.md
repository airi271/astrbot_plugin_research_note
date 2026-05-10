# Architecture Overview

![Architecture](https://img.shields.io/badge/Diagram-Architecture-0969da)
![RAG](https://img.shields.io/badge/Flow-Fixed%20RAG-1a7f37)
![Agent](https://img.shields.io/badge/Flow-Agent%20Modes-8250df)
![Storage](https://img.shields.io/badge/Backend-JSON%20%2F%20SQLite-bf8700)

This page explains the structure and execution flow of the Research Note Plugin with diagrams.

It focuses on three practical questions: what the user inputs, where materials are stored, and which sources are used when the AI answers.

> **How to read this page**
>
> Start with the overall architecture, then read Fixed RAG, Import, Storage, Agent Modes, and Multi-Agent in order. That sequence follows how the plugin is usually used.

## Diagram Index

| Diagram | What It Shows | Main Commands |
| --- | --- | --- |
| [Overall Architecture](#overall-architecture) | Relationship between the plugin, storage, LLM, and external tools | Overall |
| [Fixed RAG](#fixed-rag) | The basic search-then-answer flow | `/research ask`, `/research search` |
| [Import And Storage](#import-and-storage) | How materials become documents, chunks, and embeddings | `/research add`, `/research import` |
| [Storage Backend](#storage-backend) | JSON / SQLite storage and backup | `/research backup` |
| [Agent Modes](#agent-modes) | Difference between agent, web, and MCP modes | `/research agent*` |
| [Multi-Agent](#multi-agent) | Retriever / Reader / Writer / Critic role flow | `/research agent_multi` |

## Overall Architecture

> **Key point:** Research Note sits between chat, saved materials, LLM providers, and external tools. Its role is to keep answers connected to sources.

![Research Note Architecture](./research_note_architecture.svg)

<span style="color:#0969da"><strong>This diagram shows the current overall architecture of the Research Note Plugin.</strong></span>

`User Side` is where the user sends `/research ...` commands from Slack, Telegram, or another chat platform.

`AstrBot Core` receives chat events and routes them to plugins. Research Note runs as an AstrBot plugin.

`Research Note Plugin` is the main component. It handles adding materials, searching saved chunks, answering questions, imports, and agent execution.

`LLM Providers` include the chat model that writes answers and the embedding model that converts text into vectors for retrieval.

`Research Storage` is where saved materials live. The plugin can use `research_notes.json` or `research_notes.sqlite3`.

`External Research` includes Web Search, page extraction, AstrBot Knowledge Base, file tools, and Python tools. These tools are not always enabled; agent modes receive only the tools allowed by configuration.

<span style="color:#1a7f37"><strong>The important idea is that Research Note is both a storage layer for research materials and an entry point for source-grounded answers.</strong></span>

## Fixed RAG

> **Key point:** This is the predictable path: retrieve relevant saved chunks first, then ask the LLM to answer from them.

![Fixed RAG Flow](./flow_fixed_rag.svg)

<span style="color:#0969da"><strong>This diagram shows how `/research ask` and `/research search` work.</strong></span>

`/research search <query>` does not ask the LLM to write an answer. It only returns relevant saved chunks.

`/research ask <question>` first retrieves relevant chunks, then passes them to the LLM to generate a source-grounded answer.

Retrieval uses `embedding`. An embedding is a list of numbers that represents text meaning. Texts with similar meanings should be closer in vector space.

<span style="color:#cf222e"><strong>This plugin does not use keyword fallback.</strong></span> If query embeddings or stored chunk embeddings are missing, the command fails visibly instead of pretending that keyword search is enough.

Node meanings:

- <strong>`User command`</strong>: The user sends `/research ask ...` or `/research search ...`.
- <strong>`Extract query`</strong>: The plugin removes the command part and keeps the actual question or query.
- <strong>`Embedding model`</strong>: The query is converted into an embedding vector.
- <strong>`Load chunks`</strong>: Saved Documents and Chunks are loaded from JSON or SQLite.
- <strong>`Embedding search`</strong>: The query embedding is compared with chunk embeddings.
- <strong>`Search output`</strong>: `/research search` stops here and returns score, title, doc_id, and chunk_id.
- <strong>`Context pack`</strong>: `/research ask` trims and packages matched chunks as source material for the LLM.
- <strong>`LLM prompt`</strong>: The plugin tells the LLM to answer from sources and include references and unknowns.
- <strong>`Grounded answer`</strong>: The LLM writes an answer with citations such as `[1]` and a source list.

This is the most predictable mode. It is simpler than agent mode and easier to verify.

## Import And Storage

> **Key point:** Imports use preview and confirmation. Saving succeeds only when every chunk receives an embedding.

![Import and Storage Flow](./flow_import_storage.svg)

`/research add <text>` saves pasted text directly.

`/research import text <text>` and `/research import url <url>` create a preview first. The preview shows title, source, a content preview, and estimated chunk count.

URL import normalizes Slack or Markdown-style URLs before fetching. For HTML pages, it extracts the title and readable text.

Only after <strong>`/research import confirm <pending_id>`</strong> does the plugin save the material. Until then, it is stored temporarily in `pending_imports.json`.

When saving, the plugin creates a Document first. Then it splits content into Chunks, creates embeddings for all chunks, and saves only if embedding creation succeeds for every chunk.

## Storage Backend

> **Key point:** Commands stay the same. Only the storage backend changes between JSON and SQLite.

![Storage Backend Flow](./flow_storage_backend.svg)

The plugin reads `storage_backend` at startup. If it is not configured, it uses `json`.

JSON storage path:

```text
data/research_notes.json
```

SQLite storage path:

```text
data/research_notes.sqlite3
```

JSON is easy to inspect manually. SQLite is a better growth path when the number of documents and chunks increases.

Internally, JSON and SQLite are different. From the command layer, they share the same `load_store`, `save_store`, and `create_backup` interface, so `/research add` and `/research ask` work the same way.

`/research backup` creates a backup under `data/backups` for the active backend.

## Agent Modes

> **Key point:** The three agent modes are alternatives. They do not run in sequence.

![Agent Modes Flow](./flow_agent_modes.svg)

`/research agent <task>` uses only Research Note tools. It can search, inspect, list, and explicitly save or delete when requested.

`/research agent_web <task>` adds allowed Web Search tools. It requires `enable_web_research=true`.

`/research agent_mcp <task>` adds allowed MCP tools and AstrBot builtin tools. It requires `enable_mcp_research=true`.

Agent modes use <strong>`tool_loop_agent`</strong>. The LLM can call tools such as `research_search`, inspect the result, call another tool if needed, and then produce a final answer.

External tools can touch files, APIs, or local resources. For that reason, Web/MCP modes are explicit and use configured allowlists.

Delete operations require confirmation: `research_delete_document` only deletes when `doc_id` and `confirm_doc_id` match.

## Multi-Agent

> **Key point:** The multi-agent flow separates retrieval, reading, writing, and critique.

![Multi-Agent Flow](./flow_multi_agent.svg)

<strong>Multi-Agent</strong> does not ask a single LLM call to do everything. It breaks the task into roles.

The <strong>`Retriever`</strong> gathers evidence. It is the only role that uses `tool_loop_agent` and can receive Research Note tools, allowed builtin tools, MCP tools, and optional creation tools.

`Reader` organizes claims, comparisons, conflicts, and unknowns from the research pack.

`Writer` drafts an answer from the reader notes.

`Critic` checks missing evidence, weak citations, unsupported claims, and overlooked conflicts.

`Final Writer` revises the draft using the critique and writes the final answer.

The order is:

```text
Retriever -> Reader -> Writer -> Critic -> Final Writer
```

If `show_multi_agent_trace=true`, the final output also includes intermediate Retriever, Reader, Draft, and Critique sections.

## Implementation Mapping

- Commands: `/research add/list/show/ask/agent/agent_web/agent_mcp/agent_multi/import/search/delete/reindex/backup/clear` in `main.py`.
- Tools: `research_search`, `research_get_document`, `research_list_documents`, `research_add_text`, `research_delete_document`.
- Search: embedding-only cosine similarity in `search.py` and `tool_utils.py`.
- Storage: `NoteStore` and `SQLiteNoteStore` in `store.py`.
- Import: `pending_imports.py` and `importers/url_importer.py`.
- Agent prompts: `agent_prompts.py`.

## Design Rules

- Stored materials are split into Documents and Chunks.
- Every saved chunk must have an embedding.
- Retrieval is embedding-only.
- External Web/MCP/tool results are separated from saved materials.
- External information is not saved automatically; import confirmation or an explicit save request is required.
- Delete operations require confirmation.
