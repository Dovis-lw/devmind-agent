from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class WorkspaceOut(BaseModel):
    id: str
    name: str
    role: Literal["owner", "editor", "viewer"]


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = ""


class KnowledgeBaseOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str
    document_count: int


class TaskOut(BaseModel):
    id: str
    kind: str
    workspace_id: str = ""
    knowledge_base_id: str = ""
    status: Literal["queued", "running", "succeeded", "failed"]
    progress: int
    message: str
    created_at: datetime
    updated_at: datetime


class ModelOut(BaseModel):
    id: str
    provider: str
    name: str
    capabilities: list[str]
    enabled: bool = True


class RetrievalFilters(BaseModel):
    document_types: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class DocumentTextCreate(BaseModel):
    name: str = Field(default="pasted-note.md", min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=200000)
    document_type: Literal["markdown", "text", "python", "javascript", "typescript"] = "text"
    tags: list[str] = Field(default_factory=list, max_length=20)


class ChatRequest(BaseModel):
    workspace_id: str
    knowledge_base_id: str
    question: str = Field(min_length=1, max_length=12000)
    model_id: str = "mock-chat"
    embedding_model_id: str = "local-embedding"
    code: str = ""
    language: str = ""
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters)
    require_patch: bool = False


class StaticCheckRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50000)
    language: Literal["python", "javascript", "typescript"]


class SandboxRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50000)
    language: Literal["python", "javascript", "typescript"]
    command: str = "syntax-check"


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    document_type: str
    locator: str
    content: str
    score: float


class AgentEvent(BaseModel):
    type: str
    step: str = ""
    status: str = "running"
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class DiagnosticFinding(BaseModel):
    level: Literal["error", "warning", "info"]
    line: int | None = None
    message: str
    rule: str = ""


class DiagnosticResult(BaseModel):
    ok: bool
    language: str
    findings: list[DiagnosticFinding]
    summary: str
