"""Pydantic schemas for structured AI generation."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class MagazineEditorialContent(BaseModel):
    """Structured editorial output for magazine issue generation."""

    magazine_issue_title: str = Field(
        ...,
        description="Crisp, authoritative title for this issue (typically 6-12 words).",
    )
    description: str = Field(
        ...,
        description="Factual event overview strictly grounded in source notes (typically 25-40 words).",
    )
    writeup: str = Field(
        ...,
        description="Digest writeup or full article body strictly grounded in source material.",
    )
    captions: List[str] = Field(
        default_factory=list,
        description="List of concise, factual photo captions (max 15 words each).",
    )
    toc_summary: str = Field(
        ...,
        description="One-line summary for the table of contents (max 15 words).",
    )


class EditorialSectionPlan(BaseModel):
    """Plan specifications for an individual issue section."""

    assigned_theme: str = Field(..., description="Content focus and theme to draw from.")
    target_word_count: int = Field(default=50, description="Target word count budget.")
    tone_directive: str = Field(..., description="Directive for tone and editorial style.")
    image_pairing: str = Field(..., description="Guidance on accompanying visual asset.")


class EditorialPlan(BaseModel):
    """Pre-generation editorial plan produced by the orchestrator."""

    real_issue_title: str = Field(..., description="Formulated issue title.")
    title_placement: str = Field(default="Cover Section", description="Section placement.")
    visual_lead_section: str = Field(default="writeup", description="Visual anchor section.")
    sections_plan: Dict[str, EditorialSectionPlan] = Field(
        default_factory=dict,
        description="Section-by-section editorial plan.",
    )


class EditorialReview(BaseModel):
    """Post-generation review evaluation from the orchestrator."""

    overall_score: float = Field(..., description="Overall quality/cohesion score (0.00-1.00).")
    passed: bool = Field(..., description="Whether the issue passes editorial standards (score >= 0.80).")
    summary: str = Field(..., description="Summary explanation of evaluation.")
    section_feedback: Dict[str, str] = Field(
        default_factory=dict,
        description="Actionable section-specific feedback.",
    )


class GeneratedMagazineSections(BaseModel):
    """Plan-conditioned section generation output mapping."""

    title: str = Field(..., description="Generated title section.")
    description: str = Field(..., description="Generated description section.")
    writeup: str = Field(..., description="Generated writeup section.")
    toc_summary: str = Field(..., description="Generated table of contents section.")


class StructuredMagazineStoryContent(BaseModel):
    """
    Qwen3-14B structured magazine-ready editorial content.
    Strictly grounded in source context without coordinate generation.
    """

    section: str = Field(
        ...,
        description="Magazine section (e.g. Department News, Technical Symposia, Campus Life, Achievements).",
    )
    story_type: str = Field(
        ...,
        description="Story type (event, victory, achievement, project, workshop, seminar, faculty_activity, student_activity, photo_feature, other).",
    )
    headline: str = Field(
        ...,
        description="Polished, captivating, publication-ready headline.",
    )
    subheadline: Optional[str] = Field(
        default=None,
        description="Optional subheadline providing context or highlight.",
    )
    polished_body: str = Field(
        ...,
        description="Polished, attractive, professional article text strictly grounded in source facts.",
    )
    short_summary: str = Field(
        ...,
        description="Short digest or Table of Contents summary (max 25 words).",
    )
    photo_captions: List[str] = Field(
        default_factory=list,
        description="Factual photo captions (<= 15 words each) matching attached photos.",
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="Key topical keywords present in the story.",
    )
    page_type: str = Field(
        default="event",
        description="Target page type (cover, contents, event, achievement_victory, project, workshop, seminar, faculty_activity, student_activity, photo_feature, closing_page).",
    )
    layout_intent: str = Field(
        default="text_and_image",
        description="High-level layout intent (hero_image, image_grid, text_and_image, full_width_story, two_column_article, photo_feature, achievement_feature, event_page).",
    )
    recommended_image_count: int = Field(
        default=1,
        description="Recommended number of images to feature on the page.",
    )
    decorative_asset_category: Optional[str] = Field(
        default=None,
        description="Optional decorative or 3D asset category (trophy_3d, tech_circuit, robotics_icon, diploma_ribbon, none).",
    )

