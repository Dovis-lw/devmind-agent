from __future__ import annotations

import asyncio
import uuid

from app.services.documents import parse_document
from app.services.storage import InMemoryStore, TaskRecord, chunk_text


class TaskService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create(self, kind: str, workspace_id: str = "", knowledge_base_id: str = "") -> TaskRecord:
        task = TaskRecord(
            id=str(uuid.uuid4()),
            kind=kind,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
        )
        self.store.set_task(task)
        return task

    def _create_document_task(self, document_id: str) -> TaskRecord:
        document = self.store.documents[document_id]
        knowledge_base = self.store.knowledge_bases[document.knowledge_base_id]
        return self.create(
            "document_index",
            workspace_id=knowledge_base.workspace_id,
            knowledge_base_id=document.knowledge_base_id,
        )

    async def index_document(self, document_id: str, content: bytes) -> TaskRecord:
        task = self._create_document_task(document_id)
        await self._run_existing_task(task, document_id, content)
        return task

    def schedule_index(self, document_id: str, content: bytes) -> TaskRecord:
        task = self._create_document_task(document_id)
        # AI TECH STACK: BACKEND ORCHESTRATION
        # 生产环境将此处替换为 Redis/ARQ enqueue；离线演示用 asyncio task 保持 API 可运行。
        asyncio.create_task(self._run_existing_task(task, document_id, content))
        return task

    async def _run_existing_task(self, task: TaskRecord, document_id: str, content: bytes) -> None:
        document = self.store.documents[document_id]
        try:
            task.status, task.progress, task.message = "running", 10, "解析文档"
            self.store.set_task(task)
            document.document_type, document.content = parse_document(document.name, content)
            if not document.content.strip():
                raise ValueError("未解析到可索引文本")
            await asyncio.sleep(0)
            task.progress, task.message = 35, "文本分块"
            self.store.set_task(task)
            chunks = chunk_text(document.content)
            task.progress, task.message = 60, "生成 Embedding"
            self.store.set_task(task)
            self.store.remove_chunks_for_document(document.id)
            for index, chunk_value in enumerate(chunks):
                self.store.add_chunk(document, chunk_value, f"chunk-{index + 1}")
            task.status, task.progress, task.message = "succeeded", 100, f"索引完成，共 {len(chunks)} 个分块"
            document.status = "ready"
            self.store.set_task(task)
        except Exception as exc:
            task.status, task.message = "failed", f"索引失败：{exc}"
            document.status = "failed"
            self.store.set_task(task)
