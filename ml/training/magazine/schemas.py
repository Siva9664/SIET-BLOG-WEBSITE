"""
Schemas and data structures for SIET Magazine Training Dataset Builder.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any


class StoryType(str, Enum):
    EVENTS = "events"
    VICTORIES = "victories"
    ACHIEVEMENTS = "achievements"
    PROJECTS = "projects"
    WORKSHOPS = "workshops"
    SEMINARS = "seminars"
    COMPETITIONS = "competitions"
    FACULTY = "faculty"
    STUDENT = "student"
    OTHER = "other"


class PhotoConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    UNCERTAIN = "uncertain"


class LayoutIntent(str, Enum):
    HERO_IMAGE = "hero_image"
    IMAGE_GRID = "image_grid"
    TEXT_AND_IMAGE = "text_and_image"
    FULL_WIDTH_STORY = "full_width_story"
    TWO_COLUMN_ARTICLE = "two_column_article"
    PHOTO_FEATURE = "photo_feature"
    ACHIEVEMENT_FEATURE = "achievement_feature"
    EVENT_PAGE = "event_page"


class PageType(str, Enum):
    EVENT_PAGE = "event_page"
    PHOTO_FEATURE = "photo_feature"
    ACHIEVEMENT_FEATURE = "achievement_feature"
    DEPARTMENT_ROUNDUP = "department_roundup"
    EDITORIAL = "editorial"
    COVER_PAGE = "cover_page"


@dataclass
class PhotoItem:
    photo_id: str
    doc_id: str
    page_number: int
    relative_path: str
    filename: str
    width: Optional[int] = None
    height: Optional[int] = None
    sha256: str = ""
    format: str = "png"
    caption_hint: Optional[str] = None
    order_on_page: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PhotoItem:
        return cls(**data)


@dataclass
class PageData:
    page_number: int
    text: str
    photos: List[PhotoItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_number": self.page_number,
            "text": self.text,
            "photos": [p.to_dict() for p in self.photos]
        }


@dataclass
class DocumentRecord:
    doc_id: str
    filename: str
    file_type: str  # "pdf" | "docx" | "report" | "template"
    total_pages: int
    sha256: str
    pages: List[PageData] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "filename": self.filename,
            "file_type": self.file_type,
            "total_pages": self.total_pages,
            "sha256": self.sha256,
            "pages": [p.to_dict() for p in self.pages]
        }


@dataclass
class StorySegment:
    story_id: str
    doc_id: str
    story_type: str
    page_start: int
    page_end: int
    headline: Optional[str]
    body: str
    date: Optional[str] = None
    people: List[str] = field(default_factory=list)
    organization: Optional[str] = None
    achievement_result: Optional[str] = None
    attached_photos: List[str] = field(default_factory=list)  # List of photo_ids
    photo_confidence: str = PhotoConfidence.HIGH.value
    source_text: str = ""
    lab_department: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StorySegment:
        return cls(**data)


@dataclass
class ExampleRecord:
    messages: List[Dict[str, str]]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "messages": self.messages,
            "metadata": self.metadata
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class AdminFeedbackRecord:
    feedback_id: str
    doc_id: Optional[str]
    story_id: Optional[str]
    ai_output: Any
    admin_correction: Any
    final_approved_output: Any
    correction_type: str  # "grounding_fix", "style_edit", "headline_tweak", "layout_switch", "caption_fix", "typo"
    reason: str
    template_version: str
    model_version: str
    approved: bool
    is_training_eligible: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AdminFeedbackRecord:
        return cls(**data)


@dataclass
class QualityReport:
    total_examples: int = 0
    grounding_passed: int = 0
    grounding_failed: int = 0
    provenance_missing: int = 0
    photo_misassociations: int = 0
    leakage_detected: bool = False
    duplicate_rate: float = 0.0
    passed_all_gates: bool = True
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
