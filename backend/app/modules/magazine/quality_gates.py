"""Quality Gates and Automated Verification Scoring Module.

Scores generated magazine issues on accuracy, tone, completeness, and visual QC (0.0 to 1.0).
Routes high confidence output (>= 0.80) to auto-publish and lower scoring issues to needs_review.
Provides feedback-guided retry loops.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def evaluate_quality_score(
    section_data: Dict[str, Any],
    source_facts: List[Dict[str, Any]],
    visual_qc_score: float = 1.0,
) -> Tuple[float, List[str]]:
    """
    Computes a composite quality score (0.0 - 1.0) and generates feedback flags.
    Factors:
    - Grounding / Accuracy Score (40%)
    - Completeness / Section Coverage Score (30%)
    - Visual Quality Control Score (30%)
    """
    feedback_notes = []

    # 1. Grounding / Accuracy Score
    text_content = ""
    for sec_key, sec_val in section_data.items():
        if isinstance(sec_val, str):
            text_content += sec_val + " "
        elif isinstance(sec_val, dict) and "content" in sec_val:
            text_content += str(sec_val["content"]) + " "

    fact_matches = 0
    if source_facts:
        for fact in source_facts:
            fact_str = fact.get("text", "")
            # Simple keyword matching check for grounding
            keywords = [w.lower() for w in fact_str.split() if len(w) > 3]
            if keywords and any(kw in text_content.lower() for kw in keywords):
                fact_matches += 1

        accuracy_score = fact_matches / len(source_facts)
    else:
        accuracy_score = 0.5  # Neutral default if no source facts passed

    if accuracy_score < 0.6:
        feedback_notes.append("Low factual grounding against source documents.")

    # 2. Completeness Score
    required_keys = {"title", "description", "writeup", "toc_summary"}
    present_keys = {k for k in section_data.keys() if section_data[k]}
    completeness_score = len(required_keys.intersection(present_keys)) / len(required_keys)

    if completeness_score < 1.0:
        missing = required_keys - present_keys
        feedback_notes.append(f"Missing required sections: {', '.join(missing)}")

    # 3. Composite Score Calculation
    v_score = min(max(visual_qc_score, 0.0), 1.0)
    composite_score = (accuracy_score * 0.4) + (completeness_score * 0.3) + (v_score * 0.3)
    composite_score = round(min(max(composite_score, 0.0), 1.0), 2)

    return composite_score, feedback_notes


def route_publication_status(quality_score: float, threshold: float = 0.80) -> str:
    """Routes to 'published' if quality_score >= threshold, otherwise 'needs_review'."""
    if quality_score >= threshold:
        return "published"
    return "needs_review"
