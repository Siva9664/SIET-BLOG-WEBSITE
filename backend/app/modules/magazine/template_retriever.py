"""Dynamic retrieval-based template example selection using local BGE embeddings."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.modules.documents.embeddings import embed_text, embed_texts
from app.modules.documents.retriever import _cosine_similarity
from app.modules.magazine.models import MagazineTemplate, TemplateEmbedding


DEFAULT_TEMPLATE_EXEMPLARS = [
    {
        "section_type": "featured_story",
        "example_key": "robotics_hardware",
        "content_text": (
            "Autonomous Quadruped Legged Robotics: Team QuadRobo demonstrates real-time spatial "
            "vision and low-latency motor microcontrollers for autonomous warehouse steering. "
            "First place award winner with field trials across unstructured terrain."
        ),
    },
    {
        "section_type": "featured_story",
        "example_key": "ai_ml_quantization",
        "content_text": (
            "Quantum Edge Computing and LLM Quantization Models: Department AI Research Lab "
            "unveils sub-4-bit neural network quantization and high-precision neural architecture "
            "search achieving ultra-low inference latency on embedded IoT hardware."
        ),
    },
    {
        "section_type": "achievements",
        "example_key": "hackathon_national_victory",
        "content_text": (
            "Smart India Hackathon First Place National Victory: Undergraduate student innovators "
            "secure first prize and ₹100,000 cash grant for autonomous plant disease detection "
            "camera functioning completely offline."
        ),
    },
    {
        "section_type": "events_roundup",
        "example_key": "symposium_keynote",
        "content_text": (
            "SIET International Engineering & Innovation Symposium 2026: Dr. S. Sharma delivers "
            "opening keynote to 350 undergraduate researchers and 40 faculty delegates in the "
            "Main Auditorium & Advanced AI Labs."
        ),
    },
    {
        "section_type": "cover",
        "example_key": "cover_title",
        "content_text": "SIET Innovation Digest: Autonomous Edge Robotics & Smart Energy 2026",
    },
    {
        "section_type": "editors_note",
        "example_key": "editors_overview",
        "content_text": (
            "A celebration of student engineering breakthroughs, peer-reviewed publications, "
            "and laboratory innovations driving autonomous technology at Sri Shakthi Institute."
        ),
    },
]


async def seed_template_embeddings(db: AsyncSession, template_id: int) -> int:
    """Populates template_embeddings table for a template using BGE embeddings."""
    stmt = select(MagazineTemplate).where(MagazineTemplate.id == template_id)
    tmpl = (await db.execute(stmt)).scalars().first()
    if not tmpl:
        raise ValueError(f"MagazineTemplate #{template_id} not found.")

    # Remove existing embeddings for this template to ensure fresh state
    await db.execute(delete(TemplateEmbedding).where(TemplateEmbedding.template_id == template_id))

    # Collect exemplars from default library and any template example_outputs
    exemplars = list(DEFAULT_TEMPLATE_EXEMPLARS)

    if tmpl.example_outputs:
        for k, v in tmpl.example_outputs.items():
            if isinstance(v, str) and len(v.strip()) > 10:
                exemplars.append({
                    "section_type": "example_outputs",
                    "example_key": k,
                    "content_text": v.strip(),
                })

    texts = [e["content_text"] for e in exemplars]
    vectors = await embed_texts(texts)

    for exemplar, vec in zip(exemplars, vectors):
        record = TemplateEmbedding(
            template_id=template_id,
            section_type=exemplar["section_type"],
            example_key=exemplar["example_key"],
            content_text=exemplar["content_text"],
            embedding=vec,
            embedding_model="bge-base-en-v1.5",
        )
        db.add(record)

    await db.commit()
    logger.info(f"Seeded {len(exemplars)} template embeddings for template #{template_id}.")
    return len(exemplars)


async def retrieve_template_examples(
    db: AsyncSession,
    template_id: int,
    query_text: str,
    section_type: Optional[str] = None,
    top_k: int = 2,
) -> List[Dict[str, Any]]:
    """
    Retrieves the most semantically relevant exemplar section outputs for a given query/story.
    Dynamic retrieval-based example selection.
    """
    query_vec = await embed_text(query_text)

    stmt = select(TemplateEmbedding).where(TemplateEmbedding.template_id == template_id)
    if section_type:
        stmt = stmt.where(TemplateEmbedding.section_type == section_type)

    rows = list((await db.execute(stmt)).scalars().all())
    if not rows:
        return []

    scored = []
    for row in rows:
        if row.embedding:
            sim = _cosine_similarity(query_vec, row.embedding)
            scored.append({
                "id": row.id,
                "section_type": row.section_type,
                "example_key": row.example_key,
                "content_text": row.content_text,
                "similarity_score": round(sim, 4),
            })

    scored.sort(key=lambda x: x["similarity_score"], reverse=True)
    return scored[:top_k]
