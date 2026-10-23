"""Production repository seam backed by PostgreSQL + pgvector.

The runnable recruiter demo deliberately uses :class:`InMemoryStore`. This file
shows the production replacement boundary and keeps authorization inside the
retrieval SQL, rather than trusting only API-layer checks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


@dataclass
class PostgresRepository:
    """Async production repository; not wired into the offline default path."""

    session_factory: async_sessionmaker[AsyncSession]

    @classmethod
    def from_settings(cls) -> "PostgresRepository":
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        return cls(async_sessionmaker(engine, expire_on_commit=False))

    async def search_chunks(
        self,
        *,
        user_id: str,
        knowledge_base_id: str,
        query_embedding: list[float],
        query: str,
        limit: int = 6,
        document_types: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        # AI TECH STACK: RAG / VECTOR RETRIEVAL
        # eligible_chunks ??? workspace_members ??????????????/?????
        # ????? pgvector ? tsvector ??????? RRF ??????????????
        query_sql = text("""
            WITH eligible_chunks AS (
              SELECT c.id, c.document_id, c.content, c.locator, c.embedding, c.content_tsv,
                     d.name AS document_name, d.document_type
              FROM document_chunks c
              JOIN documents d ON d.id = c.document_id
              JOIN knowledge_bases kb ON kb.id = c.knowledge_base_id
              JOIN workspace_members wm ON wm.workspace_id = kb.workspace_id
              WHERE c.knowledge_base_id = :kb_id
                AND wm.user_id = CAST(:user_id AS uuid)
                AND (
                  cardinality(CAST(:document_types AS text[])) = 0
                  OR d.document_type = ANY(CAST(:document_types AS text[]))
                )
                AND (
                  cardinality(CAST(:tags AS text[])) = 0
                  OR d.tags && CAST(:tags AS text[])
                )
            ), vector_hits AS (
              SELECT id,
                     row_number() OVER (ORDER BY embedding <=> CAST(:embedding AS vector)) AS rank
              FROM eligible_chunks
              WHERE embedding IS NOT NULL
              ORDER BY embedding <=> CAST(:embedding AS vector)
              LIMIT :candidate_limit
            ), keyword_hits AS (
              SELECT id,
                     row_number() OVER (
                       ORDER BY ts_rank_cd(content_tsv, plainto_tsquery('simple', :query)) DESC
                     ) AS rank
              FROM eligible_chunks
              WHERE content_tsv @@ plainto_tsquery('simple', :query)
              ORDER BY ts_rank_cd(content_tsv, plainto_tsquery('simple', :query)) DESC
              LIMIT :candidate_limit
            )
            SELECT c.id, c.document_id, c.content, c.locator,
                   c.document_name, c.document_type,
                   COALESCE(1.0 / (60 + v.rank), 0)
                     + COALESCE(1.0 / (60 + k.rank), 0) AS score
            FROM eligible_chunks c
            LEFT JOIN vector_hits v ON v.id = c.id
            LEFT JOIN keyword_hits k ON k.id = c.id
            WHERE v.id IS NOT NULL OR k.id IS NOT NULL
            ORDER BY score DESC
            LIMIT :limit
        """)
        embedding = "[" + ",".join(str(float(value)) for value in query_embedding) + "]"
        parameters = {
            "user_id": user_id,
            "kb_id": knowledge_base_id,
            "embedding": embedding,
            "query": query,
            "document_types": document_types or [],
            "tags": tags or [],
            "candidate_limit": max(limit * 4, 20),
            "limit": limit,
        }
        async with self.session_factory() as session:
            result = await session.execute(query_sql, parameters)
            return [dict(row) for row in result.mappings().all()]
