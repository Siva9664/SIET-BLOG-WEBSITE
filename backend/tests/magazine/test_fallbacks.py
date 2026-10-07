import io
import docx
import pytest
from app.modules.magazine.end_to_end_pipeline import run_end_to_end_magazine_pipeline

@pytest.mark.asyncio
async def test_fallback_structure():
    # Minimal DOCX with a title and a paragraph
    doc = docx.Document()
    doc.add_heading("Sample Event", level=0)
    doc.add_paragraph("This is a brief description of the event.")
    buf = io.BytesIO()
    doc.save(buf)
    doc_bytes = buf.getvalue()

    result = await run_end_to_end_magazine_pipeline(
        file_bytes=doc_bytes,
        filename="sample.docx",
        raw_notes=None,
        real_photos=[],
        department_or_lab="Test Lab",
        event_name=None,
        event_date=None,
        target_page_budget=2,
        publish_immediately=False,
        use_llm=False,
    )

    assert result is not None
    # Captions should be empty per fallback
    assert getattr(result, "captions", []) == []
    # Projects should be derived from first paragraph(s)
    assert len(result.projects) >= 1
    # No invented achievements
    assert getattr(result, "achievements", []) == []
