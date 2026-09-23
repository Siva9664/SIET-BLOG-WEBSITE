"""
Advanced 10-Point Validation Engine for Template-Driven Magazine Generation.

Evaluates:
1. Grounding (zero hallucinated facts)
2. Missing required fields
3. Photo/story association (strict event isolation)
4. Text overflow
5. Image overflow
6. Empty regions
7. Excessive whitespace
8. Duplicate photos
9. Template compatibility
10. Page consistency

Supports targeted single-page diagnosis and regeneration planning.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from app.modules.magazine.templates.template_schema import MagazineTemplateSpec, PageTypeSpec


class PageValidationResult(BaseModel):
    page_number: int
    page_type: str
    is_valid: bool = True
    issues: List[str] = Field(default_factory=list)
    grounding_issues: List[str] = Field(default_factory=list)
    photo_issues: List[str] = Field(default_factory=list)
    layout_issues: List[str] = Field(default_factory=list)
    overflow_issues: List[str] = Field(default_factory=list)
    quality_score: float = 1.0
    needs_regeneration: bool = False
    regeneration_reasons: List[str] = Field(default_factory=list)


class MagazineValidationReport(BaseModel):
    total_pages: int
    is_valid: bool = True
    composite_score: float = 1.0
    page_results: List[PageValidationResult] = Field(default_factory=list)
    pages_needing_regeneration: List[int] = Field(default_factory=list)
    all_issues: List[str] = Field(default_factory=list)


def extract_year_dates(text: str) -> Set[str]:
    return set(re.findall(r"\b20\d{2}\b", text))


def extract_standalone_numbers(text: str) -> Set[str]:
    matches = re.findall(r"\b\d+(?:,\d+)*(?:\.\d+)?\b", text)
    filtered = set()
    ignored = {"0", "1", "2", "3", "4", "5", "8", "9", "10", "12", "15", "16", "20", "25", "30", "50", "100", "200", "300"}
    for m in matches:
        if m in ignored:
            continue
        try:
            val = float(m.replace(",", ""))
            if 0.0 <= val <= 1.0:
                continue
        except ValueError:
            pass
        filtered.add(m)
    return filtered


class AdvancedMagazineValidator:
    """
    Validates generated magazine pages and stories against strict editorial and visual criteria.
    """

    def __init__(self, template_spec: MagazineTemplateSpec):
        self.template = template_spec

    def validate_page(
        self,
        page_data: Dict[str, Any],
        source_story: Optional[Dict[str, Any]] = None,
        all_event_photos_map: Optional[Dict[str, List[str]]] = None,
    ) -> PageValidationResult:
        page_num = page_data.get("page_number", 1)
        p_type = page_data.get("page_type", "event")

        result = PageValidationResult(
            page_number=page_num,
            page_type=p_type,
            is_valid=True,
            quality_score=1.0,
        )

        headline = page_data.get("headline", "") or ""
        body = page_data.get("body", "") or ""
        attached_photos = page_data.get("attached_photos", []) or []
        story_id = page_data.get("story_id", "")

        page_spec = self.template.get_page_spec(p_type)

        # ---------------------------------------------------------------------
        # 1. Grounding Validation
        # ---------------------------------------------------------------------
        if source_story:
            source_text = source_story.get("source_text", "") or ""
            source_lower = source_text.lower()
            combined_asst = f"{headline}\n{body}"

            # Check 4-digit years
            asst_years = extract_year_dates(combined_asst)
            src_years = extract_year_dates(source_text)
            ungrounded_years = asst_years - src_years
            if ungrounded_years:
                msg = f"Ungrounded year(s) in page {page_num}: {ungrounded_years}"
                result.grounding_issues.append(msg)
                result.issues.append(msg)

            # Check standalone numbers
            asst_nums = extract_standalone_numbers(combined_asst)
            src_nums = extract_standalone_numbers(source_text)
            ungrounded_nums = asst_nums - src_nums
            if ungrounded_nums:
                msg = f"Ungrounded number(s) in page {page_num}: {ungrounded_nums}"
                result.grounding_issues.append(msg)
                result.issues.append(msg)

            # Check ungrounded prizes
            rankings = ["first prize", "second prize", "gold medal", "silver medal", "winner"]
            for rk in rankings:
                if rk in combined_asst.lower() and rk not in source_lower:
                    msg = f"Ungrounded achievement ranking '{rk}' in page {page_num}"
                    result.grounding_issues.append(msg)
                    result.issues.append(msg)

        # ---------------------------------------------------------------------
        # 2. Missing Required Fields
        # ---------------------------------------------------------------------
        if p_type not in {"cover", "closing_page", "contents"}:
            if not headline.strip():
                msg = f"Page {page_num} missing required headline."
                result.issues.append(msg)
                result.layout_issues.append(msg)
            if not body.strip():
                msg = f"Page {page_num} missing required body text."
                result.issues.append(msg)
                result.layout_issues.append(msg)

        # ---------------------------------------------------------------------
        # 3. Photo/Story Association & Isolation (Strict Invariant)
        # ---------------------------------------------------------------------
        if all_event_photos_map and story_id:
            story_event_ids = set(source_story.get("event_ids", [])) if source_story else set()
            for p_id in attached_photos:
                # Check if this photo was assigned to another story
                for other_story_id, other_photos in all_event_photos_map.items():
                    is_same = (
                        other_story_id == story_id
                        or other_story_id in story_event_ids
                        or story_id.endswith(f"_{other_story_id}")
                        or other_story_id.endswith(f"_{story_id}")
                    )
                    if not is_same and p_id in other_photos:
                        msg = (
                            f"CRITICAL PHOTO ISOLATION VIOLATION: Photo '{p_id}' belongs to "
                            f"event '{other_story_id}' but was attached to page '{page_num}' (story '{story_id}')"
                        )
                        result.photo_issues.append(msg)
                        result.issues.append(msg)

        # ---------------------------------------------------------------------
        # 4. Text Overflow Check
        # ---------------------------------------------------------------------
        word_count = len(body.split())
        headline_word_count = len(headline.split())

        max_body_words = page_spec.body_limits.get("max_words", 400)
        max_headline_words = page_spec.headline_limits.get("max_words", 20)

        if word_count > max_body_words:
            msg = f"Page {page_num} text overflow: {word_count} words exceeds limit of {max_body_words} words."
            result.overflow_issues.append(msg)
            result.issues.append(msg)

        if headline_word_count > max_headline_words:
            msg = f"Page {page_num} headline overflow: {headline_word_count} words exceeds limit of {max_headline_words} words."
            result.overflow_issues.append(msg)
            result.issues.append(msg)

        # ---------------------------------------------------------------------
        # 5. Image Overflow Check
        # ---------------------------------------------------------------------
        max_imgs = page_spec.maximum_images
        if len(attached_photos) > max_imgs:
            msg = f"Page {page_num} image overflow: {len(attached_photos)} photos exceeds max supported ({max_imgs})."
            result.overflow_issues.append(msg)
            result.issues.append(msg)

        # ---------------------------------------------------------------------
        # 6. Empty Regions Check
        # ---------------------------------------------------------------------
        for reg in page_spec.text_regions:
            if reg.role == "headline" and not headline.strip() and p_type != "contents":
                result.layout_issues.append(f"Empty headline region on page {page_num}")
            elif reg.role == "body" and not body.strip() and p_type not in {"cover", "closing_page"}:
                result.layout_issues.append(f"Empty body region on page {page_num}")

        # ---------------------------------------------------------------------
        # 7. Excessive Whitespace Check (Under-density)
        # ---------------------------------------------------------------------
        min_body_words = page_spec.body_limits.get("min_words", 30)
        if p_type not in {"cover", "closing_page", "photo_feature"} and word_count < min_body_words:
            msg = f"Page {page_num} has excessive whitespace: {word_count} words is below min {min_body_words} words."
            result.layout_issues.append(msg)

        # ---------------------------------------------------------------------
        # 8. Duplicate Photos Check
        # ---------------------------------------------------------------------
        if len(attached_photos) != len(set(attached_photos)):
            msg = f"Page {page_num} contains duplicate attached photo IDs: {attached_photos}"
            result.photo_issues.append(msg)
            result.issues.append(msg)

        # ---------------------------------------------------------------------
        # 9. Template Compatibility Check
        # ---------------------------------------------------------------------
        if p_type not in self.template.supported_page_types:
            msg = f"Page type '{p_type}' is not supported by template '{self.template.template_id}'."
            result.issues.append(msg)

        # ---------------------------------------------------------------------
        # 10. Page Consistency Check
        # ---------------------------------------------------------------------
        # Ensure dimensions match standard A4
        if page_spec.width_pt != 595.28 or page_spec.height_pt != 841.89:
            result.layout_issues.append(f"Non-standard page dimensions on page {page_num}")

        # Calculate score and validity
        has_fatal = (
            len(result.grounding_issues) > 0
            or len(result.photo_issues) > 0
            or any("overflow" in iss for iss in result.overflow_issues)
        )

        deductions = (
            len(result.grounding_issues) * 0.4
            + len(result.photo_issues) * 0.4
            + len(result.overflow_issues) * 0.2
            + len(result.layout_issues) * 0.1
        )
        result.quality_score = max(0.0, round(1.0 - deductions, 2))
        result.is_valid = not has_fatal and result.quality_score >= 0.70

        if not result.is_valid:
            result.needs_regeneration = True
            result.regeneration_reasons = list(result.issues)

        return result

    def validate_magazine(
        self,
        pages: List[Dict[str, Any]],
        source_stories_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
        all_event_photos_map: Optional[Dict[str, List[str]]] = None,
    ) -> MagazineValidationReport:
        report = MagazineValidationReport(total_pages=len(pages))
        all_seen_photos: List[str] = []

        for p in pages:
            s_id = p.get("story_id")
            s_data = source_stories_by_id.get(s_id) if source_stories_by_id and s_id else None
            p_res = self.validate_page(p, source_story=s_data, all_event_photos_map=all_event_photos_map)

            report.page_results.append(p_res)
            report.all_issues.extend(p_res.issues)

            if p_res.needs_regeneration:
                report.pages_needing_regeneration.append(p_res.page_number)

            all_seen_photos.extend(p.get("attached_photos", []))

        # Check for cross-page duplicate photos
        if len(all_seen_photos) != len(set(all_seen_photos)):
            report.all_issues.append("Duplicate photo used across multiple magazine pages.")

        report.is_valid = len(report.pages_needing_regeneration) == 0
        scores = [p.quality_score for p in report.page_results]
        report.composite_score = round(sum(scores) / len(scores), 2) if scores else 1.0

        return report
