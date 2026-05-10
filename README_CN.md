# Research Note for AstrBot 中文版

![AstrBot Plugin](https://img.shields.io/badge/AstrBot-Plugin-0969da)
![Source Grounded](https://img.shields.io/badge/Source--Grounded-RAG-1a7f37)
![Embedding Search](https://img.shields.io/badge/Search-Embedding--Only-8250df)
![Storage](https://img.shields.io/badge/Storage-JSON%20%2F%20SQLite-bf8700)

> **一个用于 AstrBot 的 source-grounded research assistant plugin。**
>
> 它可以保存研究资料，检索相关片段，并在回答时尽量保留明确的来源线索。

Research Note 是运行在 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 上的研究辅助插件。它面向的是持续性的资料整理与问答，而不是一次性的聊天回答：你可以在聊天中保存资料，把长文切分成可检索的 chunks，再基于保存过的资料向 AI 提问。

保存后的资料会被表示为 **Document** 和 **Chunk**。检索采用 **embedding-only** 的方式；如果 query embedding 或 chunk embedding 缺失，插件会明确报错，而不是悄悄退回到关键词搜索。

## Languages

| Language | README | Architecture Guide |
| --- | --- | --- |
| English | [README.md](./README.md) | [architecture_overview_en.md](./docs/practical_steps/architecture_overview_en.md) |
| Japanese | [README_JP.md](./README_JP.md) | [architecture_overview.md](./docs/practical_steps/architecture_overview.md) |
| Chinese | [README_CN.md](./README_CN.md) | [architecture_overview_zh.md](./docs/practical_steps/architecture_overview_zh.md) |

## Quick Links

| 想看什么 | 链接 |
| --- | --- |
| 整体架构与功能流程图 | [架构说明](./docs/practical_steps/architecture_overview_zh.md) |
| 实用化路线图 | [PRACTICAL_ROADMAP.md](./PRACTICAL_ROADMAP.md) |
| 分阶段实现说明 | [docs/practical_steps/README.md](./docs/practical_steps/README.md) |

## 它解决什么问题

| 研究中的问题 | Research Note 的做法 |
| --- | --- |
| 资料贴在聊天里，很快被历史消息淹没 | 将资料保存为 Document / Chunk，方便之后检索。 |
| AI 回答看起来流畅，但来源不清楚 | 在搜索结果和回答中保留 doc_id / chunk_id、title、source_uri。 |
| 关键词搜索找不到语义相关内容 | 使用 embedding-based semantic search 检索相近含义的 chunk。 |
| Web Search 或工具结果容易和已保存资料混在一起 | 区分 stored evidence 和 external evidence。 |
| 单次回答缺少复核过程 | 使用 Multi-Agent flow 进行检索、阅读、写作和 critique。 |

## 为什么需要这个插件

Research Note 把 <span style="color:#8250df"><strong>研究资料整理</strong></span>、<span style="color:#0969da"><strong>语义检索</strong></span> 和 <span style="color:#1a7f37"><strong>基于来源的回答</strong></span> 放在同一个 AstrBot 会话环境中。研究笔记、论文或文章摘录、网页正文、项目资料不再只是聊天记录的一部分，而是可以被保存、检索和复用的研究材料。

大语言模型可以生成流畅的回答，但在研究场景中，问题往往不是“回答是否流畅”，而是“回答依据是什么”。如果缺少来源约束，就容易出现 <span style="color:#cf222e"><strong>AI hallucination</strong></span>，也就是看起来合理、但并没有被资料支持的生成内容。Research Note 采用 <strong>Retrieval-Augmented Generation (RAG)</strong> 的思路：先检索保存资料，再把相关 chunk 放入 prompt context，最后让 LLM 基于这些材料回答。

在研究和调查中，<strong>evidence traceability</strong>、<strong>citation</strong>、<strong>source attribution</strong> 很重要。Research Note 会在搜索结果和回答中保留 doc_id / chunk_id、title、source_uri，帮助用户回到原始资料检查依据。这有助于 hallucination mitigation、来源复核、文献比较和后续审阅。

主要能力包括：

- <strong>Document / Chunk 管理</strong>: 将长资料切分成更适合 retrieval 的 chunk。
- <strong>Semantic Search</strong>: 使用 embedding-based semantic search，而不是只依赖关键词匹配。
- <strong>Grounded Answer</strong>: `/research ask` 会先构造 context pack，再让 LLM 回答。
- <strong>Citation Support</strong>: 输出中保留 doc_id / chunk_id，方便追踪来源。
- <strong>Retrieval Check</strong>: 使用 `/research search` 在生成回答前检查检索结果。
- <strong>Import Control</strong>: text / URL import 需要 preview 和 confirm，避免误保存。
- <strong>Evidence Separation</strong>: 区分 Web/MCP/tool 结果和已保存资料。
- <strong>Multi-Agent Review</strong>: 使用 Retriever、Reader、Writer、Critic 分阶段处理复杂任务。
- <strong>Storage Backend</strong>: 可以选择 JSON 或 SQLite backend。

<span style="color:#0969da"><strong>这个插件的价值不只是让 AI 生成答案，而是把回答前后的研究流程组织起来。</strong></span> 它把资料保存、retrieval、来源检查、外部调查和批判性复核连接成一个 source-grounded research workflow。

## Architecture

![Research Note Architecture](./docs/practical_steps/research_note_architecture.svg)

[打开架构说明和功能流程图](./docs/practical_steps/architecture_overview_zh.md)

## 主要功能

- 使用 `/research add <text>` 保存研究资料。
- 使用 preview / confirm 导入 text 或 HTML 页面。
- 将资料保存为 Documents 和可检索的 Chunks。
- 使用 `/research list` 查看已保存资料。
- 使用 `/research show <doc_id>` 查看 document 和 chunk preview。
- 使用 `/research ask <question>` 基于保存资料提问。
- 启用后，使用 `/research agent_web <task>` 进行带 Web Search 的研究。
- 启用后，使用 `/research agent_mcp <task>` 调用允许的 MCP / AstrBot tools。
- 启用后，使用 `/research agent_multi <task>` 运行分阶段 Multi-Agent flow。
- 通过 AstrBot embedding provider 进行 embedding search。
- 使用 JSON 或 SQLite 保存数据。
- 使用 `/research backup` 创建当前 backend 的备份。
- 注册 LLM tools: `research_search`, `research_get_document`, `research_list_documents`, `research_add_text`, `research_delete_document`。

## 当前状态

当前版本是早期的 `v0.1.0`。Document / Chunk RAG 的核心流程已经可以工作，插件仍在向更实用的研究辅助工具演进。

核心流程：

```text
Add material -> Split into chunks -> Store in JSON or SQLite -> Search relevant chunks -> Build prompt -> Ask LLM -> Return answer with source IDs
```

## 命令

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

也可以使用短命令：`/research import_text <text>`、`/research import_url <url>`、`/research import_confirm <pending_id>`。

## 相关文档

- [AstrBot Repository](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot Plugin Development Docs (English)](https://docs.astrbot.app/en/dev/star/plugin-new.html)
- [AstrBot Plugin Development Docs (Chinese)](https://docs.astrbot.app/dev/star/plugin-new.html)
