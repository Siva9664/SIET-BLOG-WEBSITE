import os
from typing import Any, Dict, List


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
        if os.path.exists(prev) and os.path.getsize(prev) > 0:
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
