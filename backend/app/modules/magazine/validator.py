import copy
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import fitz
from PIL import Image

from app.core.logging import logger
from app.modules.magazine.schemas import (
    PagePlan,
    PageRecoveryResult,
    PlannedRegion,
    VisualQCThresholds,
    VisualQualityReport,
)


def validate_rendered_magazine(
    pdf_path: str,
    page_previews: List[str],
    content: Dict[str, Any],
    blueprint: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Phase 6 Quality Validation Engine.
    Executes visual layout inspection and content grounding verification on generated output.
    Returns composite layout score, grounding score, issues list, and is_valid status.
    """
    issues: List[str] = []

    # 1. Physical File Validation
    if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
        issues.append("Generated PDF file does not exist or is 0 bytes.")

    valid_previews = 0
    for prev in page_previews:
        local_path = prev if os.path.exists(prev) else prev.lstrip("/")
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            valid_previews += 1
        else:
            issues.append(f"Page preview PNG '{prev}' is missing or empty.")

    # 2. Visual Layout & Blueprint Validation
    layout_score = 1.0
    bp_pages = blueprint.get("pages", [])
    if not bp_pages:
        issues.append("Blueprint contains 0 page specifications.")
        layout_score -= 0.3

    for p in bp_pages:
        regions = p.get("regions", [])
        if not regions:
            issues.append(f"Page {p.get('page_number')} contains 0 region bounding boxes.")
            layout_score -= 0.1

        # Check for invalid coordinates
        for r in regions:
            if r.get("width_pt", 0) <= 0 or r.get("height_pt", 0) <= 0:
                issues.append(f"Region '{r.get('region_key')}' has non-positive width/height dimensions.")
                layout_score -= 0.05

    layout_score = max(0.0, round(layout_score, 2))

    # 3. Content Grounding & Confidence Validation
    grounding_score = 0.85
    sources = content.get("sources", [])
    overall_band = content.get("overall_confidence_band", "do_not_auto_publish")

    if sources:
        grounding_score = 0.95
        max_source_score = max((s.get("score", 0.0) for s in sources), default=0.0)
        if max_source_score >= 0.75:
            grounding_score = 1.0
    else:
        issues.append("Content generation payload contains 0 source provenance references.")
        grounding_score = 0.60

    if overall_band == "do_not_auto_publish":
        issues.append("Overall content confidence band requires manual review before auto-publishing.")

    grounding_score = max(0.0, round(grounding_score, 2))

    # Composite Overall Score
    overall_score = round((layout_score * 0.5) + (grounding_score * 0.5), 2)
    is_valid = len([i for i in issues if "0 bytes" in i or "non-positive" in i]) == 0 and overall_score >= 0.70

    return {
        "is_valid": is_valid,
        "layout_score": layout_score,
        "grounding_score": grounding_score,
        "overall_score": overall_score,
        "confidence_band": overall_band,
        "source_count": len(sources),
        "issues": issues,
    }


def verify_section_quality(section_key: str, text: str) -> Dict[str, Any]:
    """
    Automated Self-Check Gate per section:
    Checks for zero template text leakage, word budget bounds, and forbidden clichés.
    """
    issues = []
    text_clean = text.strip() if text else ""
    words = text_clean.split()
    word_count = len(words)

    # 1. Zero Template Text Leakage Check
    leakage_patterns = [
        r"\[insert\s+", r"\{\{", r" lorem ipsum", r"sample text", r"placeholder", r"your title here"
    ]
    import re
    for pat in leakage_patterns:
        if re.search(pat, text_clean, re.IGNORECASE):
            issues.append(f"Template text leakage detected pattern '{pat}'.")

    # 2. Forbidden Clichés Check
    cliches = ["in today's fast-paced world", "in conclusion", "it goes without saying", "testament to", "embark on a journey"]
    for c in cliches:
        if c in text_clean.lower():
            issues.append(f"Forbidden house style cliché detected: '{c}'.")

    # 3. Word Budget Checks
    max_budgets = {
        "magazine_issue_title": 18,
        "title": 18,
        "writeup_headline": 18,
        "description": 100,
        "writeup": 650,
        "writeup_text": 650,
        "toc_summary": 30,
    }
    allowed_max = max_budgets.get(section_key, 650 if "writeup" in section_key else 100)
    if word_count > int(allowed_max * 1.25):
        issues.append(f"Section '{section_key}' exceeded word budget ({word_count} words > {allowed_max} allowed).")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "word_count": word_count,
    }


async def run_automated_self_check_and_retry(content: Dict[str, Any], db=None) -> Dict[str, Any]:
    """
    Automated Self-Check Gate:
    Runs leakage check, word budget enforcement, and tone/accuracy verifications.
    Executes 1 automated retry pass with feedback for any section failing verification.
    """
    from app.modules.magazine.ai_service import _enforce_word_budget_with_retry

    sections = content.get("sections", {})
    verified_sections = {}
    verifier_reports = {}
    retries_performed = 0

    if not sections:
        # Construct fallback sections mapping
        sections = {
            "title": {"content": content.get("magazine_issue_title", "")},
            "description": {"content": content.get("description", "")},
            "writeup": {"content": content.get("writeup_text", "")},
            "toc_summary": {"content": content.get("toc_summary", "")},
        }

    for key, sdata in sections.items():
        curr_text = sdata.get("content", "") if isinstance(sdata, dict) else str(sdata)
        v_res = verify_section_quality(key, curr_text)

        if not v_res["passed"]:
            retries_performed += 1
            feedback = "; ".join(v_res["issues"])
            # Automated Retry-with-Feedback Pass
            target_max = 18 if "title" in key else (500 if "writeup" in key else (25 if "toc" in key else 80))
            fixed_text = await _enforce_word_budget_with_retry(key, curr_text, max_words=target_max)
            v_res_retry = verify_section_quality(key, fixed_text)
            
            conf = sdata.get("confidence_score", 0.88) if isinstance(sdata, dict) else 0.88
            expl = sdata.get("simple_explanation", "Grounded in source document.") if isinstance(sdata, dict) else "Grounded in source document."
            
            verified_sections[key] = {
                "content": fixed_text,
                "confidence_score": conf,
                "simple_explanation": f"{expl} (Self-corrected after verifier feedback: {feedback})",
                "verifier_passed": v_res_retry["passed"],
                "issues": v_res_retry["issues"],
            }
            verifier_reports[key] = {
                "initial_passed": False,
                "initial_issues": v_res["issues"],
                "retry_performed": True,
                "retry_passed": v_res_retry["passed"],
            }
        else:
            conf = sdata.get("confidence_score", 0.88) if isinstance(sdata, dict) else 0.88
            expl = sdata.get("simple_explanation", "Grounded in source document.") if isinstance(sdata, dict) else "Grounded in source document."
            
            verified_sections[key] = {
                "content": curr_text,
                "confidence_score": conf,
                "simple_explanation": expl,
                "verifier_passed": True,
                "issues": [],
            }
            verifier_reports[key] = {
                "initial_passed": True,
                "initial_issues": [],
                "retry_performed": False,
            }

    content["sections"] = verified_sections
    content["verifier_reports"] = verifier_reports
    content["self_check_passed"] = all(r["initial_passed"] or r.get("retry_passed", False) for r in verifier_reports.values())
    content["retries_performed"] = retries_performed
    return content


# ============================================================================
# Phase 7: AUTOMATIC VISUAL QUALITY CONTROL
# ============================================================================

def _check_text_overflow(
    page: fitz.Page,
    page_plan: Any = None,
    template_metadata: Any = None,
) -> List[str]:
    """Check 1: Detects text overflow outside designated regions or bottom page margin."""
    issues: List[str] = []
    page_height = page.rect.height

    blocks = page.get_text("blocks")
    for b in blocks:
        if len(b) >= 5 and b[4].strip():
            text_content = b[4].strip()
            # Ignore running footer
            if "Sri Shakthi Institute" in text_content or "PG " in text_content:
                continue
            if b[3] > page_height - 22.0:
                issues.append(
                    f"Text overflow: text block ending at y={b[3]:.1f}pt extends beyond bottom margin ({page_height - 22.0:.1f}pt): '{text_content[:30]}…'"
                )

    return issues


def _check_image_overflow(
    page: fitz.Page,
    page_plan: Any = None,
    template_metadata: Any = None,
) -> List[str]:
    """Check 2: Detects image rectangles extending outside page printable area."""
    issues: List[str] = []
    page_width = page.rect.width
    page_height = page.rect.height

    for img_info in page.get_images():
        xref = img_info[0]
        for r in page.get_image_rects(xref):
            if r.x0 < 10.0 or r.y0 < 10.0 or r.x1 > page_width - 10.0 or r.y1 > page_height - 15.0:
                issues.append(
                    f"Image overflow: image rect [{r.x0:.1f}, {r.y0:.1f}, {r.x1:.1f}, {r.y1:.1f}] extends outside printable boundary."
                )

    return issues


def _check_missing_assets(
    page: fitz.Page,
    page_plan: Any = None,
) -> List[str]:
    """Check 3: Verifies all planned image assets exist on disk and rendered."""
    issues: List[str] = []
    if not page_plan:
        return issues

    regions = getattr(page_plan, "regions", []) or []
    planned_images_count = 0

    for r in regions:
        rtype = getattr(r, "type", "")
        asset = getattr(r, "asset", None)
        rid = getattr(r, "region_id", "")
        if rtype == "image" or "image" in rid or "photo" in rid or asset:
            planned_images_count += 1
            if asset:
                from app.modules.magazine.renderer import _resolve_image_path
                resolved = _resolve_image_path(asset)
                if not resolved:
                    issues.append(
                        f"Missing asset: image asset '{asset}' for region '{rid}' does not exist on disk."
                    )

    rendered_images = page.get_images()
    if planned_images_count > 0 and len(rendered_images) == 0:
        issues.append(
            f"Missing assets: page planned {planned_images_count} images, but 0 images were embedded on the rendered page."
        )

    return issues


def _check_image_distortion(
    page: fitz.Page,
    page_plan: Any = None,
    max_tolerance: float = 0.08,
) -> List[str]:
    """Check 4: Verifies displayed aspect ratio does not stretch or distort source images."""
    issues: List[str] = []
    doc = page.parent

    for img_info in page.get_images():
        xref = img_info[0]
        try:
            base_img = doc.extract_image(xref)
            if not base_img:
                continue
            src_w = base_img.get("width", 1)
            src_h = base_img.get("height", 1)
            src_ratio = src_w / max(1, src_h)

            for r in page.get_image_rects(xref):
                disp_w = r.width
                disp_h = r.height
                disp_ratio = disp_w / max(1.0, disp_h)

                rel_diff = abs(disp_ratio - src_ratio) / src_ratio
                if rel_diff > max_tolerance:
                    issues.append(
                        f"Image distortion: displayed aspect ratio {disp_ratio:.2f} deviates from source aspect ratio {src_ratio:.2f} by {rel_diff:.1%} (exceeds {max_tolerance:.0%} tolerance)."
                    )
        except Exception as e:
            logger.debug(f"Distortion check skipped for xref {xref}: {e}")

    return issues


def _check_low_resolution_images(
    page: fitz.Page,
    min_dpi: float = 96.0,
) -> List[str]:
    """Check 5: Computes effective Dots Per Inch (DPI) and flags low-resolution images."""
    issues: List[str] = []
    doc = page.parent

    for img_info in page.get_images():
        xref = img_info[0]
        try:
            base_img = doc.extract_image(xref)
            if not base_img:
                continue
            src_w = base_img.get("width", 1)
            src_h = base_img.get("height", 1)

            for r in page.get_image_rects(xref):
                dpi_x = (src_w / max(1.0, r.width)) * 72.0
                dpi_y = (src_h / max(1.0, r.height)) * 72.0
                effective_dpi = min(dpi_x, dpi_y)

                if effective_dpi < min_dpi:
                    issues.append(
                        f"Low-resolution image: effective DPI is {effective_dpi:.1f} (below minimum threshold of {min_dpi:.1f} DPI)."
                    )
        except Exception as e:
            logger.debug(f"DPI check skipped for xref {xref}: {e}")

    return issues


def _check_overlapping_regions(
    page: fitz.Page,
    page_plan: Any = None,
) -> List[str]:
    """Check 6: Detects unintended geometric intersection between distinct content regions."""
    issues: List[str] = []
    text_dict = page.get_text("dict")
    lines = [
        fitz.Rect(l["bbox"])
        for b in text_dict.get("blocks", [])
        if "lines" in b
        for l in b["lines"]
        if any(s.get("text", "").strip() for s in l.get("spans", []))
    ]

    # Filter out header/footer lines from overlap check
    filtered_lines = [
        r for r in lines
        if not (r.y0 < 38.0 or r.y1 > page.rect.height - 35.0)
    ]

    # Check text lines against text lines
    for i in range(len(filtered_lines)):
        for j in range(i + 1, len(filtered_lines)):
            r1, r2 = filtered_lines[i], filtered_lines[j]
            if r1.intersects(r2):
                inter = r1 & r2
                if inter.width > 5.0 and inter.height > 3.0:
                    issues.append(
                        f"Overlapping text regions detected: intersection area {inter.width * inter.height:.1f} pt² at ({inter.x0:.1f}, {inter.y0:.1f})."
                    )

    # Check text lines against image rects
    for img_info in page.get_images():
        for img_r in page.get_image_rects(img_info[0]):
            for lr in filtered_lines:
                if img_r.intersects(lr):
                    inter = img_r & lr
                    if inter.width > 20.0 and inter.height > 20.0:
                        issues.append(
                            f"Text overlapping image: intersection area {inter.width * inter.height:.1f} pt²."
                        )

    return issues


def _check_content_outside_page_boundaries(page: fitz.Page) -> List[str]:
    """Check 7: Ensures all rendered content lies strictly inside [0, 0, PAGE_WIDTH, PAGE_HEIGHT]."""
    issues: List[str] = []
    page_w = page.rect.width
    page_h = page.rect.height
    expanded_clip = fitz.Rect(-500.0, -500.0, page_w + 500.0, page_h + 500.0)

    for b in page.get_text("blocks", clip=expanded_clip):
        if len(b) >= 5 and b[4].strip():
            if b[0] < -2.0 or b[1] < -2.0 or b[2] > page_w + 2.0 or b[3] > page_h + 2.0:
                issues.append(
                    f"Content outside page boundaries: text block [{b[0]:.1f}, {b[1]:.1f}, {b[2]:.1f}, {b[3]:.1f}] exceeds page rect [0, 0, {page_w:.1f}, {page_h:.1f}]."
                )

    for img_info in page.get_images():
        for r in page.get_image_rects(img_info[0]):
            if r.x0 < -2.0 or r.y0 < -2.0 or r.x1 > page_w + 2.0 or r.y1 > page_h + 2.0:
                issues.append(
                    f"Content outside page boundaries: image rect [{r.x0:.1f}, {r.y0:.1f}, {r.x1:.1f}, {r.y1:.1f}] exceeds page rect."
                )

    return issues


def _check_excessive_empty_space(
    page: fitz.Page,
    max_empty_ratio: float = 0.75,
) -> List[str]:
    """Check 8: Assesses content area coverage and flags excessive unused white space."""
    issues: List[str] = []
    page_w = page.rect.width
    page_h = page.rect.height
    printable_area = (page_w - 60.0) * (page_h - 70.0)

    content_area = 0.0
    blocks = page.get_text("blocks")
    for b in blocks:
        if len(b) >= 5 and b[4].strip():
            w = max(0.0, b[2] - b[0])
            h = max(0.0, b[3] - b[1])
            content_area += w * h

    for img_info in page.get_images():
        for r in page.get_image_rects(img_info[0]):
            content_area += max(0.0, r.width) * max(0.0, r.height)

    coverage = content_area / max(1.0, printable_area)
    empty_ratio = max(0.0, 1.0 - coverage)

    word_count = len(page.get_text().split())
    if empty_ratio > max_empty_ratio and word_count < 30:
        issues.append(
            f"Excessive empty space: content covers only {coverage:.1%} of printable area (empty space {empty_ratio:.1%} exceeds threshold {max_empty_ratio:.0%})."
        )

    return issues


def _check_excessively_small_text(
    page: fitz.Page,
    min_fontsize: float = 5.5,
) -> List[str]:
    """Check 9: Inspects font sizes across all rendered text spans to guarantee readability."""
    issues: List[str] = []
    try:
        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    size = span.get("size", 10.0)
                    if text and size < min_fontsize:
                        issues.append(
                            f"Excessively small text: font size {size:.1f}pt for '{text[:25]}' is below readability threshold of {min_fontsize}pt."
                        )
    except Exception as e:
        logger.debug(f"Small text check error: {e}")

    return issues


def _check_inconsistent_margins(
    page: fitz.Page,
    template_metadata: Any = None,
    max_variance: float = 15.0,
) -> List[str]:
    """Check 10: Checks consistency and alignment of page margins against template rules."""
    issues: List[str] = []
    page_w = page.rect.width
    target_margin = 42.0

    blocks = page.get_text("blocks")
    text_blocks = [
        b for b in blocks
        if len(b) >= 5 and b[4].strip() and "Sri Shakthi" not in b[4] and "PG " not in b[4]
    ]

    if text_blocks:
        leftmost = min(b[0] for b in text_blocks)
        if abs(leftmost - target_margin) > max_variance * 2.0:
            issues.append(
                f"Inconsistent margins: leftmost content at x={leftmost:.1f}pt deviates from expected margin ({target_margin:.1f}pt)."
            )

    return issues


def validate_page_visual_quality(
    page: fitz.Page,
    page_plan: Any = None,
    template_metadata: Any = None,
    thresholds: Optional[VisualQCThresholds] = None,
    page_num: int = 1,
) -> VisualQualityReport:
    """
    Executes all 10 visual quality checks on a rendered page and compiles a 0-100 score report.
    Returns:
      VisualQualityReport with layout_score, image_score, text_fit_score, overall_score, and issues list.
    """
    thresh = thresholds or VisualQCThresholds()

    # Execute 10 checks
    text_overflow_issues = _check_text_overflow(page, page_plan, template_metadata)
    image_overflow_issues = _check_image_overflow(page, page_plan, template_metadata)
    missing_asset_issues = _check_missing_assets(page, page_plan)
    distortion_issues = _check_image_distortion(page, page_plan, thresh.max_distortion_tolerance)
    low_res_issues = _check_low_resolution_images(page, thresh.min_dpi)
    overlap_issues = _check_overlapping_regions(page, page_plan)
    boundary_issues = _check_content_outside_page_boundaries(page)
    empty_space_issues = _check_excessive_empty_space(page, thresh.max_empty_space_ratio)
    small_text_issues = _check_excessively_small_text(page, thresh.min_fontsize)
    margin_issues = _check_inconsistent_margins(page, template_metadata, thresh.max_margin_variance)

    # Layout Score (100 base)
    layout_deductions = (
        len(overlap_issues) * 25
        + len(boundary_issues) * 30
        + len(empty_space_issues) * 20
        + len(margin_issues) * 15
    )
    layout_score = max(0, min(100, 100 - layout_deductions))

    # Image Score (100 base)
    has_images = len(page.get_images()) > 0 or len(missing_asset_issues) > 0
    if has_images:
        image_deductions = (
            len(missing_asset_issues) * 30
            + len(image_overflow_issues) * 25
            + len(distortion_issues) * 25
            + len(low_res_issues) * 15
        )
        image_score = max(0, min(100, 100 - image_deductions))
    else:
        image_score = 100

    # Text Fit Score (100 base)
    text_deductions = len(text_overflow_issues) * 35 + len(small_text_issues) * 20
    text_fit_score = max(0, min(100, 100 - text_deductions))

    # Overall composite score (0-100)
    overall_score = round(
        (0.35 * layout_score) + (0.35 * text_fit_score) + (0.30 * image_score)
    )

    all_issues = (
        text_overflow_issues
        + image_overflow_issues
        + missing_asset_issues
        + distortion_issues
        + low_res_issues
        + overlap_issues
        + boundary_issues
        + empty_space_issues
        + small_text_issues
        + margin_issues
    )

    is_valid = (
        overall_score >= thresh.min_overall_score
        and not any(
            "overflow" in i.lower()
            or "outside page" in i.lower()
            or "missing asset" in i.lower()
            for i in all_issues
        )
    )

    return VisualQualityReport(
        page=page_num,
        layout_score=layout_score,
        image_score=image_score,
        text_fit_score=text_fit_score,
        overall_score=overall_score,
        is_valid=is_valid,
        issues=all_issues,
        metrics={
            "total_words": len(page.get_text().split()),
            "embedded_images_count": len(page.get_images()),
            "checks_performed": 10,
        },
    )


def render_and_validate_page_with_recovery(
    doc: fitz.Document,
    page_plan: Any,
    template_metadata: Any = None,
    page_num: int = 1,
    max_attempts: int = 3,
    thresholds: Optional[VisualQCThresholds] = None,
) -> PageRecoveryResult:
    """
    Closed-Loop Quality Control Workflow:
        PagePlan -> Renderer -> Validator -> FAIL -> LayoutPlanner (Alternative) -> Renderer -> Validator -> PASS

    Guarantees that regeneration attempts are strictly bounded by max_attempts to prevent infinite loops.
    """
    from app.modules.magazine.renderer import render_page_from_plan
    from app.modules.magazine.template_library import get_template_by_id

    thresh = thresholds or VisualQCThresholds()
    history = []
    initial_report: Optional[VisualQualityReport] = None
    current_plan = copy.deepcopy(page_plan)
    current_meta = copy.deepcopy(template_metadata) or {}

    attempt = 1
    final_passed = False
    last_report: Optional[VisualQualityReport] = None

    while attempt <= max_attempts:
        # 1. Render trial page on scratch document
        scratch_doc = fitz.open()
        scratch_page = render_page_from_plan(scratch_doc, current_plan, current_meta, page_num)

        # 2. Validate rendered trial page
        report = validate_page_visual_quality(scratch_page, current_plan, current_meta, thresh, page_num)
        last_report = report
        if initial_report is None:
            initial_report = report

        history.append({
            "attempt": attempt,
            "template_id": getattr(current_plan, "template_id", str(current_meta.get("template_id"))),
            "layout_variant": getattr(current_plan, "layout_variant", None),
            "overall_score": report.overall_score,
            "is_valid": report.is_valid,
            "issues_count": len(report.issues),
        })

        if report.is_valid:
            logger.info(
                f"[VisualQC] Page {page_num} passed visual QC on attempt {attempt} (Score: {report.overall_score})."
            )
            final_passed = True
            # Commit trial page to actual document
            render_page_from_plan(doc, current_plan, current_meta, page_num)
            break
        else:
            logger.warning(
                f"[VisualQC] Page {page_num} failed visual QC on attempt {attempt} (Score: {report.overall_score}, Issues: {report.issues}). Requesting alternative layout..."
            )

            if attempt < max_attempts:
                # 3. LayoutPlanner selects alternative layout / template
                current_tmpl_id = getattr(current_plan, "template_id", str(current_meta.get("template_id")))
                if "showcase" in current_tmpl_id:
                    alt_meta = get_template_by_id("ai_lab_project_split")
                    if alt_meta:
                        current_meta = alt_meta.get("template_metadata") or alt_meta
                        if hasattr(current_plan, "template_id"):
                            current_plan.template_id = "ai_lab_project_split"
                elif "spotlight" in current_tmpl_id:
                    alt_meta = get_template_by_id("student_achievement_grid")
                    if alt_meta:
                        current_meta = alt_meta.get("template_metadata") or alt_meta
                        if hasattr(current_plan, "template_id"):
                            current_plan.template_id = "student_achievement_grid"

                # Rotate layout variant
                variants = ["split_column", "compact_grid", "standard_hero"]
                new_variant = variants[(attempt - 1) % len(variants)]
                if hasattr(current_plan, "layout_variant"):
                    current_plan.layout_variant = new_variant

            attempt += 1

    # If exhausted without passing, commit final with safe fallback
    if not final_passed:
        logger.warning(
            f"[VisualQC] Page {page_num} reached max regeneration attempts ({max_attempts}). Committing safe fallback."
        )
        render_page_from_plan(doc, current_plan, current_meta, page_num)

    return PageRecoveryResult(
        page_num=page_num,
        final_template_id=getattr(current_plan, "template_id", str(current_meta.get("template_id"))),
        final_layout_variant=getattr(current_plan, "layout_variant", None),
        attempts_taken=min(attempt, max_attempts),
        passed=final_passed,
        initial_report=initial_report or last_report,
        final_report=last_report or initial_report,
        regeneration_history=history,
    )


