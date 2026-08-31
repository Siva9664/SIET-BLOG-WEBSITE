from typing import Any, Dict
from app.modules.documents.models import DocumentChunk


def confidence_band(score: float) -> str:
    """
    Categorizes confidence score into standardized bands:
    - >= 0.90: high
    - 0.75 - 0.89: review_recommended
    - < 0.75: do_not_auto_publish
    """
    if score >= 0.90:
        return "high"
    elif score >= 0.75:
        return "review_recommended"
    return "do_not_auto_publish"


def to_provenance(
    chunk: DocumentChunk,
    filename: str,
    score: float,
    semantic_score: float = 0.0,
    keyword_score: float = 0.0,
) -> Dict[str, Any]:
    """
    Formats a retrieved DocumentChunk passage into a standardized provenance dict.
    """
    clean_score = round(float(score), 4)
    band = confidence_band(clean_score)

    return {
        "document_id": chunk.document_id,
        "filename": filename,
        "page_number": chunk.page_number,
        "section_label": chunk.section_label or f"Page {chunk.page_number}",
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "score": clean_score,
        "semantic_score": round(float(semantic_score), 4),
        "keyword_score": round(float(keyword_score), 4),
        "confidence_band": band,
        "chunk_id": chunk.id,
        "text": chunk.text,
    }
