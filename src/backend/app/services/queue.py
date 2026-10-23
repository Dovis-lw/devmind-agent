"""Redis/ARQ queue seam with an asyncio fallback for the offline MVP."""
from __future__ import annotations

from typing import Any

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings


async def get_queue() -> Any:
    """Create an ARQ pool; worker and API can share the same Redis URL."""
    return await create_pool(RedisSettings.from_dsn(settings.redis_url))


async def enqueue_index_document(document_id: str, content: bytes) -> str:
    pool = await get_queue()
    try:
        job = await pool.enqueue_job("index_document", document_id, content)
        return job.job_id if job else "unknown"
    finally:
        await pool.close()
