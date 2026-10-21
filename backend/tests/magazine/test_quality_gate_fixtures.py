"""Calibration tests for Claim-Level Quality Gates and Routing Logic."""

import pytest
from app.modules.magazine.quality_gates import evaluate_quality_score, route_publication_status


@pytest.mark.asyncio
async def test_clean_source_auto_publishes():
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

    score, feedback = await evaluate_quality_score(section_data, source_facts, visual_qc_score=0.95)
    status = route_publication_status(score)

    assert score >= 0.80
    assert status == "published"
    assert len(feedback) == 0


@pytest.mark.asyncio
async def test_weak_source_routes_to_needs_review():
    """Verify that a weak document with missing sections and poor grounding scores < 0.80 (lands in needs_review)."""
    section_data = {
        "title": "Random Unrelated Title",
        # Missing description, writeup, toc_summary
    }
    source_facts = [
        {"text": "Specific quantum edge computing microcontrollers protocol"},
    ]

    score, feedback = await evaluate_quality_score(section_data, source_facts, visual_qc_score=0.50)
    status = route_publication_status(score)

    assert score < 0.80
    assert status == "needs_review"
    assert len(feedback) > 0


@pytest.mark.asyncio
async def test_adversarial_injected_false_claim_caught():
    """Verify that an injected false claim in the writeup drops the grounding score and generates feedback."""
    section_data = {
        "title": "Robotics Lab Breakthrough 2026",
        "description": "Autonomous quadruped legged robot using real-time spatial vision.",
        "writeup": "Team QuadRobo achieved 1st place at the competition. They invented a perpetual motion alien technology that powers the robot without energy.",
        "toc_summary": "Robotics lab team wins national competition.",
    }
    source_facts = [
        {"text": "Team QuadRobo 1st place award"},
        {"text": "Autonomous quadruped legged robot"},
    ]

    score, feedback = await evaluate_quality_score(section_data, source_facts, visual_qc_score=0.90)

    assert any("unsupported claim" in fb.lower() for fb in feedback)
