from __future__ import annotations

import json
from collections.abc import AsyncIterator

from app.schemas.models import AgentEvent, ChatRequest
from app.services.providers import ProviderGateway
from app.services.rag import HybridRetriever
from app.services.storage import InMemoryStore
from app.services.tools import SafeSandbox, StaticChecker


class AgentOrchestrator:
    def __init__(self, store: InMemoryStore, providers: ProviderGateway, retriever: HybridRetriever) -> None:
        self.store = store
        self.providers = providers
        self.retriever = retriever
        self.static_checker = StaticChecker()
        self.sandbox = SafeSandbox()

    async def run(self, user_id: str, request: ChatRequest) -> AsyncIterator[AgentEvent]:
        # AI TECH STACK: BACKEND ORCHESTRATION
        # 用固定状态机约束 Agent：模型只能生成计划，工具注册表负责权限与安全策略。
        yield AgentEvent(type="plan", step="问题理解", message="识别为技术问题诊断任务，准备检索授权知识库。")
        result = self.retriever.retrieve(user_id, request.workspace_id, request.knowledge_base_id, request.question, request.filters)
        yield AgentEvent(type="retrieval", step="混合检索", status="succeeded", message=f"向量召回 {result.vector_hits} 条，关键词召回 {result.keyword_hits} 条。", data={"citations": [c.model_dump() for c in result.citations]})
        if not result.citations:
            yield AgentEvent(type="answer", step="拒答", status="succeeded", message="根据当前授权知识库，证据不足，无法可靠回答。")
            yield AgentEvent(type="done", status="succeeded", data={"citations": []})
            return

        if request.code:
            language = request.language or self._infer_language(request.code)
            static_result = self.static_checker.check(request.code, language)
            yield AgentEvent(type="tool", step="代码静态检查", status="succeeded", message=static_result.summary, data=static_result.model_dump())
            sandbox_result = await self.sandbox.run(request.code, language)
            yield AgentEvent(type="tool", step="安全沙箱语法检查", status="succeeded" if sandbox_result["ok"] else "failed", message=str(sandbox_result["output"]), data=sandbox_result)

        context = "\n\n".join(f"[{citation.document_name} / {citation.locator}]\n{citation.content}" for citation in result.citations)
        tool_context = "代码已通过工具检查。" if not request.code else "代码静态检查和沙箱检查结果已纳入诊断。"
        system = "你是 DevMind Agent。只能基于提供的知识库证据和工具结果回答；证据不足时明确拒答。回答要给出原因、排查步骤、风险和引用。"
        prompt = f"问题：{request.question}\n\n知识库证据：\n{context}\n\n工具结果：{tool_context}"
        answer_parts: list[str] = []
        async for delta in self.providers.stream_chat(request.model_id, system, prompt):
            answer_parts.append(delta)
            yield AgentEvent(type="answer_delta", step="生成诊断报告", status="running", data={"delta": delta})
        yield AgentEvent(type="citation", step="引用溯源", status="succeeded", data={"citations": [c.model_dump() for c in result.citations]})
        if request.require_patch:
            yield AgentEvent(type="approval_required", step="人工确认", status="waiting", message="已生成临时 Patch 计划，应用前需要人工确认。", data={"risk": "high", "patch_preview": "仅允许应用到临时工作区，不会修改宿主机文件。"})
        yield AgentEvent(type="done", status="succeeded", data={"citations": [c.model_dump() for c in result.citations], "answer": "".join(answer_parts)})

    @staticmethod
    def _infer_language(code: str) -> str:
        return "python" if ("def " in code or "import " in code or "from " in code) else "javascript"


def sse(event: AgentEvent) -> str:
    return f"event: {event.type}\ndata: {json.dumps(event.model_dump(), ensure_ascii=False)}\n\n"
