# DevMind Agent

面向开发人员和企业员工的智能技术问题诊断与知识库 Agent 工作台。项目用于展示 AI 应用开发工程师需要掌握的完整链路：LLM 调用、知识库与向量检索（RAG）、前端交互、后端服务编排、工具调用、权限隔离、后台任务与 Docker 部署。

> 当前版本是可在无 API Key、无 PostgreSQL/Redis 的情况下运行的离线 MVP。默认主链路使用 `InMemoryStore`、确定性 64 维 Hash Embedding 和 `asyncio.create_task`；`PostgreSQL + pgvector`、`Redis + ARQ` 已提供生产替换 seam，但尚未作为默认运行时接入。

## 核心演示

1. 使用演示账号登录，进入研发工作区和平台工程知识库。
2. 上传 PDF、Word、Markdown、TXT、Python/JavaScript/TypeScript 文件或 ZIP 代码包，也可以粘贴文本/代码。
3. 后端异步解析、文本分块、生成离线 Embedding 并更新任务状态。
4. 输入报错日志或技术问题，选择对话模型和 Embedding 模型，按文档类型/标签筛选知识库。
5. Agent 依次执行规划、权限过滤后的向量+关键词混合检索、静态检查和安全沙箱语法检查。
6. 前端通过 SSE 流式展示 Agent 时间线、工具输出、引用来源和最终诊断；证据不足时拒答。
7. 勾选高风险 Patch 后展示人工确认门和预览，不会真实修改宿主机文件；真正 Patch 生成/apply 属于 P1。

## 快速开始（Mock 离线模式）

需要 Python 3.11+、Node.js 20+。Mock 模式不依赖 PostgreSQL、Redis 或任何 API Key。

### 后端

```js
cd src/backend
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

如果尚未创建项目虚拟环境：

```js
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r src/backend/requirements.txt
```

### 前端

```js
cd src/frontend
npm install
npm run dev
```

前端依赖以 `src/frontend/package-lock.json` 为准。若 Windows 上执行 `npm install` 时出现不支持 `workspace:` 协议，通常是因为当前目录残留了由 pnpm 创建的旧 `node_modules`。请在 `src/frontend` 目录清理或移走该目录后重新安装：

```js
if (Test-Path node_modules) { Remove-Item node_modules -Recurse -Force }
npm install
```

不要在项目根目录执行前端依赖安装；Docker 构建会使用锁文件执行 `npm ci`。

浏览器打开 `http://localhost:5173`，演示账号：`demo@devmind.local` / `devmind-demo`。

也可以直接在项目根目录使用已创建的 `.venv`：

```js
.\.venv\Scripts\python.exe -m pytest tests -q
```

## 云端模型 / Ollama

复制 `config/.env.example` 为项目根目录 `.env`，填写一个或多个 OpenAI-compatible Provider：OpenAI、通义、DeepSeek、智谱、硅基流动。API Key 只由后端读取，前端只看到模型 ID/名称，不会接收 Key。

- 当前 chat Provider 通过统一的 `/chat/completions` 流式接口调用。
- 当前离线 MVP 的 `ProviderGateway.embed()` 使用确定性 64 维 Embedding；云端 `/embeddings` 调用尚未实现。
- 生产接入云端 Embedding 时，文档向量、Query 向量和数据库 `vector` 维度必须使用同一个模型/维度；迁移文件当前按生产示例使用 `vector(1536)`。
- Ollama 只有在 `.env` 设置 `OLLAMA_ENABLED=true` 时才出现在模型列表中，不会强制作为本地开发默认模式。


运行配置：`CORS_ORIGINS` 使用逗号分隔允许的前端来源；`SANDBOX_TIMEOUT_SECONDS` 控制代码语法检查沙箱的超时时间。

## Docker 部署

标准命令：

```js
docker compose -f compose.yaml up --build
```

兼容的备用文件：

```js
docker compose -f docker-compose.yml config
docker compose -f docker-compose.yml up --build
```

服务：

- Web：`http://localhost:5173`
- API：`http://localhost:8000`
- OpenAPI：`http://localhost:8000/docs`
- PostgreSQL + pgvector：`localhost:5432`
- Redis：`localhost:6379`

Compose 会启动 PostgreSQL/pgvector 和 Redis，并把配置注入后端；但当前示例 API 默认仍走内存 Repository，数据库和队列主要用于展示生产部署边界与切换位置。

## 质量检查

```powershell
.\.venv\Scripts\python.exe -m compileall -q src/backend/app
.\.venv\Scripts\python.exe -m pytest tests -q
cd src/frontend
npm run build
cd ../..
docker compose -f compose.yaml config
git diff --check
```

## 项目结构

- `src/backend/app/`：FastAPI、RAG、Agent、Provider、任务和安全沙箱
- `src/frontend/`：React + TypeScript + Vite Web 工作台
- `migrations/`：PostgreSQL + pgvector schema，包含工作区成员、知识库、文档、任务和向量索引设计
- `docs/`：规格、架构、接口、简历项目描述和面试话术
- `tests/`：后端单元测试与 API 合约测试
- `config/`：非敏感配置模板

## 四类必需技术栈的代码定位

项目中使用独立注释标出四类能力，便于面试时快速讲解：

- `# AI TECH STACK: LLM CALL`：`src/backend/app/services/providers.py`
- `# AI TECH STACK: RAG / VECTOR RETRIEVAL`：`src/backend/app/services/rag.py`、`src/backend/app/services/postgres_store.py`
- `# AI TECH STACK: BACKEND ORCHESTRATION`：`src/backend/app/services/agent.py`、`src/backend/app/services/tasks.py`、`src/backend/app/main.py`
- `// AI TECH STACK: FRONTEND INTERACTION`：`src/frontend/src/App.tsx`、`src/frontend/src/api.ts`

## 当前 MVP 边界

已实现：离线演示登录、工作区/知识库权限、文档导入与解析、分块、确定性 Embedding、混合检索、RRF、引用/拒答、模型白名单、SSE、后台索引任务、静态检查、安全沙箱和人工确认事件。

P1：Git URL 导入（当前返回 501）、真实云端 Embedding、失败重试/取消、会话历史、管理员配置页、RAG 评测集、Patch 生成/Diff/真实 apply，以及让 API 与 ARQ Worker 共享持久化 Repository。
