# DevMind Agent 产品规格（MVP）

## 用户与问题

目标用户是开发人员和企业员工。主痛点是：遇到报错或技术问题时，需要在大量项目文档、代码和规范中定位证据，并把检索、分析和安全验证串成可追踪流程。

## 主流程

登录 -> 选择工作区/知识库 -> 上传或粘贴资料 -> 后台索引任务 -> 输入报错/代码问题 -> Agent 规划 -> 权限过滤的混合检索 -> 工具检查 -> 生成引用型诊断报告 -> 必要时进入 Patch 人工确认门。

## P0（当前 MVP 已实现）

- Demo 登录、工作区、知识库和 Owner/Editor/Viewer 权限隔离
- PDF、Word、Markdown、TXT、Python、JavaScript、TypeScript 及 ZIP 代码包导入
- 粘贴文本/代码导入与标签
- 文档解析、文本分块、确定性离线 Embedding、后台任务进度
- 向量/关键词混合检索、RRF、文档类型与标签筛选
- 检索结果中的工作区/知识库权限校验、引用和证据不足拒答
- OpenAI-compatible/Ollama/Mock Provider 抽象与模型白名单
- Agent SSE 流式时间线
- 知识库检索、静态检查、安全沙箱语法检查工具
- Patch 预览占位和 `approval_required` 人工确认事件
- React + TypeScript Web 页面、Docker Compose、OpenAPI 文档

## P1（明确未完成）

- Git URL 导入（当前接口返回 HTTP 501，MVP 建议先导出 ZIP）
- 云端 `/embeddings` 真实调用和多模型维度管理
- Redis/ARQ 与 API 共享 PostgreSQL Repository 的真实异步生产链路
- 失败重试/取消、会话历史、管理员配置页、RAG 评测集和日志导出
- Patch 生成、Diff、确认 API、临时目录 apply

## 非目标

私有 Git OAuth、任意命令执行、宿主机直接修改、多租户计费和复杂组织架构。

## 验收场景

1. 使用演示账号登录，上传或使用内置的 `docs/samples/fastapi-troubleshooting.md`，提问“FastAPI 返回 422 的常见原因是什么？”，回答必须出现检索事件和引用。
2. 提问“如何种植火星土豆？”，回答必须明确说明当前授权知识库证据不足，`citations` 为空。
3. 提交 Python/JS/TS 代码后，时间线出现静态检查和安全沙箱检查。
4. 勾选 Patch 需求后，出现 `approval_required`，但系统不得声称已修改宿主机代码。
