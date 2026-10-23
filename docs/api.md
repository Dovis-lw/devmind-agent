# DevMind Agent API 接口文档

基础地址：`http://localhost:8000`

除 `/health` 和 `/api/auth/login` 外，请求都需要：

```http
Authorization: Bearer demo-token
```

> 当前 Token 是演示用固定 Token。生产应替换为 JWT/OIDC，并在数据库层执行成员权限过滤。API Key 永远只从后端 `.env` 读取，不会由前端提交或返回。

## 接口总览

| Method | Path | 说明 |
|---|---|---|
| GET | `/health` | 健康检查 |
| POST | `/api/auth/login` | 演示登录并获取 Token |
| GET | `/api/me` | 当前用户 |
| GET | `/api/workspaces` | 当前用户可访问的工作区 |
| GET/POST | `/api/workspaces/{workspace_id}/knowledge-bases` | 知识库列表/创建（创建需要 Editor/Owner） |
| GET | `/api/knowledge-bases/{id}/documents` | 知识库文档列表 |
| POST | `/api/knowledge-bases/{id}/documents` | 上传 PDF/DOCX/Markdown/TXT/代码/ZIP |
| POST | `/api/knowledge-bases/{id}/documents/text` | 粘贴文本或代码并创建文档 |
| POST | `/api/knowledge-bases/{id}/imports/git` | Git URL 导入，当前 P1 返回 501 |
| GET | `/api/tasks/{task_id}` | 查询后台索引任务 |
| GET | `/api/models` | 查询后端白名单模型，不返回 API Key |
| POST | `/api/chat/stream` | SSE 流式 Agent 诊断 |
| POST | `/api/diagnostics/static-check` | Python/JavaScript/TypeScript 静态检查 |
| POST | `/api/diagnostics/sandbox` | 受限语法检查沙箱 |

## 登录

`POST /api/auth/login`

```json
{
  "email": "demo@devmind.local",
  "password": "devmind-demo"
}
```

响应：

```json
{
  "access_token": "demo-token",
  "token_type": "bearer",
  "user": {
    "id": "user-demo",
    "email": "demo@devmind.local",
    "display_name": "Demo Developer"
  }
}
```

## 文档导入与任务

### 上传文件

`POST /api/knowledge-bases/{knowledge_base_id}/documents`

使用 `multipart/form-data` 的 `file` 字段。支持：`.pdf`、`.docx`、`.md`、`.txt`、`.py`、`.js`、`.ts`、`.tsx`、`.jsx`、`.zip`，单文件最大 20 MB。

ZIP 会拒绝路径穿越、加密条目、超大单文件和超大总解压内容，并跳过 `.env` 等敏感文件。成功响应：

```json
{
  "document": {
    "id": "uuid",
    "knowledge_base_id": "kb-demo",
    "name": "project.zip",
    "document_type": "archive",
    "status": "queued",
    "source": "upload",
    "tags": []
  },
  "task": {
    "id": "uuid",
    "kind": "document_index",
    "workspace_id": "ws-demo",
    "knowledge_base_id": "kb-demo",
    "status": "queued",
    "progress": 0,
    "message": "等待执行"
  }
}
```

### 粘贴文本/代码

`POST /api/knowledge-bases/{knowledge_base_id}/documents/text`

```json
{
  "name": "error-example.py",
  "content": "def handler(:\\n    pass",
  "document_type": "python",
  "tags": ["fastapi", "incident"]
}
```

`document_type` 可选 `markdown`、`text`、`python`、`javascript`、`typescript`。后端会清洗标签、解析文本、分块、生成 Embedding，并返回后台任务 ID。

`GET /api/knowledge-bases/{knowledge_base_id}/documents` 返回当前用户有权访问的文档及 `status/tags`。

### Git URL 导入

