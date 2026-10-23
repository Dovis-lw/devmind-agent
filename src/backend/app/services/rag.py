from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.models import Citation, RetrievalFilters
from app.services.storage import InMemoryStore, cosine_similarity, embed_text


@dataclass
class RetrievalResult:
    citations: list[Citation]
    vector_hits: int
    keyword_hits: int


def lexical_terms(text: str) -> set[str]:
    """Keep English identifiers/error codes and add Chinese character bigrams."""
    lowered = text.lower()
    terms = set(re.findall(r"[a-z0-9_./:-]+", lowered))
    for block in re.findall(r"[\u4e00-\u9fff]+", lowered):
        terms.add(block)
        terms.update(block[index : index + 2] for index in range(max(len(block) - 1, 0)))
    return {term for term in terms if term}


class HybridRetriever:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def retrieve(
        self,
        user_id: str,
        workspace_id: str,
        knowledge_base_id: str,
        question: str,
        filters: RetrievalFilters,
        limit: int = 6,
    ) -> RetrievalResult:
        # AI TECH STACK: RAG / VECTOR RETRIEVAL
        # 向量召回解决语义相似，关键词召回保留错误码、函数名和类名；RRF 融合后再做权限/筛选。
        if not self.store.has_access(user_id, workspace_id, knowledge_base_id):
            return RetrievalResult(citations=[], vector_hits=0, keyword_hits=0)

        query_vector = embed_text(question)
        query_terms = lexical_terms(question)
        candidates = []
        for chunk in self.store.chunks_for_kb(knowledge_base_id):
            document = self.store.document(chunk.document_id)
            if filters.document_types and document.document_type not in filters.document_types:
                continue
            if filters.tags and not set(filters.tags).intersection(document.tags):
                continue

            vector_score = cosine_similarity(query_vector, chunk.vector)
            content_terms = lexical_terms(chunk.content)
            keyword_score = len(query_terms & content_terms) / max(len(query_terms), 1)
            # AI TECH STACK: RAG / VECTOR RETRIEVAL
            # 双阈值过滤零证据片段，让上层 Agent 在没有可靠资料时明确拒答。
            if keyword_score == 0 and vector_score < 0.45:
                continue
            if keyword_score > 0 and vector_score < 0.16 and keyword_score < 0.08:
                continue
            candidates.append((chunk, document, vector_score, keyword_score))

        vector_ranked = sorted(candidates, key=lambda item: item[2], reverse=True)
        keyword_ranked = sorted(candidates, key=lambda item: item[3], reverse=True)
        vector_position = {item[0].id: index + 1 for index, item in enumerate(vector_ranked)}
        keyword_position = {item[0].id: index + 1 for index, item in enumerate(keyword_ranked)}
        fused = []
        for chunk, document, vector_score, keyword_score in candidates:
            rrf = 1 / (60 + vector_position[chunk.id]) + 1 / (60 + keyword_position[chunk.id])
            fused.append((rrf, chunk, document, vector_score, keyword_score))
        fused.sort(key=lambda item: item[0], reverse=True)
        citations = [
            Citation(
                chunk_id=chunk.id,
                document_id=document.id,
                document_name=document.name,
                document_type=document.document_type,
                locator=chunk.locator,
                content=chunk.content,
                score=round(score, 4),
            )
            for score, chunk, document, _, _ in fused[:limit]
        ]
        return RetrievalResult(
            citations=citations,
            vector_hits=min(len(vector_ranked), limit),
            keyword_hits=min(len(keyword_ranked), limit),
        )
