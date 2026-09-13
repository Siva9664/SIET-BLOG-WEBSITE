"""Local BGE embedding provider for document chunks, templates, and queries."""

from __future__ import annotations

import math
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.modules.documents.models import DocumentChunk

EMBEDDING_MODEL_NAME = "BAAI/bge-base-en-v1.5"
DEFAULT_EMBEDDING_DIM = 768

_model = None


def get_embedding_model():
    """Lazily loads and returns the singleton local BGE-base-en-v1.5 sentence-transformer model."""
    global _model
    if _model is None:
        logger.info(f"Loading local embedding model: {EMBEDDING_MODEL_NAME}")
        from sentence_transformers import SentenceTransformer

        try:
            _model = SentenceTransformer(EMBEDDING_MODEL_NAME, local_files_only=True)
        except Exception:
            _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def _l2_normalize(vec: List[float]) -> List[float]:
    """L2 unit-normalizes a dense float vector."""
    mag = math.sqrt(sum(v * v for v in vec))
    if mag == 0:
        return vec
    return [round(v / mag, 6) for v in vec]


async def embed_text(text: str) -> List[float]:
    """
    Embeds input text into a dense L2-normalized float vector using local bge-base-en-v1.5.
    Sole embedding provider: no external API or hash fallbacks.
    """
    clean_text = text.strip()
    if not clean_text:
        return [0.0] * DEFAULT_EMBEDDING_DIM

    model = get_embedding_model()
    vec = model.encode(clean_text, normalize_embeddings=True)
    return [round(float(v), 6) for v in vec]


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Batch embeds multiple text inputs into dense L2-normalized float vectors using local bge-base-en-v1.5.
    """
    if not texts:
        return []

    cleaned = [t.strip() for t in texts]
    safe_texts = [t if t else " " for t in cleaned]

    model = get_embedding_model()
    embs = model.encode(safe_texts, normalize_embeddings=True, batch_size=32)
    return [[round(float(v), 6) for v in vec] for vec in embs]


async def embed_chunk(chunk: DocumentChunk, db: AsyncSession) -> None:
    """Computes and persists embedding for a single chunk."""
    vec = await embed_text(chunk.text)
    chunk.embedding = vec
    chunk.embedding_model = "bge-base-en-v1.5"
    await db.commit()


async def backfill_embeddings(db: AsyncSession, reembed_all: bool = False) -> int:
    """
    Computes vectors and persists updates for document chunks.
    If reembed_all is True, forces re-embedding of all existing chunks using bge-base-en-v1.5.
    """
    if reembed_all:
        stmt = select(DocumentChunk)
    else:
        stmt = select(DocumentChunk).where(
            (DocumentChunk.embedding == None) | (DocumentChunk.embedding_model != "bge-base-en-v1.5")
        )

    chunks = list((await db.execute(stmt)).scalars().all())
    if not chunks:
        return 0

    texts = [chunk.text for chunk in chunks]
    vectors = await embed_texts(texts)

    for chunk, vec in zip(chunks, vectors):
        chunk.embedding = vec
        chunk.embedding_model = "bge-base-en-v1.5"

    await db.commit()
    logger.info(f"Backfilled bge-base-en-v1.5 embeddings for {len(chunks)} document chunks.")
    return len(chunks)
