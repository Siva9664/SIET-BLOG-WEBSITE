"""
Automated quality gate verification for SIET Magazine Training Dataset Builder.
Fails or warns when:
1. An example lacks source provenance (doc_id, page_start, story_id).
2. Grounding violations or unsupported factual claims are detected.
3. Photo misassociations or cross-document photo contaminations occur.
4. Train/validation cross-document leakage occurs.
5. Duplicate rate exceeds acceptable thresholds.
"""

from __future__ import annotations

from typing import List, Dict, Set, Any, Optional

from .schemas import ExampleRecord, QualityReport, StorySegment
from .grounding import GroundingAuditor


class QualityGateManager:
    """
    Evaluates dataset quality against strict training standards.
    """

    def __init__(
        self,
        max_duplicate_rate: float = 0.05,
        max_grounding_failures: int = 0,
        grounding_auditor: Optional[GroundingAuditor] = None,
    ):
        self.max_duplicate_rate = max_duplicate_rate
        self.max_grounding_failures = max_grounding_failures
        self.auditor = grounding_auditor or GroundingAuditor()

    def evaluate(
        self,
        examples: List[ExampleRecord],
        train_examples: List[ExampleRecord],
        val_examples: List[ExampleRecord],
        stories: List[StorySegment],
        duplicate_count: int,
    ) -> QualityReport:
        report = QualityReport()
        report.total_examples = len(examples)

        # 1. Provenance Check
        for ex in examples:
            meta = ex.metadata
            if not meta.get("doc_id") or not meta.get("story_id") or "page_start" not in meta:
                report.provenance_missing += 1
                report.errors.append(f"Missing provenance in example: {meta.get('story_id')}")

        # 2. Grounding Audit
        for ex in examples:
            violations = self.auditor.audit_example(ex)
            if violations:
                report.grounding_failed += 1
                task = ex.metadata.get("task_type", "unknown")
                report.errors.append(f"Grounding failure in [{task}]: {'; '.join(violations[:2])}")
            else:
                report.grounding_passed += 1

        # 3. Photo Misassociation Check
        # Ensure attached photos strictly originate from the same document ID
        for s in stories:
            for p_id in s.attached_photos:
                # Photo ID convention: {doc_id}_p{page}_img{idx}
                if not p_id.startswith(s.doc_id):
                    report.photo_misassociations += 1
                    report.errors.append(
                        f"Photo misassociation: photo '{p_id}' attached to story from different doc '{s.doc_id}'"
                    )

        # 4. Train / Validation Leakage Check
        train_docs = {ex.metadata.get("doc_id") for ex in train_examples if ex.metadata.get("doc_id")}
        val_docs = {ex.metadata.get("doc_id") for ex in val_examples if ex.metadata.get("doc_id")}

        if len(train_docs) > 1 and len(val_docs) > 1:
            leakage = train_docs.intersection(val_docs)
            if leakage:
                report.leakage_detected = True
                report.errors.append(f"Train/Validation document leakage detected: {leakage}")

        # 5. Duplicate Rate Check
        denom = len(examples) + duplicate_count
        report.duplicate_rate = (duplicate_count / denom) if denom > 0 else 0.0
        if report.duplicate_rate > self.max_duplicate_rate:
            report.warnings.append(
                f"Duplicate rate ({report.duplicate_rate:.1%}) exceeds threshold ({self.max_duplicate_rate:.1%})"
            )

        # Final decision
        has_fatal_errors = (
            report.provenance_missing > 0
            or report.grounding_failed > self.max_grounding_failures
            or report.photo_misassociations > 0
            or report.leakage_detected
        )
        report.passed_all_gates = not has_fatal_errors

        return report
