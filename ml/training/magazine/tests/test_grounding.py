"""
Unit tests for strict factual grounding validation.
Tests:
- Detection of ungrounded dates/years
- Detection of ungrounded statistics/numbers
- Detection of ungrounded people names and entities
- Detection of ungrounded ranking claims (e.g. First Prize when none mentioned)
- Ensuring missing information is represented as null without penalty
"""

import json
import unittest

from ml.training.magazine.grounding import (
    GroundingAuditor,
    extract_year_dates,
    extract_standalone_numbers,
    extract_named_entities,
)
from ml.training.magazine.schemas import ExampleRecord


class TestGroundingValidation(unittest.TestCase):
    """Test suite verifying zero hallucination and strict grounding enforcement."""

    def setUp(self):
        self.auditor = GroundingAuditor()

    def test_grounded_content_passes(self):
        source = (
            "Event: Hands-on Workshop on TinyML.\n"
            "Date: August 12, 2026.\n"
            "Organized by: Department of Electronics & Communication Engineering.\n"
            "Lead: Dr. V. Muralidharan.\n"
            "Participants: 85 students.\n"
            "Hardware: ESP32-S3 microcontroller."
        )
        assistant = json.dumps({
            "headline": "Hands-on Workshop on TinyML",
            "body": "85 students attended the workshop led by Dr. V. Muralidharan on August 12, 2026.",
            "date": "August 12, 2026",
            "people": ["Dr. V. Muralidharan"],
            "organization": "Department of Electronics & Communication Engineering",
            "achievement_result": None,
        })

        violations = self.auditor.validate_grounding(source, assistant)
        self.assertEqual(len(violations), 0, f"Expected 0 violations for grounded content, got: {violations}")

    def test_catches_ungrounded_year(self):
        source = "Dr. Ramesh inaugurated the computing center on March 10, 2025."
        assistant = json.dumps({
            "headline": "Dr. Ramesh in 2030",
            "body": "Center inaugurated in 2030."
        })
        violations = self.auditor.validate_grounding(source, assistant)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any("2030" in v for v in violations))

    def test_catches_ungrounded_statistics(self):
        source = "A team of students attended the seminar in Hall A."
        assistant = json.dumps({
            "headline": "Large Seminar",
            "body": "There were 9750 attendees present at the conference."
        })
        violations = self.auditor.validate_grounding(source, assistant)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any("9750" in v for v in violations))

    def test_catches_ungrounded_ranking_claim(self):
        source = "SIET students participated in the regional hackathon."
        assistant = json.dumps({
            "headline": "Hackathon Results",
            "body": "SIET students secured First Prize and Gold Medal at the hackathon."
        })
        violations = self.auditor.validate_grounding(source, assistant)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any("first prize" in v.lower() or "gold medal" in v.lower() for v in violations))

    def test_missing_fields_must_remain_null(self):
        source = "Students demonstrated their project in the lab."
        # Correct grounded behavior: missing fields are None
        valid_response = json.dumps({
            "headline": "Project Demonstration in Lab",
            "body": "Students presented their project inside the college lab.",
            "date": None,
            "speaker": None,
            "cash_prize": None,
        })
        violations = self.auditor.validate_grounding(source, valid_response)
        self.assertEqual(len(violations), 0)

        # Violation behavior: model fabricated a date or speaker
        hallucinated_response = json.dumps({
            "headline": "Project Demonstration in Lab",
            "body": "Students presented their project inside the college lab.",
            "date": "September 24, 2026",
            "speaker": "Dr. Albert Einstein",
            "cash_prize": "INR 1,00,000",
        })
        hallucination_violations = self.auditor.validate_grounding(source, hallucinated_response)
        self.assertGreater(len(hallucination_violations), 0)

    def test_audit_example_record(self):
        example = ExampleRecord(
            messages=[
                {"role": "system", "content": "System instruction."},
                {
                    "role": "user",
                    "content": "SOURCE CONTEXT:\nDr. Anand gave a talk on robotics on October 5, 2025.\n\nTASK:\nRewrite.",
                },
                {
                    "role": "assistant",
                    "content": json.dumps({"title": "Robotics Talk", "speaker": "Dr. Anand", "year": "2025"}),
                },
            ],
            metadata={"doc_id": "doc1", "story_id": "s1", "task_type": "grounded_rewriting"},
        )
        violations = self.auditor.audit_example(example)
        self.assertEqual(len(violations), 0)


if __name__ == "__main__":
    unittest.main()
