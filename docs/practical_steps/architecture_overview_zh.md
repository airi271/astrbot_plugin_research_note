# Architecture Overview 中文版

![Architecture](https://img.shields.io/badge/Diagram-Architecture-0969da)
![RAG](https://img.shields.io/badge/Flow-Fixed%20RAG-1a7f37)
![Agent](https://img.shields.io/badge/Flow-Agent%20Modes-8250df)
![Storage](https://img.shields.io/badge/Backend-JSON%20%2F%20SQLite-bf8700)

这个页面用图说明 Research Note Plugin 的结构和执行流程。

阅读时可以关注三个问题：用户输入了什么，资料保存在哪里，AI 回答时使用了哪些资料。

> **阅读顺序建议**
>
> 先看整体架构，再依次看 Fixed RAG、Import、Storage、Agent Modes、Multi-Agent。这个顺序基本对应插件的实际使用路径。

## Diagram Index

| 图 | 可以了解什么 | 主要命令 |
| --- | --- | --- |
| [整体架构](#整体架构) | plugin、存储、LLM、外部工具之间的关系 | 全体 |
| [Fixed RAG](#fixed-rag) | 先检索再回答的基本流程 | `/research ask`, `/research search` |
| [Import And Storage](#import-and-storage) | 资料如何变成 document、chunk 和 embedding | `/research add`, `/research import` |
| [Storage Backend](#storage-backend) | JSON / SQLite 存储与备份 | `/research backup` |
| [Agent Modes](#agent-modes) | agent / web / mcp 三种模式的区别 | `/research agent*` |
| [Multi-Agent](#multi-agent) | Retriever / Reader / Writer / Critic 的角色分工 | `/research agent_multi` |

## 整体架构

> **看图重点:** Research Note 位于聊天、保存资料、LLM 和外部工具之间，用来组织基于资料的研究流程。

![Research Note Architecture](./research_note_architecture.svg)

<span style="color:#0969da"><strong>这张图展示了 Research Note Plugin 当前的整体架构。</strong></span>

`User Side` 是用户从 Slack、Telegram 等聊天平台发送 `/research ...` 命令的地方。

`AstrBot Core` 负责接收聊天事件，并把命令分发给 plugin。Research Note 作为 AstrBot plugin 运行。

`Research Note Plugin` 是核心部分，负责添加资料、检索 chunk、回答问题、导入资料和执行 agent。

`LLM Providers` 包括生成回答的 chat model，以及把文本转换为检索向量的 embedding model。

`Research Storage` 是保存资料的位置。当前可以选择 `research_notes.json` 或 `research_notes.sqlite3`。

`External Research` 包括 Web Search、页面抽取、AstrBot Knowledge Base、文件工具和 Python 工具。这些工具不会默认全部开放，而是根据配置传给 agent。

<span style="color:#1a7f37"><strong>最重要的一点是，Research Note 同时承担“保存研究资料”和“基于资料生成回答”的入口。</strong></span>

## Fixed RAG

> **看图重点:** 这是固定流程。先检索保存资料，再让 LLM 基于检索结果回答。

![Fixed RAG Flow](./flow_fixed_rag.svg)

<span style="color:#0969da"><strong>这张图说明 `/research ask` 和 `/research search` 的工作方式。</strong></span>

`/research search <query>` 不让 LLM 写回答，只返回相关的保存 chunk。

`/research ask <question>` 会先检索相关 chunk，再把这些 chunk 交给 LLM 生成带来源的回答。

检索使用 `embedding`。embedding 是一组表示文本含义的数字。含义相近的文本，在向量空间中通常更接近。

<span style="color:#cf222e"><strong>这个 plugin 不使用 keyword fallback。</strong></span> 如果 query embedding 或保存 chunk 的 embedding 缺失，命令会明确失败，而不是退回到关键词搜索。

节点说明：

- <strong>`User command`</strong>: 用户发送 `/research ask ...` 或 `/research search ...`。
- <strong>`Extract query`</strong>: 去掉命令本身，只保留真正的问题或查询。
- <strong>`Embedding model`</strong>: 把查询文本转换成 embedding 向量。
- <strong>`Load chunks`</strong>: 从 JSON 或 SQLite 读取保存的 Document / Chunk。
- <strong>`Embedding search`</strong>: 比较 query embedding 和 chunk embedding。
- <strong>`Search output`</strong>: `/research search` 在这里返回 score、title、doc_id、chunk_id。
- <strong>`Context pack`</strong>: `/research ask` 会把匹配到的 chunk 整理成给 LLM 的参考资料包。
- <strong>`LLM prompt`</strong>: 告诉 LLM 基于资料回答，并输出参考文献和不明点。
- <strong>`Grounded answer`</strong>: LLM 输出带 `[1]` 等引用编号的回答。

这是最容易预测的模式，比 agent mode 更简单，也更容易验证。

## Import And Storage

> **看图重点:** 导入资料时先 preview / confirm，保存时会同时创建 Document、Chunk 和 embedding。

![Import and Storage Flow](./flow_import_storage.svg)

`/research add <text>` 会直接保存用户粘贴的文本。

`/research import text <text>` 和 `/research import url <url>` 会先创建 preview。preview 会显示标题、来源、内容预览和预计 chunk 数。

URL import 会先把 Slack 或 Markdown 格式的 URL 规范化，再抓取页面。对于 HTML 页面，会提取 title 和可读文本。

只有执行 <strong>`/research import confirm <pending_id>`</strong> 后，资料才会真正保存。在此之前，内容临时保存在 `pending_imports.json`。

保存时，插件先创建 Document，再把正文拆成 Chunks。之后为所有 chunk 创建 embedding。只有全部 chunk embedding 创建成功，资料才会保存。

## Storage Backend

> **看图重点:** 命令用法不变，只切换底层保存方式：JSON 或 SQLite。

![Storage Backend Flow](./flow_storage_backend.svg)

插件启动时读取 `storage_backend`。如果没有配置，默认使用 `json`。

JSON 保存路径：

```text
data/research_notes.json
```

SQLite 保存路径：

```text
data/research_notes.sqlite3
```

JSON 便于直接查看文件内容。SQLite 更适合资料和 chunk 数量增加后的管理。

JSON 和 SQLite 的内部保存方式不同，但命令层统一通过 `load_store`、`save_store`、`create_backup` 使用。因此 `/research add` 和 `/research ask` 的用法不会变化。

`/research backup` 会在 `data/backups` 中为当前 backend 创建备份。

## Agent Modes

> **看图重点:** 三种 agent mode 是可选模式，不是按顺序全部执行。

![Agent Modes Flow](./flow_agent_modes.svg)

`/research agent <task>` 只使用 Research Note tools。它可以搜索资料、查看 document、列出资料，并在用户明确要求时保存或删除。

`/research agent_web <task>` 会额外加入允许的 Web Search tools。需要 `enable_web_research=true`。

`/research agent_mcp <task>` 会额外加入允许的 MCP tools 和 AstrBot builtin tools。需要 `enable_mcp_research=true`。

Agent mode 使用 <strong>`tool_loop_agent`</strong>。LLM 可以调用 `research_search` 等 tool，读取结果，必要时继续调用 tool，最后生成回答。

外部工具可能访问文件、API 或本地资源。因此 Web/MCP 模式是显式开启的，并且通过 allowlist 控制。

删除操作需要确认：`research_delete_document` 只有在 `doc_id` 与 `confirm_doc_id` 一致时才会删除。

## Multi-Agent

> **看图重点:** Multi-Agent 把检索、阅读、写作和 critique 分成不同角色。

![Multi-Agent Flow](./flow_multi_agent.svg)

<strong>Multi-Agent</strong> 不是让一次 LLM 调用完成所有事情，而是把任务拆成多个角色。

<strong>`Retriever`</strong> 负责收集证据。只有 Retriever 使用 `tool_loop_agent`，可以接收 Research Note tools、允许的 builtin tools、MCP tools，以及可选的 creation tools。

`Reader` 负责从 Research Pack 中整理主张、比较点、冲突和不明点。

`Writer` 基于 Reader Notes 写出 draft answer。

`Critic` 检查证据不足、引用不足、没有资料支持的断言，以及遗漏的冲突。

`Final Writer` 根据 Critic 的意见修订 draft，并输出最终回答。

顺序如下：

```text
Retriever -> Reader -> Writer -> Critic -> Final Writer
```

如果 `show_multi_agent_trace=true`，最终输出会包含 Retriever、Reader、Draft、Critique 等中间结果。

## 实现对应关系

- Commands: `main.py` 中的 `/research add/list/show/ask/agent/agent_web/agent_mcp/agent_multi/import/search/delete/reindex/backup/clear`。
- Tools: `research_search`、`research_get_document`、`research_list_documents`、`research_add_text`、`research_delete_document`。
- Search: `search.py` 和 `tool_utils.py` 中的 embedding-only cosine similarity。
- Storage: `store.py` 中的 `NoteStore` 和 `SQLiteNoteStore`。
- Import: `pending_imports.py` 和 `importers/url_importer.py`。
- Agent prompts: `agent_prompts.py`。

## 设计原则

- 保存资料会被拆成 Document 和 Chunk。
- 每个保存的 chunk 都必须有 embedding。
- 检索只使用 embedding，不使用 keyword fallback。
- Web/MCP/tool 的外部结果与保存资料分开处理。
- 外部信息不会自动保存；需要 import confirm 或明确的保存请求。
- 删除操作必须确认。
