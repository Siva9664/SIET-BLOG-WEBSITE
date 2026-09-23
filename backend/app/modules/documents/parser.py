"""Legacy adapter for the persisted RAG span contract.

New callers should use app.modules.ingestion.parse_document and
app.modules.analysis.analyze_document directly.
"""

from typing import Any

from app.modules.ingestion.compat import document_to_spans
from app.modules.ingestion.parsers import parse_document


def detect_section_label(text_snippet: str) -> str | None:
    """Retained for older callers that inspect a page-text snippet."""
    document = parse_document(text_snippet.encode("utf-8"), "snippet.txt")
    for block in document.blocks:
        if block.kind == "heading":
            return block.text
    return None


def parse_document_spans(file_bytes: bytes, filename: str) -> list[dict[str, Any]]:
    """Returns page-aware spans while delegating format parsing to ingestion."""
    return document_to_spans(parse_document(file_bytes, filename))
