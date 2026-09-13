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
