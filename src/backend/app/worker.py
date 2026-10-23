"""ARQ worker entrypoint: arq app.worker.WorkerSettings"""
from __future__ import annotations

from arq.connections import RedisSettings

from app.core.config import settings
from app.services.storage import InMemoryStore
from app.services.tasks import TaskService

store = InMemoryStore()
task_service = TaskService(store)


async def index_document(ctx: dict, document_id: str, content: bytes) -> None:
    """Production job; idempotency can be added with a document version key."""
    await task_service.index_document(document_id, content)


class WorkerSettings:
    functions = [index_document]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 4
    job_timeout = 120
    max_tries = 2
