import re
from typing import Any, Dict, List


def chunk_document_spans(
    spans: List[Dict[str, Any]],
    target_chunk_size: int = 500,
    overlap_size: int = 100,
) -> List[Dict[str, Any]]:
    """
    Chunks document spans by paragraph/section first, falling back to a sliding window
    with overlap when paragraphs exceed target_chunk_size.

    Returns list of chunk dicts:
    - page_number: int
    - section_label: str | None
    - text: str
    - char_start: int
    - char_end: int
    """
    chunks: List[Dict[str, Any]] = []

    for span in spans:
        page_num = span["page_number"]
        sec_label = span.get("section_label")
        span_text = span["text"]
        base_offset = span["char_start"]

        # Split span into natural paragraphs/blocks
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", span_text) if p.strip()]

        current_chunk_text = ""
        current_chunk_start = base_offset

        for para in paragraphs:
            # If a single paragraph is larger than target_chunk_size, split it using sliding window
            if len(para) > target_chunk_size + overlap_size:
                # Flush any accumulated chunk text first
                if current_chunk_text.strip():
                    c_end = current_chunk_start + len(current_chunk_text)
                    chunks.append({
                        "page_number": page_num,
                        "section_label": sec_label,
                        "text": current_chunk_text.strip(),
                        "char_start": current_chunk_start,
                        "char_end": c_end,
                    })
                    current_chunk_text = ""

                # Sliding window split inside large paragraph
                para_offset = span_text.find(para)
                abs_para_start = base_offset + (para_offset if para_offset != -1 else 0)
                
                step = target_chunk_size - overlap_size
                for start_i in range(0, len(para), step):
                    sub_text = para[start_i : start_i + target_chunk_size]
                    if len(sub_text.strip()) < 30 and start_i > 0:
                        continue  # Skip tiny residual trailing fragments
                    
                    sub_start = abs_para_start + start_i
                    sub_end = sub_start + len(sub_text)
                    chunks.append({
                        "page_number": page_num,
                        "section_label": sec_label,
                        "text": sub_text.strip(),
                        "char_start": sub_start,
                        "char_end": sub_end,
                    })

                current_chunk_start = base_offset + len(span_text)

            elif len(current_chunk_text) + len(para) + 2 <= target_chunk_size:
                if not current_chunk_text:
                    para_pos = span_text.find(para)
                    current_chunk_start = base_offset + (para_pos if para_pos != -1 else 0)
                    current_chunk_text = para
                else:
                    current_chunk_text += "\n\n" + para
            else:
                # Flush accumulated chunk and start new chunk with para
                c_end = current_chunk_start + len(current_chunk_text)
                chunks.append({
                    "page_number": page_num,
                    "section_label": sec_label,
                    "text": current_chunk_text.strip(),
                    "char_start": current_chunk_start,
                    "char_end": c_end,
                })
                para_pos = span_text.find(para)
                current_chunk_start = base_offset + (para_pos if para_pos != -1 else 0)
                current_chunk_text = para

        # Flush trailing chunk for the span
        if current_chunk_text.strip():
            c_end = current_chunk_start + len(current_chunk_text)
            chunks.append({
                "page_number": page_num,
                "section_label": sec_label,
                "text": current_chunk_text.strip(),
                "char_start": current_chunk_start,
                "char_end": c_end,
            })

    return chunks
