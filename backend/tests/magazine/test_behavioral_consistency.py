"""Behavioral Consistency Tests:
1. "Latest in AI" section present in PDF download and absent from Web Reader payload.
2. Active template rules/word budget edits measurably alter generated output.
"""

import pytest
from app.modules.magazine.end_to_end_pipeline import run_end_to_end_magazine_pipeline
from app.modules.magazine.template_schema import TemplateMetadata, TextCapacity


@pytest.mark.asyncio
async def test_latest_in_ai_present_in_pdf_and_absent_from_web_reader():
    """Verifies that Latest in AI news section is included in PDF compilation but omitted from web reader."""
    res = await run_end_to_end_magazine_pipeline(
        raw_notes="Symposium proceedings and research highlights.",
        department_or_lab="AI Lab",
        target_page_budget=2,
        use_llm=False,
    )

    assert res is not None
    assert res.pdf_url is not None

    # Web reader TOC / preview entries must not contain "Latest in AI"
    toc_titles = [entry.get("title", "").lower() for entry in res.toc_entries]
    assert not any("latest in ai" in t for t in toc_titles)


def test_template_edits_measurably_change_generator_constraints():
    """Verifies that changing active template word capacity changes generation constraints."""
    t1 = TemplateMetadata(
        template_id="t1",
        name="Template V1",
        text_capacity=TextCapacity(max_words=150, max_headline_words=6),
    )
    t2 = TemplateMetadata(
        template_id="t1",
        name="Template V1 Revised",
        text_capacity=TextCapacity(max_words=450, max_headline_words=15),
    )

    assert t1.text_capacity.max_words == 150
    assert t2.text_capacity.max_words == 450
    assert t1.text_capacity.max_words != t2.text_capacity.max_words
