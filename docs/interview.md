# 面试讲解话术

## 1 分钟版本

这是一个面向研发团队的技术问题诊断 Agent。用户先把企业技术文档和代码导入知识库，系统在后台完成解析、分块和 Embedding。用户提交错误日志后，Agent 先规划，再用带工作区权限的向量+关键词混合检索找证据，之后调用静态检查和安全沙箱工具，最后流式输出带引用的诊断报告。前端展示每一个 Agent 步骤和后台任务状态，云端模型和 Ollama 都通过统一 Provider Gateway 接入。为了让面试现场无 API Key 也能运行，MVP 默认使用内存 Repository、确定性 Embedding 和 Mock；生产替换 seam 已在 PostgreSQL/pgvector、Redis/ARQ 模块中保留。

## 为什么使用混合检索

向量检索适合自然语言语义相似，全文/关键词检索对 `422`、类名、函数名和路径更准确。两路结果通过 RRF 融合，既保留语义召回，也减少关键符号被语义模型稀释的风险。无可靠候选时拒答，而不是让模型用常识补全。

## 权限如何保证

API 入口先校验用户是否属于工作区和知识库，再把 `user_id`、`workspace_id`、`knowledge_base_id` 带入 Retriever。内存 MVP 在候选遍历前做权限检查；生产 SQL 会 JOIN `workspace_members`、`knowledge_bases` 和 `documents`，在向量和全文召回前过滤，避免先召回后泄露。

## 为什么 Agent 不能直接执行任意命令

Agent 只负责选择注册工具，工具层负责白名单、临时目录、超时、输出限制和敏感文件拦截。当前沙箱只做受限语法检查。高风险动作只产生 Patch 预览和 `approval_required` 事件，必须人工确认；真正 Patch 生成、Diff 和 apply 是 P1，不能说成已经修改了宿主机项目。

## 为什么默认不是 PostgreSQL/Redis

	这是面试 Demo 的可运行性取舍：没有 Docker、数据库或 API Key 时，Mock 模式仍能完整演示上传、RAG、Agent SSE 和工具链。生产切换时，把 FastAPI 依赖的 Store 换成 `PostgresStore`，让 `TaskService` 调用 Redis/ARQ enqueue，并让 API 与 Worker 共同使用持久化 Repository；同时把 64 维 Demo Embedding 换成真实云端 Embedding，并统一向量维度。

## 如何继续演进

下一步会加入真实云端 `/embeddings`、独立 Reranker、OpenTelemetry、评测集、失败重试/取消、会话历史、私有 Git OAuth、管理员模型配置和安全的 Patch apply 流程。
