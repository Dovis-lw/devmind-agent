# 项目上下文

## 项目名称

DevMind Agent

## 目标

为开发人员和企业员工提供研发知识库问答与技术问题诊断工作台。主场景是“用户粘贴报错/技术问题，Agent 检索授权知识库并调用代码工具，输出有证据的诊断报告”。

## 已确认范围

- MVP 语言：Python、JavaScript/TypeScript
- 数据导入优先级：上传文件/压缩包或代码目录 -> Git URL -> 粘贴文本/代码
- RAG：PDF/Word/Markdown/TXT 解析、分块、Embedding、向量检索、关键词检索、混合检索、引用、不确定拒答、权限与筛选
- Agent 工具：知识库检索、代码静态检查、安全沙箱测试/命令
- 用户模型：多用户、工作区、知识库隔离；Owner/Editor/Viewer
- 模型：OpenAI-compatible 云模型 + Ollama；管理员配置供应商和模型，API Key 只读后端 `.env`
- 部署：Docker Compose，PostgreSQL + pgvector，Redis
- 高风险操作：生成 Patch，用户确认后只应用到临时工作区并展示 Diff

## 技术栈

- Backend: Python 3.11, FastAPI, Pydantic, SQLAlchemy/asyncpg, Redis/ARQ-ready
- AI: OpenAI-compatible Chat Completions, Ollama, deterministic local embedding fallback
- RAG: PostgreSQL full-text search + pgvector, RRF fusion, metadata permission filters
- Frontend: React, TypeScript, Vite, SSE streaming
- Infra: Docker Compose, PostgreSQL + pgvector, Redis

## 验收标准

- `docker compose up --build` 可以启动服务
- 登录、工作区、知识库、文档上传、任务状态、问答和模型选择页面可演示
- 问答返回引用、检索阶段和工具时间线
- 没有充分检索证据时返回拒答
- 代码诊断支持 Python 与 JavaScript/TypeScript 的静态检查
- 高风险 Patch 必须经过确认，不能直接修改宿主机文件
- API 文档、架构图、简历描述和面试话术齐全
