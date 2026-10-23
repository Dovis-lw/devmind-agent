# 简历项目描述

**DevMind Agent｜研发知识库智能诊断与 Agent 工作台**（个人项目）

- 使用 FastAPI + React + TypeScript 搭建多用户工作区与知识库系统，支持 PDF/Word/Markdown/TXT/代码包导入、粘贴代码、后台解析分块、任务状态和 Docker Compose 部署。
- 设计 RAG 检索链路：离线 MVP 使用确定性 64 维 Embedding 与内存 Repository，结合关键词召回和 RRF；同时设计 PostgreSQL + pgvector/FTS 的生产 Repository seam，支持工作区、知识库、角色、文档类型和标签过滤，回答返回可追溯引用并支持无依据拒答。
- 设计 Agent Orchestrator 状态机，统一接入 OpenAI-compatible API、通义/DeepSeek/智谱/硅基流动和可选 Ollama，支持知识库检索、Python/JS/TS 静态检查、安全沙箱工具调用及 SSE 流式时间线。
- 通过 API Key 后端隔离、ZIP 安全解析、命令白名单、临时工作区、超时/输出限制和高风险操作人工确认，构建可观测的自动诊断闭环；Redis/ARQ 队列作为生产替换 seam。

## 简历写法边界

面试时应明确：当前默认演示链路为了能在无外部服务时稳定运行，使用内存存储、64 维确定性向量和 asyncio 任务；PostgreSQL/pgvector 与 Redis/ARQ 已完成接口和迁移设计，但不是默认运行时已经接入的生产链路。
