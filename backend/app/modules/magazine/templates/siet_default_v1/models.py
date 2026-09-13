"""Data models and schemas for SIET_DEFAULT_V1 magazine template.

Deconstructed from editorial design principles of professional high-density publications
(reference: The Austin Chronicle Vol 30 No 28).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RegionRole(str, Enum):
    """Standardized reusable region roles across all magazine page layouts."""

    HEADLINE = "headline"
    SUBHEADLINE = "subheadline"
    BODY = "body"
    IMAGE_HERO = "image_hero"
    IMAGE_GRID = "image_grid"
    CAPTION = "caption"
    METADATA = "metadata"
    PULL_QUOTE = "pull_quote"
    SIDEBAR = "sidebar"
    DECORATIVE_ELEMENT = "decorative_element"
    PAGE_NUMBER = "page_number"
    SECTION_LABEL = "section_label"


class PageType(str, Enum):
    """The 15 standardized page types supported by SIET_DEFAULT_V1."""

    COVER = "cover"
    CONTENTS = "contents"
    SECTION_OPENER = "section_opener"
    EVENT = "event"
    ACHIEVEMENT = "achievement"
    VICTORY = "victory"
    PROJECT = "project"
    WORKSHOP = "workshop"
    SEMINAR = "seminar"
    FACULTY_ACTIVITY = "faculty_activity"
    STUDENT_ACTIVITY = "student_activity"
    PHOTO_FEATURE = "photo_feature"
    INTERVIEW = "interview"
    NEWS_HIGHLIGHTS = "news_highlights"
    CLOSING = "closing"


class GridSpec(BaseModel):
    """Multi-column modular grid specification."""

    columns: int = Field(..., description="Number of text columns on page (1, 2, or 3).")
    column_width: float = Field(..., description="Calculated width of each column in points.")
    column_gap: float = Field(default=16.0, description="Gutter width between adjacent columns in points.")
    row_gap: float = Field(default=12.0, description="Vertical rhythm spacing between block rows in points.")
    baseline_grid_pt: float = Field(default=12.0, description="Baseline typographical grid height in points.")


class TypographyLevelSpec(BaseModel):
    """Typographical styling specification for a specific text hierarchy level."""

    font_family: str = Field(default="helv", description="Font name (helv, hebo, heit, tiro, tibo, tiit, cour).")
    font_size: float = Field(..., description="Base font size in points.")
    font_size_min: Optional[float] = Field(default=None, description="Minimum scaled font size.")
    font_size_max: Optional[float] = Field(default=None, description="Maximum scaled font size.")
    line_height: float = Field(default=1.2, description="Line leading multiplier.")
    letter_spacing: float = Field(default=0.0, description="Letter spacing tracking.")
    color_hex: str = Field(default="#1F2937", description="Hex text color.")
    font_weight: str = Field(default="normal", description="Weight description (normal, bold, italic).")
    text_transform: Optional[str] = Field(default=None, description="Transform: uppercase, lowercase, capitalize, none.")


class TypographyHierarchySpec(BaseModel):
    """Typographical hierarchy system for a page layout."""

    headline: TypographyLevelSpec
    subheadline: Optional[TypographyLevelSpec] = None
    body: TypographyLevelSpec
    section_label: Optional[TypographyLevelSpec] = None
    metadata: Optional[TypographyLevelSpec] = None
    pull_quote: Optional[TypographyLevelSpec] = None
    caption: Optional[TypographyLevelSpec] = None
    sidebar_title: Optional[TypographyLevelSpec] = None
    sidebar_body: Optional[TypographyLevelSpec] = None


class RegionSpec(BaseModel):
    """Reusable layout region defining physical position, role, typography, and styling."""

    region_key: str = Field(..., description="Unique key for the region within the page.")
    role: RegionRole = Field(..., description="Semantic reusable region role.")
    x_pt: float = Field(..., description="X coordinate in points from page left edge.")
    y_pt: float = Field(..., description="Y coordinate in points from page top edge.")
    width_pt: float = Field(..., description="Width in points.")
    height_pt: float = Field(..., description="Height in points.")
    column_index: Optional[int] = Field(default=None, description="Zero-indexed column allocation.")
    max_words: Optional[int] = Field(default=None, description="Maximum word limit.")
    max_chars: Optional[int] = Field(default=None, description="Maximum character limit.")
    font_family: Optional[str] = Field(default=None, description="Font identifier.")
    font_size: Optional[float] = Field(default=None, description="Base font size in points.")
    font_size_min: Optional[float] = Field(default=None, description="Minimum scaled font size.")
    font_size_max: Optional[float] = Field(default=None, description="Maximum scaled font size.")
    color_hex: str = Field(default="#1F2937", description="Foreground text/content color.")
    align: str = Field(default="left", description="Alignment: left, center, right, justify.")
    background_color_hex: Optional[str] = Field(default=None, description="Optional background fill color.")
    border_color_hex: Optional[str] = Field(default=None, description="Optional stroke border color.")
    border_width: Optional[float] = Field(default=None, description="Optional stroke border width in points.")
    padding: Optional[Dict[str, float]] = Field(default=None, description="Inner padding in points {top, bottom, left, right}.")


class ImageSlotSpec(BaseModel):
    """Image slot definition with strict event association and aspect ratio guidance."""

    slot_key: str = Field(..., description="Unique identifier for the image region.")
    role: str = Field(default="hero", description="Role: hero, grid, portrait, badge.")
    x_pt: float = Field(..., description="X coordinate in points.")
    y_pt: float = Field(..., description="Y coordinate in points.")
    width_pt: float = Field(..., description="Width in points.")
    height_pt: float = Field(..., description="Height in points.")
    aspect_ratio: str = Field(default="16:9", description="Expected aspect ratio (16:9, 4:3, 1:1, 3:2).")
    fit_mode: str = Field(default="cover", description="Fit mode: cover, contain, fill.")
    border_radius: float = Field(default=0.0, description="Corner radius in points.")
    associated_caption_key: Optional[str] = Field(default=None, description="Key of caption region bound to this image.")


class SpacingSpec(BaseModel):
    """Layout spacing and rhythm tokens."""

    paragraph_gap: float = Field(default=8.0, description="Space between paragraphs in points.")
    column_gap: float = Field(default=16.0, description="Gutter space between columns in points.")
    section_gap: float = Field(default=24.0, description="Vertical space separating content sections.")
    margin_inner: float = Field(default=36.0, description="Inner / spine margin in points.")
    margin_outer: float = Field(default=36.0, description="Outer margin in points.")


class PageTypeConfig(BaseModel):
    """Full declarative configuration for a specific page type in SIET_DEFAULT_V1."""

    page_type: PageType = Field(..., description="The unique page type identifier.")
    display_name: str = Field(..., description="Human-readable title of the layout.")
    description: str = Field(..., description="Editorial intent and visual design description.")
    page_dimensions: Dict[str, float] = Field(
        default_factory=lambda: {"width_pt": 595.28, "height_pt": 841.89},
        description="Page dimensions in points (A4 default: 595.28 x 841.89 pt).",
    )
    margins: Dict[str, float] = Field(
        default_factory=lambda: {"top": 36.0, "bottom": 36.0, "left": 36.0, "right": 36.0},
        description="Page margins in points.",
    )
    grid: GridSpec = Field(..., description="Modular grid specification.")
    columns: int = Field(default=2, description="Active columns for the page layout.")
    typography_hierarchy: TypographyHierarchySpec = Field(..., description="Typographical hierarchy scale.")
    regions: List[RegionSpec] = Field(default_factory=list, description="All reusable content regions on the page.")
    image_slots: List[ImageSlotSpec] = Field(default_factory=list, description="All allocated image slots.")
    maximum_image_count: int = Field(default=2, description="Maximum images supported.")
    text_limits: Dict[str, Any] = Field(
        default_factory=lambda: {"min_words": 50, "max_words": 400, "max_headline_words": 14},
        description="Text capacity constraints for validation.",
    )
    spacing: SpacingSpec = Field(default_factory=SpacingSpec, description="Spacing tokens.")
    alignment: str = Field(default="left", description="Default page text alignment.")
    overflow_rules: Dict[str, str] = Field(
        default_factory=lambda: {
            "headline": "scale_down",
            "body": "truncate_with_ellipsis",
            "sidebar": "truncate",
            "caption": "truncate",
        },
        description="Behavior when content exceeds region bounding box.",
    )
    optional_decorative_assets: Dict[str, Any] = Field(
        default_factory=dict,
        description="Decorative configuration: background color, accent borders, seal placement, divider styles.",
    )


class SIETDefaultV1Template(BaseModel):
    """Top-level magazine template container for SIET_DEFAULT_V1."""

    template_id: str = "SIET_DEFAULT_V1"
    name: str = "SIET College Magazine Default Template"
    version: str = "1.0.0"
    description: str = (
        "Professional college magazine template inspired by high-density publication design principles "
        "(Austin Chronicle). Modular multi-column grids, strict typography hierarchy, alternating running folios, "
        "reusable regions, and strict event photo isolation."
    )
    page_types: Dict[str, PageTypeConfig] = Field(
        ..., description="Lookup dictionary mapping PageType value to PageTypeConfig."
    )
    theme_tokens: Dict[str, Any] = Field(
        default_factory=lambda: {
            "primary_color": "#8B0000",        # SIET Deep Crimson
            "secondary_color": "#1A365D",      # SIET Academic Navy
            "accent_gold": "#D97706",          # Honor & Trophy Amber Gold
            "neutral_dark": "#1F2937",         # Charcoal Body Text
            "neutral_muted": "#4B5563",        # Secondary / Caption Gray
            "neutral_light": "#FDFBF7",        # Editorial Cream Canvas
            "card_bg": "#F9FAFB",              # Sidebar Tint
            "border_muted": "#E5E7EB",         # Divider Rule
        }
    )
