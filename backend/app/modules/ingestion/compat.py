"""Compatibility adapters for the existing RAG document-chunk persistence contract."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.modules.ingestion.models import ContentBlock, StructuredDocument


def _block_text(block: ContentBlock) -> str:
    if block.kind == "table" and block.rows:
        return "\n".join(" | ".join(cell for cell in row) for row in block.rows)
    return block.text.strip()


def document_to_spans(document: StructuredDocument) -> list[dict[str, Any]]:
    """
    Converts structured blocks to the legacy, page-aware span shape.

    This keeps DocumentChunk persistence and provenance APIs stable while callers
    adopt the richer ingestion and analysis layers.
    """
    blocks_by_page: dict[int, list[ContentBlock]] = defaultdict(list)
    for block in document.blocks:
        if _block_text(block):
            blocks_by_page[block.page_number].append(block)

    spans: list[dict[str, Any]] = []
    running_offset = 0
    current_section: str | None = None

    for page_number in sorted(blocks_by_page):
        page_blocks = sorted(blocks_by_page[page_number], key=lambda block: block.order)
        page_parts: list[str] = []
        for block in page_blocks:
            text = _block_text(block)
            if block.kind == "heading" and text:
                current_section = text
            page_parts.append(text)

        page_text = "\n\n".join(page_parts).strip()
        if not page_text:
            continue

        char_start = running_offset
        char_end = char_start + len(page_text)
        spans.append(
            {
                "page_number": page_number,
                "text": page_text,
                "char_start": char_start,
                "char_end": char_end,
                "section_label": current_section or f"Page {page_number}",
            }
        )
        running_offset = char_end + 1

    return spans
