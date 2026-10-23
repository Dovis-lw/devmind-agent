from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
import uuid

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.schemas.models import (
    ChatRequest,
    DocumentTextCreate,
    KnowledgeBaseCreate,
    LoginRequest,
    LoginResponse,
    ModelOut,
    SandboxRequest,
    StaticCheckRequest,
    TaskOut,
    UserOut,
    WorkspaceOut,
)
from app.services.agent import AgentOrchestrator, sse
from app.services.documents import infer_document_type, is_supported_document, safe_filename
from app.services.providers import ProviderGateway
from app.services.rag import HybridRetriever
from app.services.storage import InMemoryStore, KnowledgeBase
from app.services.tasks import TaskService
from app.services.tools import SafeSandbox, StaticChecker

MAX_UPLOAD_BYTES = 20 * 1024 * 1024

app = FastAPI(title="DevMind Agent API", version="0.1.0", description="研发知识库诊断 Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = InMemoryStore()
providers = ProviderGateway()
retriever = HybridRetriever(store)
tasks = TaskService(store)
orchestrator = AgentOrchestrator(store, providers, retriever)
checker = StaticChecker()
sandbox = SafeSandbox()


def current_user(authorization: str | None = Header(default=None)):
    # AI TECH STACK: BACKEND ORCHESTRATION
    # 生产版本替换为 JWT 验证；演示 Token 让面试现场无需额外注册流程。
    if authorization and authorization.removeprefix("Bearer ") == "demo-token":
        return store.users["user-demo"]
    raise HTTPException(status_code=401, detail="请先登录")


def accessible_knowledge_base(knowledge_base_id: str, user):
    kb = store.knowledge_bases.get(knowledge_base_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if not store.has_access(user.id, kb.workspace_id, knowledge_base_id):
        raise HTTPException(status_code=403, detail="无权访问知识库")
    return kb


def require_editor(user, workspace_id: str) -> None:
    if store.role(user.id, workspace_id) not in {"owner", "editor"}:
        raise HTTPException(status_code=403, detail="需要 Editor 或 Owner 权限")


def serialize_document(document) -> dict[str, str]:
    return {
        "id": document.id,
        "knowledge_base_id": document.knowledge_base_id,
        "name": document.name,
        "document_type": document.document_type,
        "status": document.status,
        "source": document.source,
        "tags": document.tags,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "devmind-agent"}


@app.post("/api/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    user = next((u for u in store.users.values() if u.email == payload.email and u.password == payload.password), None)
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    return LoginResponse(access_token="demo-token", user=UserOut(id=user.id, email=user.email, display_name=user.display_name))


@app.get("/api/me", response_model=UserOut)
async def me(user=Depends(current_user)) -> UserOut:
    return UserOut(id=user.id, email=user.email, display_name=user.display_name)


@app.get("/api/workspaces", response_model=list[WorkspaceOut])
async def list_workspaces(user=Depends(current_user)) -> list[WorkspaceOut]:
    return [WorkspaceOut(id=workspace.id, name=workspace.name, role=role) for workspace, role in store.workspace_list(user.id)]


@app.get("/api/workspaces/{workspace_id}/knowledge-bases", response_model=list)
async def list_knowledge_bases(workspace_id: str, user=Depends(current_user)):
    if store.role(user.id, workspace_id) is None:
        raise HTTPException(status_code=403, detail="无权访问工作区")
    return [
        {
            "id": kb.id,
            "workspace_id": kb.workspace_id,
            "name": kb.name,
            "description": kb.description,
            "document_count": len([d for d in store.documents.values() if d.knowledge_base_id == kb.id]),
        }
        for kb in store.kb_list(workspace_id)
    ]


@app.post("/api/workspaces/{workspace_id}/knowledge-bases")
async def create_knowledge_base(workspace_id: str, payload: KnowledgeBaseCreate, user=Depends(current_user)):
    require_editor(user, workspace_id)
    kb = KnowledgeBase(f"kb-{uuid.uuid4().hex[:8]}", workspace_id, payload.name, payload.description)
    store.knowledge_bases[kb.id] = kb
    return {"id": kb.id, "workspace_id": kb.workspace_id, "name": kb.name, "description": kb.description, "document_count": 0}


@app.get("/api/knowledge-bases/{knowledge_base_id}/documents")
async def list_documents(knowledge_base_id: str, user=Depends(current_user)):
    accessible_knowledge_base(knowledge_base_id, user)
    return [serialize_document(d) for d in store.documents.values() if d.knowledge_base_id == knowledge_base_id]


@app.post("/api/knowledge-bases/{knowledge_base_id}/documents")
async def upload_document(knowledge_base_id: str, file: UploadFile = File(...), user=Depends(current_user)):
    kb = accessible_knowledge_base(knowledge_base_id, user)
    require_editor(user, kb.workspace_id)
    name = safe_filename(file.filename or "untitled.txt")
    if not is_supported_document(name):
        raise HTTPException(status_code=415, detail="仅支持 PDF、DOCX、Markdown、TXT、Python、JavaScript、TypeScript 和 ZIP")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="不能上传空文件")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="单文件不能超过 20MB")
    document = store.add_document(knowledge_base_id, name, infer_document_type(name), "upload", "")
    task = tasks.schedule_index(document.id, content)
    return {"document": serialize_document(document), "task": TaskOut(**task.__dict__).model_dump(mode="json")}


@app.post("/api/knowledge-bases/{knowledge_base_id}/documents/text")
async def create_text_document(knowledge_base_id: str, payload: DocumentTextCreate, user=Depends(current_user)):
    kb = accessible_knowledge_base(knowledge_base_id, user)
    require_editor(user, kb.workspace_id)
    name = safe_filename(payload.name)
    if not Path(name).suffix:
        suffix = {"markdown": ".md", "text": ".txt", "python": ".py", "javascript": ".js", "typescript": ".ts"}[payload.document_type]
        name += suffix
    document = store.add_document(knowledge_base_id, name, payload.document_type, "pasted", "")
    document.tags = list(dict.fromkeys(tag.strip() for tag in payload.tags if tag.strip()))
    task = tasks.schedule_index(document.id, payload.content.encode("utf-8"))
    return {"document": serialize_document(document), "task": TaskOut(**task.__dict__).model_dump(mode="json")}


@app.post("/api/knowledge-bases/{knowledge_base_id}/imports/git", status_code=501)
async def import_git_repository(knowledge_base_id: str, user=Depends(current_user)):
    kb = accessible_knowledge_base(knowledge_base_id, user)
    require_editor(user, kb.workspace_id)
    raise HTTPException(
        status_code=501,
        detail="Git URL 导入属于 P1。当前 MVP 请先导出 ZIP 上传；生产实现将使用 Provider 白名单、凭据隔离和临时目录。",
    )


@app.get("/api/tasks/{task_id}", response_model=TaskOut)
async def get_task(task_id: str, user=Depends(current_user)):
    task = store.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.workspace_id or not task.knowledge_base_id:
        raise HTTPException(status_code=403, detail="任务缺少权限上下文")
    if not store.has_access(user.id, task.workspace_id, task.knowledge_base_id):
        raise HTTPException(status_code=403, detail="无权查看该任务")
    return TaskOut(**task.__dict__)


@app.get("/api/models", response_model=list[ModelOut])
async def list_models(user=Depends(current_user)) -> list[ModelOut]:
    return [ModelOut(**model) for model in providers.models()]


@app.post("/api/chat/stream")
async def chat_stream(payload: ChatRequest, user=Depends(current_user)):
    if not store.has_access(user.id, payload.workspace_id, payload.knowledge_base_id):
        raise HTTPException(status_code=403, detail="无权检索该知识库")
    if payload.model_id not in providers.enabled_model_ids("chat"):
        raise HTTPException(status_code=400, detail="对话模型未由管理员启用")
    if payload.embedding_model_id not in providers.enabled_model_ids("embedding"):
        raise HTTPException(status_code=400, detail="Embedding 模型未由管理员启用")

    async def event_stream() -> AsyncIterator[str]:
        async for event in orchestrator.run(user.id, payload):
            yield sse(event)
            await asyncio.sleep(0)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.post("/api/diagnostics/static-check")
async def static_check(payload: StaticCheckRequest, user=Depends(current_user)):
    return checker.check(payload.code, payload.language)


@app.post("/api/diagnostics/sandbox")
async def sandbox_check(payload: SandboxRequest, user=Depends(current_user)):
    return await sandbox.run(payload.code, payload.language, payload.command)
