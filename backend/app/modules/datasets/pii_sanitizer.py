"""Privacy and PII Sanitizer for Magazine Training Datasets (Phase 8).

Detects and redacts sensitive student and personal data (phone numbers, personal emails,
registration numbers, confidential tokens) while strictly preserving legitimate institutional
entities, department/lab designations, competition titles, and public event information.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Union


# Legitimate public contact addresses that do not require redaction
SAFE_INSTITUTIONAL_EMAILS = {
    "info@siet.ac.in",
    "admissions@siet.ac.in",
    "magazine@siet.ac.in",
    "principal@siet.ac.in",
    "research@siet.ac.in",
}

# Regex patterns for identifying personal and sensitive data
PHONE_PATTERN = re.compile(
    r"(?:\+91[\s\-]?)?(?:\(?0\d{2,4}\)?[\s\-]?)?[6-9]\d{4}[\s\-]?\d{5}\b|"
    r"\b(?:\+1[\s\-]?)?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}\b|"
    r"\b\d{5}[\s\-]\d{5}\b"
)

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

# University registration / roll numbers: e.g. 714021104001, 21CS045, 714020106012
STUDENT_REG_PATTERN = re.compile(
    r"\b(?:reg(?:istration)?\.?\s*(?:no|num|number)?\.?\s*[:=]?\s*|roll\s*(?:no|num|number)?\.?\s*[:=]?\s*)?[78]\d{11}\b|"
    r"\b(?:reg(?:istration)?\.?\s*(?:no|num|number)?\.?\s*[:=]?\s*|roll\s*(?:no|num|number)?\.?\s*[:=]?\s*)\d{2}[A-Za-z]{2,4}\d{3,4}\b",
    re.IGNORECASE,
)

# Confidential credentials or API keys
SECRET_TOKEN_PATTERN = re.compile(
    r"\b(?:sk\-[A-Za-z0-9]{20,}|AIzaSy[A-Za-z0-9_\-]{33}|ghp_[A-Za-z0-9]{36}|bearer\s+[A-Za-z0-9\-_.]{20,})\b",
    re.IGNORECASE,
)

# National ID patterns (Aadhaar 12-digit)
AADHAAR_PATTERN = re.compile(
    r"\b[2-9]\d{3}[\s\-]\d{4}[\s\-]\d{4}\b"
)


def sanitize_text(text: str) -> str:
    """
    Sanitizes raw text by redacting sensitive student, personal, and secret information.
    Preserves college name, labs, departments, and public academic context.
    """
    if not text:
        return ""

    sanitized = text

    # 1. Redact API keys / Secret tokens first
    sanitized = SECRET_TOKEN_PATTERN.sub("[SECRET_TOKEN_REDACTED]", sanitized)

    # 2. Redact Aadhaar / National ID
    sanitized = AADHAAR_PATTERN.sub("[GOVT_ID_REDACTED]", sanitized)

    # 3. Redact Emails (preserving official institutional addresses)
    def _replace_email(match: re.Match) -> str:
        email = match.group(0).lower()
        if email in SAFE_INSTITUTIONAL_EMAILS:
            return match.group(0)
        return "[EMAIL_REDACTED]"

    sanitized = EMAIL_PATTERN.sub(_replace_email, sanitized)

    # 4. Redact Student Registration / Roll Numbers
    sanitized = STUDENT_REG_PATTERN.sub("[STUDENT_ID_REDACTED]", sanitized)

    # 5. Redact Phone Numbers
    sanitized = PHONE_PATTERN.sub("[PHONE_REDACTED]", sanitized)

    return sanitized


def detect_pii_issues(text: str) -> List[str]:
    """
    Audits text to identify any remaining unredacted sensitive PII patterns.
    Returns a list of issue descriptions.
    """
    if not text:
        return []

    issues: List[str] = []

    if SECRET_TOKEN_PATTERN.search(text):
        issues.append("Unredacted API key or secret token detected.")

    if AADHAAR_PATTERN.search(text):
        issues.append("Unredacted Government/Aadhaar ID detected.")

    for match in EMAIL_PATTERN.finditer(text):
        email = match.group(0).lower()
        if email not in SAFE_INSTITUTIONAL_EMAILS:
            issues.append(f"Unredacted personal email detected: {email}")

    if STUDENT_REG_PATTERN.search(text):
        issues.append("Unredacted Student Registration/Roll number detected.")

    for match in PHONE_PATTERN.finditer(text):
        num = match.group(0)
        # Avoid false positives on 4-digit years like 2024, 2026 or small quantities
        if len(re.sub(r"\D", "", num)) >= 10:
            issues.append(f"Unredacted phone number detected: {num}")

    return issues


def sanitize_data_structure(data: Union[Dict[str, Any], List[Any], str, Any]) -> Any:
    """Recursively traverses nested dictionaries/lists to sanitize all string fields."""
    if isinstance(data, str):
        return sanitize_text(data)
    elif isinstance(data, dict):
        return {k: sanitize_data_structure(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_data_structure(item) for item in data]
    return data
