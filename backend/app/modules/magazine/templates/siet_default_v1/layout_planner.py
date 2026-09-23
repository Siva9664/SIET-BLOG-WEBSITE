"""Layout Planner Engine for SIET_DEFAULT_V1.

Binds structured Qwen3-14B editorial content to physical template regions and
strictly preserves event photo isolation.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging import logger
from app.infrastructure.ai.schemas import StructuredMagazineStoryContent
from app.modules.magazine.templates.siet_default_v1.models import (
    PageType,
    PageTypeConfig,
    RegionRole,
    SIETDefaultV1Template,
)
from app.modules.magazine.templates.siet_default_v1.config import build_siet_default_v1_template


class SIETDefaultV1LayoutPlanner:
    """
    Deterministic layout planner that maps Qwen editorial stories into
    SIET_DEFAULT_V1 page layouts with strict photo isolation.
    """

    def __init__(self, template: Optional[SIETDefaultV1Template] = None):
        self.template = template or build_siet_default_v1_template()

    def resolve_page_type(
        self,
        story_type: str,
        layout_intent: Optional[str] = None,
        photo_count: int = 0,
    ) -> PageType:
        """
        Determines the optimal PageType from story_type, layout_intent, and photo_count.
        """
        st = story_type.lower().strip()
        li = (layout_intent or "").lower().strip()

        if st in {"interview", "spotlight"} or li == "interview":
            return PageType.INTERVIEW
        elif st in {"news", "highlights", "briefs"} or li in {"news_digest", "capsule_grid"}:
            return PageType.NEWS_HIGHLIGHTS
        elif st in {"photo_feature", "gallery"} or li in {"photo_feature", "gallery"} or photo_count >= 3:
            return PageType.PHOTO_FEATURE
        elif st in {"victory", "championship", "winners"} or li == "victory_celebration":
            return PageType.VICTORY
        elif st in {"achievement", "award", "honor"} or li == "achievement_feature":
            return PageType.ACHIEVEMENT
        elif st in {"project", "innovation", "hackathon_project"} or li == "technical_project":
            return PageType.PROJECT
        elif st in {"workshop", "hands_on", "bootcamp"} or li == "workshop_session":
            return PageType.WORKSHOP
        elif st in {"seminar", "keynote", "lecture", "talk"} or li == "keynote_lecture":
            return PageType.SEMINAR
        elif st in {"faculty", "faculty_activity", "research_grant"}:
            return PageType.FACULTY_ACTIVITY
        elif st in {"student_activity", "club", "cultural", "sports"}:
            return PageType.STUDENT_ACTIVITY
        elif st in {"section_opener", "divider"}:
            return PageType.SECTION_OPENER
        else:
            return PageType.EVENT

    def plan_story_page(
        self,
        page_number: int,
        story_meta: Dict[str, Any],
        content: StructuredMagazineStoryContent,
        department: str,
    ) -> Dict[str, Any]:
        """
        Plans a single magazine page model for a story, strictly binding the story's own photos.
        """
        attached_photos = story_meta.get("attached_photos", [])
        photo_count = len(attached_photos)

        # Resolve Page Type
        resolved_type = self.resolve_page_type(
            story_type=content.story_type,
            layout_intent=content.layout_intent,
            photo_count=photo_count,
        )

        p_cfg = self.template.page_types.get(resolved_type.value)
        if not p_cfg:
            p_cfg = self.template.page_types[PageType.EVENT.value]

        # Region Data Binders
        region_payloads: Dict[str, Any] = {}

        # 1. Headline & Subheadline
        region_payloads["headline"] = content.headline
        region_payloads["subheadline"] = content.subheadline or f"{department} • {content.section}"

        # 2. Section Label
        region_payloads["section_label"] = content.section.upper()

        # 3. Metadata
        meta_items = [department]
        if content.keywords:
            meta_items.append(" • ".join(content.keywords[:3]))
        region_payloads["metadata"] = " | ".join(meta_items)

        # 4. Body Content
        region_payloads["body"] = content.polished_body

        # 5. Pull Quote
        if resolved_type in {PageType.INTERVIEW, PageType.VICTORY, PageType.SECTION_OPENER}:
            region_payloads["pull_quote"] = f"“{content.short_summary}”"

        # 6. Sidebar
        if resolved_type in {PageType.ACHIEVEMENT, PageType.PROJECT, PageType.WORKSHOP, PageType.SEMINAR, PageType.FACULTY_ACTIVITY, PageType.INTERVIEW, PageType.NEWS_HIGHLIGHTS}:
            sidebar_bullets = [
                f"Department: {department}",
                f"Category: {content.story_type.replace('_', ' ').title()}",
            ]
            if content.keywords:
                sidebar_bullets.append(f"Key Focus: {', '.join(content.keywords[:3])}")
            sidebar_bullets.append(f"Highlights: {content.short_summary}")
            region_payloads["sidebar"] = "\n\n• ".join(["KEY HIGHLIGHTS"] + sidebar_bullets)

        # 7. Photos (STRICT EVENT ISOLATION)
        # Allocate strictly up to maximum_image_count from this story's own photos
        allocated_photos = attached_photos[: p_cfg.maximum_image_count]

        # 8. Captions (bound to allocated photos)
        captions = content.photo_captions if content.photo_captions else []
        allocated_captions = captions[: len(allocated_photos)]
        while len(allocated_captions) < len(allocated_photos):
            allocated_captions.append(f"Photograph {len(allocated_captions) + 1}: {content.headline[:40]}")

        return {
            "page_number": page_number,
            "page_type": resolved_type.value,
            "story_id": story_meta.get("story_id"),
            "section": content.section,
            "headline": region_payloads.get("headline", ""),
            "subheadline": region_payloads.get("subheadline", ""),
            "body": region_payloads.get("body", ""),
            "section_label": region_payloads.get("section_label", ""),
            "metadata": region_payloads.get("metadata", ""),
            "pull_quote": region_payloads.get("pull_quote"),
            "sidebar": region_payloads.get("sidebar"),
            "attached_photos": allocated_photos,
            "captions": allocated_captions,
            "keywords": content.keywords,
            "decorative_asset_category": content.decorative_asset_category,
            "page_config": p_cfg,
        }

    def plan_full_magazine(
        self,
        issue_title: str,
        department: str,
        structured_stories: List[Tuple[Dict[str, Any], StructuredMagazineStoryContent]],
    ) -> List[Dict[str, Any]]:
        """
        Plans all pages for an issue: Cover -> Contents -> Stories -> Closing.
        """
        planned_pages: List[Dict[str, Any]] = []
        page_num = 1

        # 1. Cover
        cover_cfg = self.template.page_types[PageType.COVER.value]
        hero_photo = []
        if structured_stories and structured_stories[0][0].get("attached_photos"):
            hero_photo = [structured_stories[0][0]["attached_photos"][0]]

        top_story_headline = structured_stories[0][1].headline if structured_stories else issue_title
        planned_pages.append({
            "page_number": page_num,
            "page_type": PageType.COVER.value,
            "headline": issue_title.upper(),
            "subheadline": f"{department.upper()} • ANNUAL COMPENDIUM",
            "body": f"Featuring: {top_story_headline}",
            "metadata": "VOLUME 30 • ISSUE 1 | ACADEMIC YEAR 2026-2027",
            "attached_photos": hero_photo,
            "captions": [],
            "page_config": cover_cfg,
        })
        page_num += 1

        # 2. Table of Contents
        contents_cfg = self.template.page_types[PageType.CONTENTS.value]
        toc_entries = []
        est_page = 3
        for _, s_content in structured_stories:
            toc_entries.append(f"• Page {est_page}: {s_content.headline}\n  {s_content.short_summary}")
            est_page += 1

        toc_body = "\n\n".join(toc_entries) if toc_entries else "Compilation of department events and achievements."
        planned_pages.append({
            "page_number": page_num,
            "page_type": PageType.CONTENTS.value,
            "headline": "TABLE OF CONTENTS",
            "subheadline": f"Editorial Digest • {department}",
            "body": toc_body,
            "sidebar": (
                "EDITORIAL BOARD\n\n"
                "Chief Patron:\nDr. S. Deepa, Principal\n\n"
                "Executive Editor:\nHead of Department\n\n"
                "Staff Coordinators:\nFaculty Advisory Board\n\n"
                "Student Editors:\nEditorial Working Group\n\n"
                "Published by:\nSIET Publications Desk"
            ),
            "attached_photos": [],
            "captions": [],
            "page_config": contents_cfg,
        })
        page_num += 1

        # 3. Story Pages
        for s_meta, s_content in structured_stories:
            page_data = self.plan_story_page(
                page_number=page_num,
                story_meta=s_meta,
                content=s_content,
                department=department,
            )
            planned_pages.append(page_data)
            page_num += 1

        # 4. Closing Page
        closing_cfg = self.template.page_types[PageType.CLOSING.value]
        planned_pages.append({
            "page_number": page_num,
            "page_type": PageType.CLOSING.value,
            "headline": "IN PURSUIT OF TECHNICAL EXCELLENCE",
            "subheadline": "Sri Shakthi Institute of Engineering and Technology",
            "body": (
                "To innovate, educate, and inspire next-generation engineers with profound ethical "
                "standards and world-class problem-solving capabilities. Congratulations to all students, "
                "faculty, and research labs featured in this edition."
            ),
            "sidebar": (
                "SRI SHAKTHI INSTITUTE OF ENGINEERING AND TECHNOLOGY\n"
                "Affiliated to Anna University | Approved by AICTE | Accredited with 'A' Grade by NAAC\n"
                "Coimbatore - 641062, Tamil Nadu, India\n"
                "Web: www.siet.ac.in | Email: magazine@siet.ac.in"
            ),
            "attached_photos": [],
            "captions": [],
            "page_config": closing_cfg,
        })

        return planned_pages
