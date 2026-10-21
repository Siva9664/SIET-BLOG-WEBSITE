#!/usr/bin/env python3
"""
CLI Script: Idempotent Vector Embedding Backfill.

Backfills L2-normalized BGE-base-en-v1.5 embeddings for all un-embedded
or stale DocumentChunks and MagazineTemplates in PostgreSQL pgvector tables.
"""

import asyncio
import os
import sys

# Ensure backend root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import all SQLAlchemy models to register relationship target classes (e.g. Lab)
import app.modules.labs.models  # noqa: F401
import app.modules.auth.models  # noqa: F401
import app.modules.news.models  # noqa: F401

from app.core.database import async_session_maker, engine
from app.core.logging import logger
from app.modules.documents.embeddings import backfill_embeddings as backfill_doc_embeddings
from app.modules.magazine.models import MagazineTemplate
from app.modules.magazine.template_retriever import seed_template_embeddings


async def run_vector_backfill(force_reembed: bool = False) -> None:
    logger.info("Starting Idempotent Vector Embedding Backfill (bge-base-en-v1.5)...")
    async with async_session_maker() as db:
        # 1. Backfill Document Chunks
        doc_count = await backfill_doc_embeddings(db, reembed_all=force_reembed)
        logger.info(f"Document Chunks Backfilled: {doc_count}")

        # 2. Backfill Magazine Template Embeddings
        from sqlalchemy import select
        tmpl_stmt = select(MagazineTemplate).where(MagazineTemplate.is_active == True)
        templates = (await db.execute(tmpl_stmt)).scalars().all()
        tmpl_count = 0
        for tmpl in templates:
            seeded = await seed_template_embeddings(db, tmpl.id)
            tmpl_count += seeded

        logger.info(f"Magazine Template Exemplar Embeddings Seeded: {tmpl_count}")
        logger.info("Vector Embedding Backfill complete.")


if __name__ == "__main__":
    force = "--force" in sys.argv
    asyncio.run(run_vector_backfill(force_reembed=force))
