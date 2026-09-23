"""
Pydantic schemas and dataclasses for configuration-driven magazine templates.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class TextRegionSpec(BaseModel):
    region_key: str = Field(..., description="Unique key for text region (e.g. headline, body_col1).")
    role: str = Field(..., description="Role of region: headline, subheadline, body, callout, meta_bar, header, footer.")
    x_pt: float = Field(..., description="X coordinate in points from left.")
    y_pt: float = Field(..., description="Y coordinate in points from top.")
    width_pt: float = Field(..., description="Width in points.")
    height_pt: float = Field(..., description="Height in points.")
    max_words: Optional[int] = Field(default=None, description="Max word count for region.")
    max_chars: Optional[int] = Field(default=None, description="Max char count for region.")
    font_size_min: float = Field(default=9.0, description="Minimum scalable font size.")
    font_size_max: float = Field(default=12.0, description="Maximum initial font size.")
    font_family: str = Field(default="helv", description="Font name (helv, times, courier).")
    color_hex: str = Field(default="#1F2937", description="Text color hex code.")
    align: str = Field(default="left", description="Alignment: left, center, right, justify.")


class ImageRegionSpec(BaseModel):
    region_key: str = Field(..., description="Unique key for image region (e.g. hero_img, grid_img_1).")
    role: str = Field(default="image", description="Role: hero, secondary, grid, badge, banner.")
    x_pt: float = Field(..., description="X coordinate in points from left.")
    y_pt: float = Field(..., description="Y coordinate in points from top.")
    width_pt: float = Field(..., description="Width in points.")
    height_pt: float = Field(..., description="Height in points.")
    aspect_ratio: str = Field(default="16:9", description="Expected aspect ratio (16:9, 4:3, 1:1, 3:2).")
    fit_mode: str = Field(default="cover", description="Fit mode: cover, contain, fill.")
    border_radius: float = Field(default=0.0, description="Corner radius in points.")


class CaptionRegionSpec(BaseModel):
    region_key: str = Field(..., description="Unique key for caption region.")
    associated_image_key: str = Field(..., description="Target image region key.")
    x_pt: float = Field(..., description="X coordinate in points.")
    y_pt: float = Field(..., description="Y coordinate in points.")
    width_pt: float = Field(..., description="Width in points.")
    height_pt: float = Field(..., description="Height in points.")
    max_words: int = Field(default=15, description="Max words allowed in caption.")
    font_size: float = Field(default=8.0, description="Caption font size.")
    color_hex: str = Field(default="#4B5563", description="Caption font color.")


class PageTypeSpec(BaseModel):
    page_type: str = Field(..., description="Page type identifier (e.g. cover, event, workshop, photo_feature).")
    display_name: str = Field(..., description="Human-readable title.")
    description: str = Field(..., description="Editorial and visual intent description.")
    width_pt: float = Field(default=595.28, description="Page width in points (A4 portrait = 595.28).")
    height_pt: float = Field(default=841.89, description="Page height in points (A4 portrait = 841.89).")
    margins: Dict[str, float] = Field(
        default_factory=lambda: {"top": 36.0, "bottom": 36.0, "left": 36.0, "right": 36.0}
    )
    maximum_images: int = Field(default=2, description="Maximum images this page layout supports.")
    headline_limits: Dict[str, int] = Field(
        default_factory=lambda: {"max_chars": 120, "max_words": 16}
    )
    body_limits: Dict[str, int] = Field(
        default_factory=lambda: {"min_words": 40, "max_words": 350}
    )
    spacing: Dict[str, float] = Field(
        default_factory=lambda: {"paragraph_gap": 8.0, "column_gap": 16.0}
    )
    alignment: str = Field(default="left", description="Default text alignment.")
    text_regions: List[TextRegionSpec] = Field(default_factory=list)
    image_regions: List[ImageRegionSpec] = Field(default_factory=list)
    caption_regions: List[CaptionRegionSpec] = Field(default_factory=list)
    decorative_elements: Dict[str, Any] = Field(
        default_factory=lambda: {
            "background_color": "#FDFBF7",
            "accent_border_color": "#8B0000",
            "accent_border_width": 1.0,
            "has_header_bar": True,
            "has_footer_bar": True,
        }
    )


class MagazineTemplateSpec(BaseModel):
    template_id: str = Field(..., description="Unique template identifier (e.g. SIET_DEFAULT_V1).")
    name: str = Field(..., description="Template name.")
    version: str = Field(default="1.0", description="Template schema version.")
    description: str = Field(..., description="Template description.")
    primary_color: str = Field(default="#8B0000", description="Primary brand color (SIET Crimson).")
    secondary_color: str = Field(default="#1A365D", description="Secondary brand color (Navy Blue).")
    background_color: str = Field(default="#FDFBF7", description="Default page background.")
    text_color: str = Field(default="#1F2937", description="Default body text color.")
    supported_page_types: Dict[str, PageTypeSpec] = Field(
        default_factory=dict,
        description="Map of page_type key to PageTypeSpec.",
    )
    def get_page_spec(self, page_type: str) -> PageTypeSpec:
        spec = self.supported_page_types.get(page_type)
        if not spec:
            if page_type == "closing":
                spec = self.supported_page_types.get("closing_page")
            elif page_type == "closing_page":
                spec = self.supported_page_types.get("closing")
            elif page_type in {"achievement", "victory"}:
                spec = self.supported_page_types.get("achievement_victory") or self.supported_page_types.get(page_type)
        if not spec:
            # Fallback to standard event page or first available
            spec = self.supported_page_types.get("event") or next(iter(self.supported_page_types.values()))
        return spec

