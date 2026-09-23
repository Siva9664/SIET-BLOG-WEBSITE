"""Cloud-assisted candidate generation with deterministic validation and review."""

from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import httpx


DATASET_SCHEMA_VERSION = "fact-extraction-v1"


class CandidateGenerationError(RuntimeError):
    """Raised when the one-off candidate generation call cannot be completed."""


def _normalise_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _json_object_from_response(response_text: str) -> dict[str, Any]:
    clean = response_text.strip()
    clean = re.sub(r"^\x60\x60\x60(?:json)?\s*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*\x60\x60\x60$", "", clean)
    try:
        value = json.loads(clean)
    except json.JSONDecodeError as error:
        raise CandidateGenerationError("Gemini did not return valid JSON.") from error
    if isinstance(value, list):
        value = {"facts": value}
    if not isinstance(value, dict):
        raise CandidateGenerationError("Gemini response must be a JSON object or array.")
    return value


def build_fact_extraction_prompt(source_text: str) -> str:
    """Returns the stable task prompt used in both generation and training data."""
    return f"""Extract only atomic, source-grounded facts from the passage below.

Rules:
- Do not infer, combine unrelated statements, or add outside knowledge.
- Every fact must include an evidence string copied exactly from the passage.
- A fact must be independently checkable and concise.
- Return an empty facts list when the passage has no concrete claims.

Return only JSON matching this shape:
{{
  "facts": [
    {{
      "subject": "entity",
      "predicate": "relationship or action",
      "object": "value, entity, or outcome",
      "qualifiers": {{}},
      "fact_type": "event|person|organization|date|quantity|location|other",
      "evidence": "exact source sentence or clause"
    }}
  ]
}}

Source passage:
{source_text.strip()}"""


def _validate_fact(fact: Any, source_text: str) -> dict[str, Any] | None:
    if not isinstance(fact, dict):
        return None
    subject = str(fact.get("subject", "")).strip()
    predicate = str(fact.get("predicate", "")).strip()
    object_value = str(fact.get("object", "")).strip()
    evidence = str(fact.get("evidence", "")).strip()
    fact_type = str(fact.get("fact_type", "other")).strip().lower() or "other"
    qualifiers = fact.get("qualifiers", {})
    if not isinstance(qualifiers, dict):
        qualifiers = {}

    if not all([subject, predicate, object_value, evidence]):
        return None
    if _normalise_text(evidence) not in _normalise_text(source_text):
        return None

    return {
        "id": hashlib.sha256(
            f"{subject}|{predicate}|{object_value}|{evidence}".encode("utf-8")
        ).hexdigest()[:16],
        "subject": subject,
        "predicate": predicate,
        "object": object_value,
        "qualifiers": qualifiers,
        "fact_type": fact_type,
        "evidence": evidence,
    }


def parse_candidate_facts(response_text: str, source_text: str) -> list[dict[str, Any]]:
    """Strictly validates model candidates against their original source passage."""
    value = _json_object_from_response(response_text)
    raw_facts = value.get("facts", [])
    if not isinstance(raw_facts, list):
        raise CandidateGenerationError("Gemini response field 'facts' must be a list.")

    seen_ids: set[str] = set()
    facts: list[dict[str, Any]] = []
    for raw_fact in raw_facts:
        fact = _validate_fact(raw_fact, source_text)
        if fact and fact["id"] not in seen_ids:
            facts.append(fact)
            seen_ids.add(fact["id"])
    return facts


