"""Typed, serializable intermediate representation for source documents."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ContentBlock:
    """An ordered, page-aware document element."""

    kind: str
    text: str
    page_number: int
    order: int
    level: int | None = None
    rows: list[list[str]] | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ImageReference:
    """Metadata for an image without duplicating the image binary in the dataset."""

    image_id: str
    page_number: int
    order: int
    source: str | None = None
    alt_text: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StructuredDocument:
    """Format-neutral document representation used by ingestion and analysis."""

    filename: str
    document_type: str
    mime_type: str
    page_count: int
    blocks: list[ContentBlock] = field(default_factory=list)
    images: list[ImageReference] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def text_blocks(self) -> list[ContentBlock]:
        return [block for block in self.blocks if block.text.strip()]

    @property
    def text(self) -> str:
        return "\n\n".join(block.text.strip() for block in self.text_blocks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "document_type": self.document_type,
            "mime_type": self.mime_type,
            "page_count": self.page_count,
            "blocks": [block.to_dict() for block in self.blocks],
            "images": [image.to_dict() for image in self.images],
            "attributes": self.attributes,
        }
