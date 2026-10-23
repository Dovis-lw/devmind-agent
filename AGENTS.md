# Agent 工作规则

## 开始工作前

1. 阅读 `CONTEXT.md`、`README.md` 和对应的 `docs/` 规格。
2. 在项目根目录执行 `git rev-parse --show-toplevel`。
3. 检查 `git status --short`，不要覆盖已有未提交改动。

## 目录边界

- 生产代码：`src/`
- 测试：`tests/`
- 文档：`docs/`
- 脚本：`scripts/`
- 配置模板：`config/`

## AI 技术栈注释规范

涉及以下能力时，必须保留独立注释，便于求职展示和代码走读：

- `# AI TECH STACK: LLM CALL`
- `# AI TECH STACK: RAG / VECTOR RETRIEVAL`
- `# AI TECH STACK: BACKEND ORCHESTRATION`
- `// AI TECH STACK: FRONTEND INTERACTION`

## 安全

不提交 `.env`、API Key、数据库密码和本机产物。沙箱默认只允许白名单命令，禁止任意宿主机读写和网络访问。

## 验证命令

- `python -m pytest tests -q`
- `python -m compileall src/backend/app`
- `npm run build`（在 `src/frontend`）
