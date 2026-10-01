"""Tests for how source text is split and spread across magazine pages (no filler, nothing lost)."""
from app.modules.magazine.end_to_end_pipeline import (
    _distribute_units,
    _expand_units,
    _split_source_sections,
)

DOC = (
    "Symposium 2026\n"
    "Event Date: 2026-09-12\n"
    "Keynote\n"
    "The keynote covered practical AI systems. Students asked many questions about fine-tuning.\n"
    "Expo\n"
    "Forty teams presented projects in vision and NLP.\n"
    "Outcomes\n"
    "The lab plans monthly sessions."
)


def test_title_block_is_kept_not_dropped():
    secs = _split_source_sections(DOC)
    assert secs[0]["title"] == "Symposium 2026"
    assert "Event Date: 2026-09-12" in secs[0]["paras"]
    assert [s["title"] for s in secs] == ["Symposium 2026", "Keynote", "Expo", "Outcomes"]


def test_every_section_text_appears_exactly_once_after_distribution():
    units = [{"title": s["title"], "body": "\n\n".join(s["paras"])} for s in _split_source_sections(DOC)]
    for pages in (1, 2, 3, 4, 6):
        groups = _distribute_units(_expand_units(units, pages), pages)
        assert 1 <= len(groups) <= pages
        flat = " ".join(u["title"] + " " + u["body"] for g in groups for u in g)
        for needle in ("Event Date: 2026-09-12", "practical AI systems", "Forty teams", "monthly sessions"):
            assert flat.count(needle) == 1, (pages, needle)


def test_short_text_is_not_padded_with_filler():
    units = [{"title": "", "body": "One short sentence."}]
    assert len(_distribute_units(_expand_units(units, 4), 4)) == 1


def test_long_unit_is_split_to_fill_requested_pages():
    body = "\n\n".join(f"Paragraph {i}. " + "word " * 40 for i in range(4))
    groups = _distribute_units(_expand_units([{"title": "Long", "body": body}], 3), 3)
    assert len(groups) == 3
import uuid

import pytest
from sqlalchemy import delete, select

import app.modules.auth.models  # noqa: F401  (register all tables)
import app.modules.labs.models  # noqa: F401
import app.modules.media.models  # noqa: F401
from app.core.database import async_session_maker
from app.modules.magazine.end_to_end_pipeline import _slugify, run_end_to_end_magazine_pipeline
from app.modules.magazine.models import Magazine

@pytest.mark.asyncio
async def test_slug_allocation_skips_many_existing_slugs():
    """A dev database that already holds 30+ magazines with the same title must still accept a new one."""
    event = f"slugtest{uuid.uuid4().hex[:8]}"
    base = _slugify(f"{event}: Special Research Digest")
    async with async_session_maker() as db:
        try:
            for slug in [base] + [f"{base}-{i}" for i in range(1, 30)]:
                db.add(Magazine(title="seed", slug=slug, status="published", magazine_type="SPECIAL",
                                target_page_budget=2, publication_year=2026, page_count=1))
            await db.commit()

            res = await run_end_to_end_magazine_pipeline(
                raw_notes="Sensors and smart telemetry units designed by students.",
                department_or_lab="IoT Lab",
                event_name=event,
                target_page_budget=1,
                use_llm=False,
                db=db,
            )
            await db.commit()
            assert res.magazine_id is not None
            assert res.slug == f"{base}-30"
            saved = (await db.execute(select(Magazine.slug).where(Magazine.id == res.magazine_id))).scalar_one()
            assert saved == res.slug  # response slug always equals the saved slug
        finally:
            await db.rollback()
            await db.execute(delete(Magazine).where(Magazine.slug.like(f"{base}%")))
            await db.commit()
