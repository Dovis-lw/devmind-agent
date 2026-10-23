import pytest

from app.schemas.models import RetrievalFilters
from app.services.rag import HybridRetriever
from app.services.storage import InMemoryStore


def test_hybrid_retrieval_returns_citation_after_indexing() -> None:
    store = InMemoryStore()
    result = HybridRetriever(store).retrieve(
        "user-demo",
        "ws-demo",
        "kb-demo",
        "FastAPI 422 Pydantic",
        RetrievalFilters(),
    )
    assert result.citations
    assert result.citations[0].document_name == "fastapi-troubleshooting.md"


def test_unrelated_question_is_refused() -> None:
    store = InMemoryStore()
    result = HybridRetriever(store).retrieve(
        "user-demo",
        "ws-demo",
        "kb-demo",
        "如何种植火星土豆",
        RetrievalFilters(),
    )
    assert result.citations == []


def test_document_type_filter_is_applied() -> None:
    store = InMemoryStore()
    result = HybridRetriever(store).retrieve(
        "user-demo",
        "ws-demo",
        "kb-demo",
        "FastAPI 422 Pydantic",
        RetrievalFilters(document_types=["pdf"]),
    )
    assert result.citations == []


def test_tag_filter_is_applied() -> None:
    store = InMemoryStore()
    document = next(document for document in store.documents.values() if document.name == "fastapi-troubleshooting.md")
    document.tags = ["backend", "fastapi"]
    matching = HybridRetriever(store).retrieve(
        "user-demo",
        "ws-demo",
        "kb-demo",
        "FastAPI 422 Pydantic",
        RetrievalFilters(tags=["backend"]),
    )
    blocked = HybridRetriever(store).retrieve(
        "user-demo",
        "ws-demo",
        "kb-demo",
        "FastAPI 422 Pydantic",
        RetrievalFilters(tags=["frontend"]),
    )
    assert matching.citations
    assert blocked.citations == []


def test_permission_filter_blocks_unknown_user_and_workspace() -> None:
    store = InMemoryStore()
    retriever = HybridRetriever(store)
    unknown_user = retriever.retrieve("unknown", "ws-demo", "kb-demo", "FastAPI", RetrievalFilters())
    unknown_workspace = retriever.retrieve("user-demo", "ws-other", "kb-demo", "FastAPI", RetrievalFilters())
    assert unknown_user.citations == []
    assert unknown_workspace.citations == []
