import pytest

from app.services.storage import InMemoryStore, chunk_text
from app.services.tasks import TaskService


def test_chunk_text_preserves_content():
    chunks = chunk_text("第一段\n\n第二段\n\n第三段", max_chars=8, overlap=2)
    assert chunks
    assert "第一段" in " ".join(chunks)
    assert "第三段" in " ".join(chunks)


def test_seed_store_has_demo_user_and_permission():
    store = InMemoryStore()
    assert store.users["user-demo"].email == "demo@devmind.local"
    assert store.has_access("user-demo", "ws-demo", "kb-demo")


def test_embedding_is_deterministic():
    from app.services.storage import embed_text
    assert embed_text("FastAPI 422") == embed_text("FastAPI 422")


@pytest.mark.asyncio
async def test_reindex_replaces_existing_document_chunks():
    store = InMemoryStore()
    document = next(item for item in store.documents.values() if item.name == "fastapi-troubleshooting.md")
    old_chunk_ids = {chunk.id for chunk in store.chunks.values() if chunk.document_id == document.id}

    task = await TaskService(store).index_document(document.id, "# 新内容\n\n只保留新的索引内容。".encode("utf-8"))

    new_chunks = [chunk for chunk in store.chunks.values() if chunk.document_id == document.id]
    assert task.status == "succeeded"
    assert len(new_chunks) == 1
    assert old_chunk_ids.isdisjoint({chunk.id for chunk in new_chunks})
    assert new_chunks[0].content == "# 新内容\n\n只保留新的索引内容。"
