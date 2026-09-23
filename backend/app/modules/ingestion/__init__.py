"""Deterministic, format-aware source document ingestion."""

from app.modules.ingestion.compat import document_to_spans
from app.modules.ingestion.models import ContentBlock, ImageReference, StructuredDocument
from app.modules.ingestion.parsers import (
    UnsupportedDocumentType,
    detect_document_type,
    parse_document,
)

__all__ = [
    "ContentBlock",
    "ImageReference",
    "StructuredDocument",
    "UnsupportedDocumentType",
    "detect_document_type",
    "document_to_spans",
    "parse_document",
]
