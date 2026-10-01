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


def _extract_dates(text: str) -> set[str]:
    """Extracts date strings and normalized month-day-year tuples from text."""
    date_patterns = [
        r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b",
        r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b",
        r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b",
        r"\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b",
    ]
    dates = set()
    for pat in date_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            raw = m.group(0).strip()
            # Clean ordinals
            cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", raw, flags=re.IGNORECASE)
            dates.add(cleaned.lower())
    return dates


def verify_magazine_content_against_sources(
    structured_content: Dict[str, Any],
    source_text: str,
    source_chunks: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Comprehensive Factual Verification of generated magazine content against source passages.
    Checks:
    - Date fidelity (e.g. source 15 August 2026 vs generated 20 August 2026)
    - Award & achievement grounding (never invents awards when absent from source)
    - Numeric consistency (participant counts, funding, prize amounts)
    - Named entities (recipients, speakers, departments)
    - Provenance source page tracking

    Returns validation dict with status ('PASS' | 'REVIEW_REQUIRED'), confidence, source pages, and issues.
    """
    unsupported_claims: List[str] = []
    issues: List[str] = []
    source_pages: Set[int] = set()

    norm_source = _normalize(source_text)
    source_numbers = _extract_numbers(source_text)
    source_nouns = _extract_proper_nouns(source_text)
    source_dates = _extract_dates(source_text)

    # Collect source pages from chunks
    if source_chunks:
        for sc in source_chunks:
            p = sc.get("page_number")
            if p:
                source_pages.add(int(p))
    if not source_pages:
        source_pages.add(1)

    # 1. Date Verification across generated events, writeup, and metadata
    content_dates: Set[str] = set()
    writeup = str(structured_content.get("writeup_text", "") or structured_content.get("writeup", ""))
    content_dates.update(_extract_dates(writeup))

    for ev in structured_content.get("events", []):
        if isinstance(ev, dict):
            ev_date = str(ev.get("date", "")).strip()
            if ev_date:
                content_dates.update(_extract_dates(ev_date) or {ev_date.lower()})

    for d in content_dates:
        # Check if date appears in source
        if d not in source_dates and not any(d in sd or sd in d for sd in source_dates):
            # Also check if numeric day/year appear in source numbers
            day_matches = [n for n in _extract_numbers(d) if len(n) <= 2 and int(n) <= 31]
            if day_matches and not all(dm in source_numbers for dm in day_matches):
                msg = f"Date mismatch: generated date '{d}' is not grounded in source document."
                unsupported_claims.append(msg)
                issues.append(msg)

    # 2. Award / Achievement Grounding Check
    # Verify that awards are not fabricated when source lacks award information
    award_keywords = ["award", "prize", "winner", "place", "won", "honor", "medal", "trophy", "cash prize", "fellowship", "grant"]
    source_has_awards = any(k in norm_source for k in award_keywords)

    achievements = structured_content.get("achievements", [])
    if achievements:
        if not source_has_awards:
            msg = "Unsupported awards: generated magazine contains achievements/awards, but source document contains zero award information."
            unsupported_claims.append(msg)
            issues.append(msg)
        else:
            for ach in achievements:
                if isinstance(ach, dict):
                    ach_title = str(ach.get("title", ""))
                    ach_desc = str(ach.get("description", ""))
                    ach_text = f"{ach_title} {ach_desc}"
                    # Check recipient if present
                    recip = str(ach.get("recipient", "")).strip()
                    if recip and recip.lower() not in norm_source:
                        issues.append(f"Achievement recipient '{recip}' not found in source text.")

    # 3. Numeric Integrity Check (participant counts, metrics)
    content_numbers = _extract_numbers(writeup)
    suspicious_numbers = [
        n for n in content_numbers
        if n not in source_numbers and int(float(n)) not in (1, 2, 3, 4, 5, 2026, 2027)
    ]
    if len(suspicious_numbers) > 3:
        msg = f"Generated writeup introduces unsupported numerical claims: {suspicious_numbers[:4]}."
        unsupported_claims.append(msg)
        issues.append(msg)

    # 4. Project Grounding Check
    for proj in structured_content.get("projects", []):
        if isinstance(proj, dict):
            p_title = str(proj.get("title", "")).strip()
            # If project title has distinct words, check if they exist in source
            p_words = [w.lower() for w in re.findall(r"\b[A-Za-z0-9]+\b", p_title) if len(w) > 3]
            if p_words:
                overlap = sum(1 for w in p_words if w in norm_source)
                if overlap == 0:
                    msg = f"Project '{p_title}' terms not found in source text."
                    issues.append(msg)

    # 5. Determine Final Status and Confidence
    if unsupported_claims:
        status = "REVIEW_REQUIRED"
        confidence = max(0.40, round(1.0 - (len(unsupported_claims) * 0.25) - (len(issues) * 0.05), 2))
    elif issues:
        status = "PASS" if len(issues) <= 1 else "REVIEW_REQUIRED"
        confidence = max(0.65, round(0.95 - (len(issues) * 0.08), 2))
    else:
        status = "PASS"
        confidence = 0.96

    return {
        "status": status,
        "confidence": confidence,
        "source_pages": sorted(list(source_pages)),
        "unsupported_claims": unsupported_claims,
        "issues": issues,
    }

