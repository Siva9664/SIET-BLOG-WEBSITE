import math
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.documents.embeddings import embed_text
from app.modules.documents.models import DocumentChunk, SourceDocument
from app.modules.documents.provenance import to_provenance


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculates cosine similarity between two float vectors."""
    if len(vec1) == 0 or len(vec2) == 0:
        return 0.0
    min_len = min(len(vec1), len(vec2))
    dot = sum(vec1[i] * vec2[i] for i in range(min_len))
    mag1 = math.sqrt(sum(v * v for v in vec1[:min_len]))
    mag2 = math.sqrt(sum(v * v for v in vec2[:min_len]))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


def _compute_keyword_score(query: str, text: str) -> float:
    """Calculates keyword match score based on term frequency and substring coverage."""
    clean_q = query.lower().strip()
    clean_text = text.lower()
    if not clean_q or not clean_text:
        return 0.0

    terms = [t for t in clean_q.split() if len(t) > 2]
    if not terms:
        return 0.0

    matches = 0
    total_freq = 0
    for term in terms:
        count = clean_text.count(term)
        if count > 0:
            matches += 1
            total_freq += count

    coverage = matches / len(terms)
    frequency_boost = min(1.0, total_freq * 0.1)
    exact_phrase_bonus = 0.3 if clean_q in clean_text else 0.0

    score = (coverage * 0.6) + (frequency_boost * 0.2) + exact_phrase_bonus
    return min(1.0, score)


async def retrieve(
    db: AsyncSession,
    query: str,
    top_k: int = 20,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Hybrid retriever combining semantic vector similarity and keyword matching.
    Returns candidates keeping raw semantic_score and keyword_score distinct for reranking.
    """
    filters = filters or {}
    query_vec = await embed_text(query)

    # 1. Fetch chunks matching optional metadata filters
    stmt = (
        select(DocumentChunk, SourceDocument.filename)
        .join(SourceDocument, DocumentChunk.document_id == SourceDocument.id)
    )

    if "document_id" in filters and filters["document_id"]:
        stmt = stmt.where(DocumentChunk.document_id == int(filters["document_id"]))

    if "section_label" in filters and filters["section_label"]:
        stmt = stmt.where(DocumentChunk.section_label.ilike(f"%{filters['section_label']}%"))

    results = list((await db.execute(stmt)).all())
    if not results:
        return []

    candidates: List[Dict[str, Any]] = []

    # 2. Score candidates using both semantic vector distance and keyword signals
    for chunk, filename in results:
        sem_score = 0.0
        if chunk.embedding:
            sem_score = _cosine_similarity(query_vec, chunk.embedding)

        kw_score = _compute_keyword_score(query, chunk.text)

        # Raw combined candidate score (0.6 semantic + 0.4 keyword)
        raw_combined = (sem_score * 0.6) + (kw_score * 0.4)

        prov = to_provenance(
            chunk=chunk,
            filename=filename,
            score=raw_combined,
            semantic_score=sem_score,
            keyword_score=kw_score,
        )
        candidates.append(prov)

    # 3. Sort by raw_combined score and slice top_k
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:top_k]
