from __future__ import annotations

import hashlib
import math
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Iterable


@dataclass
class User:
    id: str
    email: str
    password: str
    display_name: str


@dataclass
class Workspace:
    id: str
    name: str


@dataclass
class KnowledgeBase:
    id: str
    workspace_id: str
    name: str
    description: str


@dataclass
class Document:
    id: str
    knowledge_base_id: str
    name: str
    document_type: str
    source: str
    content: str
    status: str = "queued"
    tags: list[str] = field(default_factory=list)


@dataclass
class Chunk:
    id: str
    document_id: str
    knowledge_base_id: str
    content: str
    locator: str
    vector: list[float]


@dataclass
class TaskRecord:
    id: str
    kind: str
    # Task ownership is persisted in production so status polling cannot leak
    # another workspace's task metadata.
    workspace_id: str = ""
    knowledge_base_id: str = ""
    status: str = "queued"
    progress: int = 0
    message: str = "等待执行"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class InMemoryStore:
    """离线 Demo Repository；生产部署由 PostgreSQL/pgvector Repository 替换。"""

    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.workspaces: dict[str, Workspace] = {}
        self.memberships: dict[tuple[str, str], str] = {}
        self.knowledge_bases: dict[str, KnowledgeBase] = {}
        self.documents: dict[str, Document] = {}
        self.chunks: dict[str, Chunk] = {}
        self.tasks: dict[str, TaskRecord] = {}
        self._seed()

    def _seed(self) -> None:
        user = User("user-demo", "demo@devmind.local", "devmind-demo", "Demo Developer")
        self.users[user.id] = user
        ws = Workspace("ws-demo", "研发效能工作区")
        self.workspaces[ws.id] = ws
        self.memberships[(user.id, ws.id)] = "owner"
        kb = KnowledgeBase("kb-demo", ws.id, "平台工程知识库", "FastAPI、RAG 与代码规范示例资料")
        self.knowledge_bases[kb.id] = kb
        fastapi_doc = self.add_document(
            kb.id,
            "fastapi-troubleshooting.md",
            "markdown",
            "sample",
            "# FastAPI 常见问题排查\n\nFastAPI 返回 422 通常表示请求体、查询参数或路径参数没有通过 Pydantic 校验。排查时先查看响应中的 detail 数组，确认字段名、类型、必填字段和嵌套结构；再核对前端请求的 Content-Type 是否为 application/json。\n\n在 async 路由中直接调用阻塞式文件解析或 subprocess 会阻塞事件循环，应把重任务放入后台队列。",
        )
        rag_doc = self.add_document(
            kb.id,
            "rag-principles.md",
            "markdown",
            "sample",
            "# 企业 RAG 设计原则\n\n检索结果必须带有文档、页码或代码路径等来源信息。系统应该在证据不足时明确拒答，而不是让模型用常识补全。权限过滤要发生在向量和全文检索结果融合之后的最终裁剪阶段。",
        )
        # Seed documents are indexed too, so a fresh offline demo is immediately queryable.
        for document in (fastapi_doc, rag_doc):
            document.status = "ready"
            for index, chunk in enumerate(chunk_text(document.content)):
                self.add_chunk(document, chunk, f"chunk-{index + 1}")

    def add_document(self, knowledge_base_id: str, name: str, document_type: str, source: str, content: str) -> Document:
        doc = Document(str(uuid.uuid4()), knowledge_base_id, name, document_type, source, content)
        self.documents[doc.id] = doc
        return doc

    def add_chunk(self, document: Document, content: str, locator: str) -> Chunk:
        chunk = Chunk(str(uuid.uuid4()), document.id, document.knowledge_base_id, content, locator, embed_text(content))
        self.chunks[chunk.id] = chunk
        return chunk

    def remove_chunks_for_document(self, document_id: str) -> None:
        """重建索引前删除旧分块，避免重复索引导致召回结果重复。"""
        stale_chunk_ids = [chunk_id for chunk_id, chunk in self.chunks.items() if chunk.document_id == document_id]
        for chunk_id in stale_chunk_ids:
            del self.chunks[chunk_id]

    def chunks_for_kb(self, knowledge_base_id: str) -> Iterable[Chunk]:
        return (c for c in self.chunks.values() if c.knowledge_base_id == knowledge_base_id)

    def document(self, document_id: str) -> Document:
        return self.documents[document_id]

    def task(self, task_id: str) -> TaskRecord:
        return self.tasks[task_id]

    def set_task(self, task: TaskRecord) -> None:
        task.updated_at = datetime.now(UTC)
        self.tasks[task.id] = task

    def has_access(self, user_id: str, workspace_id: str, knowledge_base_id: str) -> bool:
        kb = self.knowledge_bases.get(knowledge_base_id)
        return bool(kb and kb.workspace_id == workspace_id and (user_id, workspace_id) in self.memberships)

    def role(self, user_id: str, workspace_id: str) -> str | None:
        return self.memberships.get((user_id, workspace_id))

    def workspace_list(self, user_id: str) -> list[tuple[Workspace, str]]:
        return [(self.workspaces[wid], role) for (uid, wid), role in self.memberships.items() if uid == user_id]

    def kb_list(self, workspace_id: str) -> list[KnowledgeBase]:
        return [kb for kb in self.knowledge_bases.values() if kb.workspace_id == workspace_id]

    def chunk_count(self, knowledge_base_id: str) -> int:
        return sum(1 for c in self.chunks.values() if c.knowledge_base_id == knowledge_base_id)


def chunk_text(text: str, max_chars: int = 900, overlap: int = 120) -> list[str]:
    normalized = re.sub(r"\r\n?", "\n", text).strip()
    if not normalized:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", normalized) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= max_chars:
            current = f"{current}\n\n{paragraph}".strip()
            continue
        if current:
            chunks.append(current)
        prefix = current[-overlap:] if current else ""
        current = f"{prefix}\n\n{paragraph}".strip()
    if current:
        chunks.append(current)
    return chunks


def embed_text(text: str, dimensions: int = 64) -> list[float]:
    """确定性离线 Embedding；生产环境由 embedding Provider 生成 1536 维向量。"""
    values = [0.0] * dimensions
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        values[index] += 1.0
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    length = min(len(left), len(right))
    return sum(left[i] * right[i] for i in range(length))
