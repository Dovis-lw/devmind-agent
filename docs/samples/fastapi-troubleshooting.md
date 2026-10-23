# FastAPI 常见问题排查

## 422 Unprocessable Entity

FastAPI 返回 422 通常表示请求体、查询参数或路径参数没有通过 Pydantic 校验。排查时先查看响应中的 `detail` 数组，确认字段名、类型、必填字段和嵌套结构；再核对前端请求的 Content-Type 是否为 application/json。

## 依赖注入

如果 Depends 注入的函数没有返回预期类型，路由可能在运行时失败。建议将数据库会话、当前用户和权限上下文分别封装为依赖，并在测试中覆盖未登录和无权限场景。

## 异步阻塞

在 async 路由中直接调用阻塞式文件解析或 subprocess 会阻塞事件循环。应把重任务放入后台队列，或使用线程池/独立 Worker。
