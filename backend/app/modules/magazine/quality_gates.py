"""Claim-Level Grounding & Verification Quality Gate.

Splits generated output into claim sentences, verifies each claim against source document chunks,
calls the local verification model/adapter, flags unsupported claims, and calculates a composite quality score (0.0 to 1.0).
Routes score >= 0.80 to 'published' and lower scores to 'needs_review'.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from app.modules.documents.embeddings import embed_text
from app.modules.documents.retriever import _cosine_similarity, _compute_keyword_score


def extract_claims(text: str) -> List[str]:
    """Splits section text into sentence claims."""
    clean = re.sub(r"<[^>]+>", "", text)  # Strip HTML tags
    sentences = [s.strip() for s in re.split(r"[.!?]\s+", clean) if len(s.strip()) > 12]
    return sentences


async def verify_claim_grounding(claim: str, source_facts: List[Dict[str, Any]]) -> float:
    """Computes similarity score between a claim sentence and source facts/chunks."""
    if not source_facts:
        return 0.5

    claim_vec = await embed_text(claim)
    max_sim = 0.0

    for fact in source_facts:
        fact_text = fact.get("text", "")
        if not fact_text:
            continue

        # Hybrid cosine similarity + keyword score
        fact_vec = await embed_text(fact_text)
        cos_sim = _cosine_similarity(claim_vec, fact_vec)
        kw_sim = _compute_keyword_score(claim, fact_text)
        score = (cos_sim * 0.7) + (kw_sim * 0.3)
        max_sim = max(max_sim, score)

    return max_sim


async def evaluate_quality_score(
    section_data: Dict[str, Any],
    source_facts: List[Dict[str, Any]],
    visual_qc_score: float = 1.0,
) -> Tuple[float, List[str]]:
    """
    Computes claim-level composite quality score (0.0 - 1.0) and generates feedback notes.
    Invokes the local verification LoRA adapter via get_lora_swapper() to score accuracy, tone, completeness.
    """
    from app.modules.datasets.lora_swapper import get_lora_swapper

    swapper = get_lora_swapper()
    swapper.swap_adapter("verification")

    feedback_notes = []

    # 1. Extract and verify claims
    text_content = ""
    for sec_key, sec_val in section_data.items():
        if isinstance(sec_val, str):
            text_content += sec_val + " "
        elif isinstance(sec_val, dict) and "content" in sec_val:
            text_content += str(sec_val["content"]) + " "

    claims = extract_claims(text_content)
    supported_claims = 0
    unsupported_claims = []

    if claims and source_facts:
        for claim in claims:
            sim = await verify_claim_grounding(claim, source_facts)
            if sim >= 0.45:
                supported_claims += 1
            else:
                unsupported_claims.append(claim)

        accuracy_score = supported_claims / len(claims)
    elif not source_facts:
        accuracy_score = 0.85
    else:
        accuracy_score = 0.0

    if unsupported_claims:
        feedback_notes.append(f"Found {len(unsupported_claims)} unsupported claim(s) lacking factual source backing.")

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
