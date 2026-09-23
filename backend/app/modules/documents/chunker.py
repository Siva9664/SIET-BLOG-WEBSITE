"""Deterministic paragraph-aware document chunking with source offsets."""

import re
from typing import Any


def _paragraphs_with_offsets(text: str) -> list[tuple[str, int, int]]:
    paragraphs: list[tuple[str, int, int]] = []
    for match in re.finditer(r"(?s)\S.*?(?=\n\s*\n|\Z)", text):
        raw_text = match.group(0)
        clean_text = raw_text.strip()
        if not clean_text:
            continue
        leading_whitespace = len(raw_text) - len(raw_text.lstrip())
        start = match.start() + leading_whitespace
        paragraphs.append((clean_text, start, start + len(clean_text)))
    return paragraphs


def chunk_document_spans(
    spans: list[dict[str, Any]],
    target_chunk_size: int = 500,
    overlap_size: int = 100,
) -> list[dict[str, Any]]:
    """
    Chunks document spans by paragraph first, then uses overlapping windows for
    oversized paragraphs. Each chunk preserves offsets into its original span.
    """
    if target_chunk_size <= 0:
        raise ValueError("target_chunk_size must be positive.")
    if overlap_size < 0 or overlap_size >= target_chunk_size:
        raise ValueError("overlap_size must be non-negative and smaller than target_chunk_size.")

    chunks: list[dict[str, Any]] = []

    for span in spans:
        page_number = span["page_number"]
        section_label = span.get("section_label")
        span_text = span["text"]
        base_offset = span["char_start"]
        current_parts: list[str] = []
        current_start: int | None = None
        current_end: int | None = None

        def flush_current() -> None:
            nonlocal current_parts, current_start, current_end
            if current_parts and current_start is not None and current_end is not None:
                chunks.append(
                    {
                        "page_number": page_number,
                        "section_label": section_label,
                        "text": "\n\n".join(current_parts),
                        "char_start": current_start,
                        "char_end": current_end,
                    }
                )
            current_parts = []
            current_start = None
            current_end = None

        for paragraph, relative_start, relative_end in _paragraphs_with_offsets(span_text):
            paragraph_start = base_offset + relative_start
            paragraph_end = base_offset + relative_end
            if len(paragraph) > target_chunk_size:
                flush_current()
                step = target_chunk_size - overlap_size
                for start_index in range(0, len(paragraph), step):
                    raw_window = paragraph[start_index : start_index + target_chunk_size]
                    clean_window = raw_window.strip()
                    if len(clean_window) < 30 and start_index > 0:
                        continue
                    leading_whitespace = len(raw_window) - len(raw_window.lstrip())
                    window_start = paragraph_start + start_index + leading_whitespace
                    chunks.append(
                        {
                            "page_number": page_number,
                            "section_label": section_label,
                            "text": clean_window,
                            "char_start": window_start,
                            "char_end": window_start + len(clean_window),
                        }
                    )
                continue

            projected_size = sum(len(part) for part in current_parts)
            projected_size += 2 * len(current_parts) + len(paragraph)
            if current_parts and projected_size > target_chunk_size:
                flush_current()

            if not current_parts:
                current_start = paragraph_start
            current_parts.append(paragraph)
            current_end = paragraph_end

        flush_current()

    return chunks