async def generate_candidate_facts(
    source_text: str,
    *,
    api_key: str,
    model: str = "gemini-2.5-flash",
) -> list[dict[str, Any]]:
    """Makes exactly one Gemini request for a source chunk and validates its result."""
    if not api_key:
        raise CandidateGenerationError(
            "GEMINI_API_KEY or GOOGLE_API_KEY is required for candidate generation."
        )
    prompt = build_fact_extraction_prompt(source_text)
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as error:
        raise CandidateGenerationError(
            f"Gemini request failed before a response was received: {error}"
        ) from error

    if response.status_code != 200:
        raise CandidateGenerationError(
            f"Gemini request failed with HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    try:
        response_json = response.json()
        parts = response_json["candidates"][0]["content"]["parts"]
        response_text = "".join(
            str(part.get("text", "")) for part in parts if isinstance(part, dict)
        )
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise CandidateGenerationError(
            "Gemini returned no candidate text."
        ) from error

    return parse_candidate_facts(response_text, source_text)


def make_candidate_record(
    chunk: dict[str, Any],
    facts: list[dict[str, Any]],
    *,
    model: str,
) -> dict[str, Any]:
    """Wraps validated candidates with source provenance for review."""
    return {
        "schema_version": DATASET_SCHEMA_VERSION,
        "id": chunk["id"],
        "task": "fact_extraction",
        "source": {
            "text": chunk["text"],
            "provenance": chunk["provenance"],
        },
        "candidate_facts": facts,
        "generation": {
            "provider": "gemini",
            "model": model,
            "generated_at": datetime.now(UTC).isoformat(),
        },
    }


def select_review_examples(
    candidates: list[dict[str, Any]], fraction: float = 0.25
) -> list[dict[str, Any]]:
    """Deterministically selects a reproducible random-looking review sample."""
    if not 0 < fraction <= 1:
        raise ValueError("Review fraction must be greater than zero and at most one.")
    count = math.ceil(len(candidates) * fraction)
    selected = sorted(
        candidates,
        key=lambda record: hashlib.sha256(record["id"].encode("utf-8")).hexdigest(),
    )[:count]

    review_records: list[dict[str, Any]] = []
    for candidate in selected:
        review = deepcopy(candidate)
        review["review"] = {
            "status": "pending",
            "reviewer": None,
            "reviewed_at": None,
            "notes": "",
            "fact_decisions": [
                {
                    "fact_id": fact["id"],
                    "decision": "pending",
                    "corrected_fact": None,
                    "notes": "",
                }
                for fact in candidate["candidate_facts"]
            ],
        }
        review_records.append(review)
    return review_records


def _approved_facts(
    candidate: dict[str, Any], review: dict[str, Any] | None
) -> tuple[list[dict[str, Any]], str]:
    if not review:
        return deepcopy(candidate["candidate_facts"]), "not_sampled"

    review_data = review.get("review", {})
    if review_data.get("status") != "completed":
        raise ValueError(f"Review for {candidate['id']} is not completed.")

    by_fact_id = {
        decision.get("fact_id"): decision
        for decision in review_data.get("fact_decisions", [])
    }
    approved: list[dict[str, Any]] = []
    for fact in candidate["candidate_facts"]:
        decision = by_fact_id.get(fact["id"], {})
        status = decision.get("decision")
        if status == "accept":
            approved.append(deepcopy(fact))
        elif status == "edit":
            corrected = _validate_fact(
                decision.get("corrected_fact"),
                candidate["source"]["text"],
            )
            if not corrected:
                raise ValueError(
                    f"Edited fact {fact['id']} in {candidate['id']} is invalid."
                )
            approved.append(corrected)
        elif status != "reject":
            raise ValueError(
                f"Fact {fact['id']} in {candidate['id']} has no review decision."
            )
    return approved, "spot_checked"


def build_training_example(
    candidate: dict[str, Any], review: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Converts a validated candidate record into portable chat-format JSONL."""
    approved_facts, review_status = _approved_facts(candidate, review)
    source_text = candidate["source"]["text"]
    return {
        "schema_version": DATASET_SCHEMA_VERSION,
        "id": candidate["id"],
        "task": "fact_extraction",
        "messages": [
            {"role": "user", "content": build_fact_extraction_prompt(source_text)},
            {
                "role": "assistant",
                "content": json.dumps({"facts": approved_facts}, ensure_ascii=False),
            },
        ],
        "metadata": {
            "provenance": candidate["source"]["provenance"],
            "review_status": review_status,
            "candidate_model": candidate["generation"]["model"],
        },
    }


def finalize_examples(
    candidates: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    *,
    minimum_review_fraction: float = 0.25,
) -> list[dict[str, Any]]:
    """Builds final examples only after the requested human spot-check threshold."""
    if not candidates:
        return []
    reviews_by_id = {record["id"]: record for record in reviews}
    completed_count = sum(
        1
        for record in reviews
        if record.get("review", {}).get("status") == "completed"
    )
    required_count = math.ceil(len(candidates) * minimum_review_fraction)
    if completed_count < required_count:
        raise ValueError(
            f"Need {required_count} completed reviews for {len(candidates)} candidates; "
            f"found {completed_count}."
        )
    return [
        build_training_example(candidate, reviews_by_id.get(candidate["id"]))
        for candidate in candidates
    ]