`POST /api/knowledge-bases/{knowledge_base_id}/imports/git` 当前返回 HTTP `501`。P1 计划使用 URL 白名单、临时目录、凭据隔离和安全解析；MVP 请先导出 ZIP 上传。

### 查询任务

`GET /api/tasks/{task_id}`

任务状态：`queued`、`running`、`succeeded`、`failed`。任务带有 `workspace_id` 和 `knowledge_base_id`，查询前执行权限检查，避免跨工作区泄露。

## 模型列表

`GET /api/models`

返回示例：

```json
[
  {
    "id": "mock-chat",
    "provider": "mock",
    "name": "Mock Demo Chat",
    "capabilities": ["chat", "stream", "tools"],
    "enabled": true
  },
  {
    "id": "local-embedding",
    "provider": "local",
    "name": "Deterministic Demo Embedding",
    "capabilities": ["embedding"],
    "enabled": true
  }
]
```

配置了相应后端 Key 的供应商才会出现；Ollama 需要 `OLLAMA_ENABLED=true`。前端可以选择 `model_id` 和 `embedding_model_id`，但不能配置或读取 API Key。

## SSE 流式诊断

`POST /api/chat/stream`

请求：

```json
{
  "workspace_id": "ws-demo",
  "knowledge_base_id": "kb-demo",
  "question": "FastAPI 返回 422，如何定位是 Pydantic 参数校验还是前端请求格式问题？",
  "model_id": "mock-chat",
  "embedding_model_id": "local-embedding",
  "code": "",
  "language": "",
  "filters": {
    "document_types": ["markdown"],
    "tags": ["fastapi"]
  },
  "require_patch": false
}
```

请求进入 Agent 状态机后以 `text/event-stream` 返回：

```text
event: plan
data: {"type":"plan","step":"问题理解",...}

event: retrieval
data: {"type":"retrieval","data":{"citations":[...]},...}
event: tool
data: {"type":"tool","step":"代码静态检查",...}
event: answer_delta
data: {"type":"answer_delta","data":{"delta":"..."},...}
event: citation
data: {"type":"citation","data":{"citations":[...]},...}
event: done
data: {"type":"done","data":{"citations":[...],"answer":"..."},...}
```

可能的事件：

- `plan`：固定 Agent 计划
- `retrieval`：向量/关键词召回统计和引用候选
- `tool`：静态检查或安全沙箱结果
- `answer_delta`：模型流式输出片段
- `citation`：最终引用
- `approval_required`：高风险 Patch 人工确认门；当前仅展示预览，不执行 apply
- `answer`：无证据拒答
- `done`：流程结束

如果混合检索没有达到证据阈值，直接返回 `answer`，并在 `done.data.citations` 中返回空数组，避免编造。

## 工具接口

### 静态检查

`POST /api/diagnostics/static-check`

```json
{
  "language": "python",
  "code": "def handler(:\\n    pass"
}
```

支持 `python`、`javascript`、`typescript`，返回 `ok`、`findings` 和 `summary`。

### 沙箱语法检查

`POST /api/diagnostics/sandbox`

```json
{
  "language": "python",
  "code": "print('hello')",
  "command": "syntax-check"
}
```

MVP 仅允许白名单语法检查，使用临时目录、超时和输出限制，不挂载宿主机目录、不允许任意 shell。


沙箱运行时说明：Python 使用 `py_compile`；JavaScript 使用 Node.js `--check`；TypeScript 需要后端镜像或 PATH 提供 `tsc`。缺少 `tsc` 时接口返回 `status=unavailable`，静态规则检查仍可使用。超时由 `SANDBOX_TIMEOUT_SECONDS` 控制。

## 错误码

- `400`：模型未启用或请求参数不合法
- `401`：缺少/无效演示 Token
- `403`：无工作区、知识库或任务权限
- `404`：资源不存在
- `413`：上传文件超过 20 MB
- `415`：不支持的文件类型
- `501`：P1 功能暂未实现（当前为 Git URL 导入）
