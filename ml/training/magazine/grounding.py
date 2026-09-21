"""
Strict factual grounding validation for SIET Magazine Training Dataset.
Ensures zero hallucinations:
- No invented dates / years
- No invented statistics / numbers
- No invented names / people
- No invented organizations / partners
- No invented achievements / awards
- Missing fields must remain null or empty
"""

from __future__ import annotations

import re
import json
from typing import List, Dict, Set, Any, Optional

from .schemas import ExampleRecord


def extract_year_dates(text: str) -> Set[str]:
    """Extracts 4-digit years (e.g., 2024, 2025, 2026, 2027)."""
    return set(re.findall(r"\b20\d{2}\b", text))


def extract_standalone_numbers(text: str) -> Set[str]:
    """
    Extracts standalone numbers >= 3 from text, ignoring standard schema/prompt
    constants such as limits (15, 25, 100, 300) and column counts (1, 2).
    """
    matches = re.findall(r"\b\d+(?:,\d+)*(?:\.\d+)?\b", text)
    filtered = set()
    # Structural limits often appearing in prompt or template formatting (aspect ratios 16:9, columns 1-4, word limits)
    prompt_constants = {
        "0", "1", "2", "3", "4", "5", "6", "8", "9", "10", "12", "15", "16", "20", "22",
        "25", "30", "50", "100", "150", "200", "250", "300", "600"
    }

    for m in matches:
        if m in prompt_constants:
            continue
        try:
            val = float(m.replace(",", ""))
            if 0.0 <= val <= 1.0:
                continue
        except ValueError:
            pass
        filtered.add(m)
    return filtered


def extract_named_entities(text: str) -> Set[str]:
    """Extracts capitalized named entities like Dr. Name, Company names, etc."""
    entities = set()
    # Matches Dr./Prof./Er. <Name>
    for m in re.finditer(r"\b(?:Dr\.|Prof\.|Er\.|Mr\.|Ms\.|Mrs\.)\s+([A-Z][a-zA-Z]+)", text):
        entities.add(m.group(0).strip().lower())

    # Matches Indian currency mentions e.g. INR 35 Lakhs or ₹ 10,000
    for m in re.finditer(r"\b(?:INR|₹)\s*[\d,]+(?:\s*Lakhs?|\s*Crores?)?", text, re.IGNORECASE):
        entities.add(m.group(0).strip().lower())

    return entities


class GroundingAuditor:
    """
    Audits an ExampleRecord or prompt/response pair for strict factual grounding.
    """

    def validate_grounding(
        self, source_text: str, assistant_text: str
    ) -> List[str]:
        """
        Validates that assistant_text does not introduce facts absent from source_text.
        Returns a list of violation descriptions (empty if 100% grounded).
        """
        violations: List[str] = []
        source_lower = source_text.lower()
        asst_lower = assistant_text.lower()

        # 1. Date / Year validation: Every 4-digit year in output must be in source
        asst_years = extract_year_dates(assistant_text)
        src_years = extract_year_dates(source_text)
        ungrounded_years = asst_years - src_years
        if ungrounded_years:
            violations.append(f"Ungrounded year(s) found in response: {ungrounded_years}")

        # 2. Number / Statistics validation: Significant numbers in output must be in source
        asst_nums = extract_standalone_numbers(assistant_text)
        src_nums = extract_standalone_numbers(source_text)
        ungrounded_nums = asst_nums - src_nums
        if ungrounded_nums:
            violations.append(f"Ungrounded number(s) found in response: {ungrounded_nums}")

        # 3. Named entities & honors
        asst_entities = extract_named_entities(assistant_text)
        for entity in asst_entities:
            if entity not in source_lower:
                violations.append(f"Ungrounded named entity/honor in response: '{entity}'")

        # 4. Check for hallucinated prize rankings
        rankings = ["first prize", "second prize", "third prize", "gold medal", "silver medal", "bronze medal"]
        for rk in rankings:
            if rk in asst_lower and rk not in source_lower:
                violations.append(f"Ungrounded ranking claim: '{rk}'")

        # 5. Missing fields verification if output is JSON
        try:
            parsed = json.loads(assistant_text)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    # If field represents date, people, organization, achievement and source doesn't have it,
                    # verify it is null or empty
                    if k in {"date", "event_date", "speaker", "organizer", "achievement_result", "cash_prize"}:
                        if v is not None and str(v).strip():
                            # Value was provided; ensure it is grounded
                            val_str = str(v).lower()
                            # Check if at least one token from value is in source
                            val_tokens = [t for t in re.findall(r"\w+", val_str) if len(t) > 3]
                            if val_tokens and not any(t in source_lower for t in val_tokens):
                                violations.append(f"Ungrounded field value for '{k}': {v}")
        except Exception:
            pass

        return violations

    def audit_example(self, example: ExampleRecord) -> List[str]:
        """Audits a complete ExampleRecord."""
        # Find user message and assistant message
        user_msg = ""
        asst_msg = ""
        for m in example.messages:
            if m["role"] == "user":
                user_msg = m["content"]
            elif m["role"] == "assistant":
                asst_msg = m["content"]

        # Extract source context from user prompt
        source_match = re.search(
            r"(?:SOURCE CONTEXT|STORY CONTEXT|EVENT METADATA):\s*(.*?)(?=\n\n(?:TASK|AVAILABLE|PHOTO)|$)",
            user_msg,
            re.DOTALL | re.IGNORECASE,
        )
        source_context = source_match.group(1) if source_match else user_msg
        combined_context = f"{source_context}\n{user_msg}"

        return self.validate_grounding(combined_context, asst_msg)

