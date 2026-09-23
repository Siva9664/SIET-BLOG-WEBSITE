"""Heading, table, and image-caption analysis without model calls."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.modules.ingestion.models import ContentBlock, ImageReference, StructuredDocument


@dataclass(slots=True)
class HeadingNode:
    text: str
    level: int
    page_number: int
    order: int
    parent_order: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TableSummary:
    page_number: int
    order: int
    row_count: int
    column_count: int
    header: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ImageCaptionLink:
    image_id: str
    page_number: int
    image_order: int
    caption_text: str | None
    caption_order: int | None
    relationship: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StructureAnalysis:
    heading_hierarchy: list[HeadingNode] = field(default_factory=list)
    tables: list[TableSummary] = field(default_factory=list)
    image_caption_links: list[ImageCaptionLink] = field(default_factory=list)

    def summary(self) -> dict[str, int]:
        return {
            "heading_count": len(self.heading_hierarchy),
            "table_count": len(self.tables),
            "image_count": len(self.image_caption_links),
            "linked_caption_count": sum(
                1 for link in self.image_caption_links if link.caption_text
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary(),
            "heading_hierarchy": [node.to_dict() for node in self.heading_hierarchy],
            "tables": [table.to_dict() for table in self.tables],
            "image_caption_links": [
                link.to_dict() for link in self.image_caption_links
            ],
        }


_CAPTION_PREFIX = re.compile(
    r"^(?:figure|fig\.?|photo(?:graph)?|image|table)\s*\d*\s*[:.\-]",
    flags=re.IGNORECASE,
)


def _heading_nodes(blocks: list[ContentBlock]) -> list[HeadingNode]:
    stack: list[HeadingNode] = []
    nodes: list[HeadingNode] = []
    for block in blocks:
        if block.kind != "heading" or not block.text.strip():
            continue
        level = block.level or 1
        while stack and stack[-1].level >= level:
            stack.pop()
        node = HeadingNode(
            text=block.text.strip(),
            level=level,
            page_number=block.page_number,
            order=block.order,
            parent_order=stack[-1].order if stack else None,
        )
        nodes.append(node)
        stack.append(node)
    return nodes


def _table_summaries(blocks: list[ContentBlock]) -> list[TableSummary]:
    summaries: list[TableSummary] = []
    for block in blocks:
        if block.kind != "table":
            continue
        rows = block.rows or []
        column_count = max((len(row) for row in rows), default=0)
        summaries.append(
            TableSummary(
                page_number=block.page_number,
                order=block.order,
                row_count=len(rows),
                column_count=column_count,
                header=rows[0] if rows else [],
            )
        )
    return summaries


def _caption_candidates(blocks: list[ContentBlock]) -> list[ContentBlock]:
    candidates: list[ContentBlock] = []
    for block in blocks:
        text = block.text.strip()
        if not text:
            continue
        if block.kind == "caption" or _CAPTION_PREFIX.match(text):
            candidates.append(block)
    return candidates


def _link_images_to_captions(
    images: list[ImageReference], blocks: list[ContentBlock]
) -> list[ImageCaptionLink]:
    captions = _caption_candidates(blocks)
    links: list[ImageCaptionLink] = []
    for image in images:
        same_page = [
            caption
            for caption in captions
            if caption.page_number == image.page_number
        ]
        nearby = [
            caption
            for caption in same_page
            if abs(caption.order - image.order) <= 3
        ]
        candidates = nearby or same_page
        if candidates:
            caption = min(
                candidates,
                key=lambda candidate: (
                    abs(candidate.order - image.order),
                    0 if candidate.order >= image.order else 1,
                ),
            )
            relationship = (
                "adjacent"
                if abs(caption.order - image.order) <= 1
                else "nearby_same_page"
            )
            links.append(
                ImageCaptionLink(
                    image_id=image.image_id,
                    page_number=image.page_number,
                    image_order=image.order,
                    caption_text=caption.text,
                    caption_order=caption.order,
                    relationship=relationship,
                )
            )
        else:
            links.append(
                ImageCaptionLink(
                    image_id=image.image_id,
                    page_number=image.page_number,
                    image_order=image.order,
                    caption_text=None,
                    caption_order=None,
                    relationship="unlinked",
                )
            )
    return links


def analyze_document(document: StructuredDocument) -> StructureAnalysis:
    """Builds deterministic structural metadata from normalized document blocks."""
    ordered_blocks = sorted(
        document.blocks, key=lambda block: (block.page_number, block.order)
    )
    return StructureAnalysis(
        heading_hierarchy=_heading_nodes(ordered_blocks),
        tables=_table_summaries(ordered_blocks),
        image_caption_links=_link_images_to_captions(document.images, ordered_blocks),
    )
