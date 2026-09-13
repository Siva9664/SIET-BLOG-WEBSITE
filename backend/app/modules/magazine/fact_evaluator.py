"""Fact Evaluator and Grounding Monitor for Magazine Pipeline.

Evaluates extracted candidate facts against source document passages.
Catches hallucinations, altered dates, modified entities, and distorted numbers.
Acts as a strict gating filter before generation.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class EvaluationResult:
    verdict: str  # "VALID" | "CORRUPTED" | "UNSUPPORTED"
    is_grounded: bool
    confidence: float
    issues: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _normalize(text: str) -> str:
    """Standardizes whitespace and lowercases for fuzzy token presence checks."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _extract_numbers(text: str) -> set[str]:
    """Extracts numeric values including currency and comma notation."""
    # Find patterns like 75,000, 350, 4-bit, 2026, 1st, ₹75000
    cleaned = re.sub(r"[₹$,]", "", text)
    nums = set(re.findall(r"\b\d+(?:\.\d+)?\b", cleaned))
    # Also extract ordinal numbers (1st, 2nd, 3rd)
    ordinals = set(re.findall(r"\b\d+(?:st|nd|rd|th)\b", text.lower()))
    return nums | ordinals


def _extract_proper_nouns(text: str) -> set[str]:
    """Extracts capitalized named entity candidates from un-lowercased text."""
    # Matches words starting with Capital letter that are not standard stop words
    words = re.findall(r"\b[A-Z][a-zA-Z0-9_\-\.]+\b", text)
    common = {"The", "A", "An", "In", "On", "At", "By", "For", "With", "About", "Against", "Between", "Into", "Through", "During", "Before", "After", "Above", "Below", "To", "From", "Up", "Down"}
    return {w for w in words if w not in common and len(w) > 1}


def build_evaluator_prompt(source_passage: str, fact: Dict[str, Any]) -> str:
    """Builds prompt for model-based fact evaluation."""
    return f"""You are an expert fact verification judge.
Compare the atomic fact below with the source passage.

=== SOURCE PASSAGE ===
{source_passage.strip()}

=== FACT TO EVALUATE ===
Subject:   {fact.get('subject', '')}
Predicate: {fact.get('predicate', '')}
Object:    {fact.get('object', '')}
Evidence:  {fact.get('evidence', '')}

Evaluation Rules:
1. Every name, number, date, and claim must match the source passage exactly.
2. If any number, date, name, or role is altered or invented, verdict is CORRUPTED.
3. If the evidence quote is not found in the source passage, verdict is UNSUPPORTED.
4. If the fact is completely accurate and grounded, verdict is VALID.

Return ONLY JSON:
{{
  "verdict": "VALID" | "CORRUPTED" | "UNSUPPORTED",
  "is_grounded": true | false,
  "confidence": 0.0 to 1.0,
  "issues": ["list of specific discrepancies if any"]
}}"""


def evaluate_fact_grounding(
    source_passage: str,
    fact: Dict[str, Any],
) -> EvaluationResult:
    """
    High-precision prompt-and-rule evaluator monitor.
    Enforces strict evidence presence, entity conservation, and numeric consistency.
    """
    issues: List[str] = []
    norm_source = _normalize(source_passage)

    evidence = str(fact.get("evidence", "")).strip()
    subject = str(fact.get("subject", "")).strip()
    predicate = str(fact.get("predicate", "")).strip()
    object_val = str(fact.get("object", "")).strip()

    # Gate 1: Evidence must be provided
    if not evidence:
        return EvaluationResult(
            verdict="UNSUPPORTED",
            is_grounded=False,
            confidence=1.0,
            issues=["Missing evidence citation."],
        )

    norm_evidence = _normalize(evidence)

    # Gate 2: Evidence must appear verbatim (or normalized) in the source text
    if norm_evidence not in norm_source:
        # Check if high overlap exists (at least 90% character substring)
        # If evidence was fabricated or altered, mark as CORRUPTED / UNSUPPORTED
        issues.append(f"Evidence '{evidence}' is not found verbatim in source passage.")

    # Gate 3: Numeric consistency check (Critical for dates, award amounts, counts)
    fact_combined_text = f"{subject} {predicate} {object_val} {evidence}"
    fact_numbers = _extract_numbers(fact_combined_text)
    source_numbers = _extract_numbers(source_passage)

    unsupported_numbers = fact_numbers - source_numbers
    if unsupported_numbers:
        issues.append(f"Fact contains altered/unsupported numeric values: {sorted(list(unsupported_numbers))}")

    # Gate 4: Named entity / Proper noun consistency check
    fact_nouns = _extract_proper_nouns(f"{subject} {object_val} {evidence}")
    source_nouns = _extract_proper_nouns(source_passage)

    unsupported_nouns = {
        n for n in fact_nouns
        if n not in source_nouns and not any(n.lower() in sn.lower() or sn.lower() in n.lower() for sn in source_nouns)
    }
    if unsupported_nouns:
        issues.append(f"Fact introduces altered/unsupported named entities: {sorted(list(unsupported_nouns))}")

    # Gate 5: Subject/Object must have substantive overlap with evidence/passage
    norm_claim = _normalize(f"{subject} {object_val}")
    claim_words = [w for w in norm_claim.split() if len(w) > 3]
    if claim_words:
        matched_words = sum(1 for w in claim_words if w in norm_source)
        coverage = matched_words / len(claim_words)
        if coverage < 0.40:
            issues.append(f"Low term alignment ({coverage:.0%}) between claim and source passage.")

    if not issues:
        return EvaluationResult(
            verdict="VALID",
            is_grounded=True,
            confidence=0.98,
            issues=[],
        )

    # Determine whether it is a deliberate corruption or completely unsupported
    is_corruption = any(
        "altered/unsupported numeric" in iss or "altered/unsupported named" in iss or "not found verbatim" in iss
        for iss in issues
    )
    verdict = "CORRUPTED" if is_corruption else "UNSUPPORTED"

    return EvaluationResult(
        verdict=verdict,
        is_grounded=False,
        confidence=0.95,
        issues=issues,
    )


def gate_extracted_facts(
    source_passage: str,
    candidate_facts: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Evaluator Gate Filter:
    Inspects candidate facts against the source passage.
    Returns (accepted_facts, dropped_or_flagged_facts).
    Facts failing evaluation are dropped/flagged, never silently passed through.
    """
    accepted: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []

    for fact in candidate_facts:
        eval_res = evaluate_fact_grounding(source_passage, fact)
        fact_with_eval = dict(fact)
        fact_with_eval["evaluation"] = eval_res.to_dict()

        if eval_res.is_grounded and eval_res.verdict == "VALID":
            accepted.append(fact_with_eval)
        else:
            dropped.append(fact_with_eval)

    return accepted, dropped
