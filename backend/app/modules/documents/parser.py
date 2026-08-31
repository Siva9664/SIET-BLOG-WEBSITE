import io
import re
from typing import Any, Dict, List

import fitz  # PyMuPDF
import docx


def detect_section_label(text_snippet: str) -> str | None:
    """
    Detects if a text snippet represents a heading or section label.
    """
    lines = [line.strip() for line in text_snippet.splitlines() if line.strip()]
    if not lines:
        return None
    first = lines[0]
    # Check common section heading patterns (e.g. "Section 1", "1. Introduction", ALL CAPS lines)
    if len(first) < 80:
        if first.isupper() and len(first) > 3:
            return first.title()
        if re.match(r"^(?:Section|Chapter|\d+\.|\d+\)|\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b)", first):
            return first
    return None


def parse_document_spans(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Parses a document byte stream into structured, page-aware text spans.
    Each span dict contains:
    - page_number: int (1-based)
    - text: str
    - char_start: int
    - char_end: int
    - section_label: str | None
    """
    filename_lower = filename.lower()
    spans: List[Dict[str, Any]] = []
    running_char_offset = 0

    if filename_lower.endswith(".pdf"):
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        current_section = None
        for page_idx in range(len(doc)):
            page_num = page_idx + 1
            page = doc.load_page(page_idx)
            page_text = page.get_text("text") or ""
            if not page_text.strip():
                continue

            detected = detect_section_label(page_text)
            if detected:
                current_section = detected

            char_start = running_char_offset
            char_end = char_start + len(page_text)
            running_char_offset = char_end + 1  # count page break newline

            spans.append({
                "page_number": page_num,
                "text": page_text,
                "char_start": char_start,
                "char_end": char_end,
                "section_label": current_section or f"Page {page_num}",
            })

    elif filename_lower.endswith(".docx"):
        doc = docx.Document(io.BytesIO(file_bytes))
        current_page = 1
        current_section = None
        current_page_paragraphs: List[str] = []
        page_char_start = running_char_offset

        for para in doc.paragraphs:
            para_text = para.text.strip()
            # Check paragraph style for heading
            style_name = para.style.name.lower() if para.style else ""
            if "heading" in style_name or para_text.isupper() and len(para_text) < 80:
                if para_text:
                    current_section = para_text

            # Check for page break in runs or XML
            has_page_break = False
            for run in para.runs:
                if 'lastRenderedPageBreak' in run._element.xml or 'w:br w:type="page"' in run._element.xml:
                    has_page_break = True
                    break

            if para_text:
                current_page_paragraphs.append(para_text)

            if has_page_break:
                full_page_text = "\n\n".join(current_page_paragraphs)
                if full_page_text.strip():
                    char_start = page_char_start
                    char_end = char_start + len(full_page_text)
                    spans.append({
                        "page_number": current_page,
                        "text": full_page_text,
                        "char_start": char_start,
                        "char_end": char_end,
                        "section_label": current_section or f"Section {current_page}",
                    })
                    page_char_start = char_end + 1
                current_page += 1
                current_page_paragraphs = []

        # Flush remaining paragraphs
        if current_page_paragraphs:
            full_page_text = "\n\n".join(current_page_paragraphs)
            if full_page_text.strip():
                char_start = page_char_start
                char_end = char_start + len(full_page_text)
                spans.append({
                    "page_number": current_page,
                    "text": full_page_text,
                    "char_start": char_start,
                    "char_end": char_end,
                    "section_label": current_section or f"Section {current_page}",
                })

    else:
        # Text or fallback file format
        text_content = file_bytes.decode("utf-8", errors="replace")
        # Split by form feed (\f) if available, otherwise by double line breaks into virtual pages
        raw_pages = text_content.split("\f") if "\f" in text_content else [text_content]
        current_section = None

        for idx, page_str in enumerate(raw_pages, 1):
            if not page_str.strip():
                continue
            detected = detect_section_label(page_str)
            if detected:
                current_section = detected

            char_start = running_char_offset
            char_end = char_start + len(page_str)
            running_char_offset = char_end + 1

            spans.append({
                "page_number": idx,
                "text": page_str,
                "char_start": char_start,
                "char_end": char_end,
                "section_label": current_section or f"Page {idx}",
            })

    return spans
