"""Calibration tests for Quality Gates and Routing Logic."""

import pytest
from app.modules.magazine.quality_gates import evaluate_quality_score, route_publication_status


def test_clean_source_auto_publishes():
    """Verify that a clean document with complete sections and strong grounding scores >= 0.80 (auto-publishes)."""
    section_data = {
        "title": "Robotics Lab Breakthrough 2026",
        "description": "Autonomous quadruped legged robot using real-time spatial vision.",
        "writeup": "Team QuadRobo achieved 1st place and ₹75,000 cash award at the national robotics competition.",
        "toc_summary": "Robotics lab team wins national competition.",
    }
    source_facts = [
        {"text": "Team QuadRobo 1st place ₹75,000 award"},
        {"text": "Autonomous quadruped legged robot"},
        {"text": "Real-time spatial vision"},
    ]

    score, feedback = evaluate_quality_score(section_data, source_facts, visual_qc_score=0.95)
    status = route_publication_status(score)

    assert score >= 0.80
    assert status == "published"
    assert len(feedback) == 0


def test_weak_source_routes_to_needs_review():
    """Verify that a weak document with missing sections and poor grounding scores < 0.80 (lands in needs_review)."""
    section_data = {
        "title": "Random Unrelated Title",
        # Missing description, writeup, toc_summary
    }
    source_facts = [
        {"text": "Specific quantum edge computing microcontrollers protocol"},
    ]

    score, feedback = evaluate_quality_score(section_data, source_facts, visual_qc_score=0.50)
    status = route_publication_status(score)

    assert score < 0.80
    assert status == "needs_review"
    assert len(feedback) > 0
