"""Comprehensive tests for Phase 2 Template Intelligence & Selection Service."""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.modules.magazine.template_schema import (
    TemplateMetadata,
    normalize_template_metadata,
)
from app.modules.magazine.template_selection import (
    build_content_profile,
    validate_template_candidate,
    recommend_template,
    select_template,
)
from app.modules.magazine.template_library import get_standard_templates


# ============================================================================
# 1. UNIT TESTS: Metadata Validation & Constraints
# ============================================================================

def test_metadata_validation_rejects_text_capacity_overflow():
    """Validates that a template is rejected if text word count exceeds declared capacity."""
    tmpl = normalize_template_metadata({
        "name": "Micro Showcase",
        "template_metadata": {
            "template_id": "micro_showcase_01",
            "page_type": "project_showcase",
            "supported_content_types": ["project_showcase"],
            "image_count": 1,
            "text_capacity": {"max_words": 50},
        }
    })
    long_content = "Word " * 120
    profile = build_content_profile(
        content=long_content,
        page_type="project_showcase",
        available_photographs=[{"id": "img1"}],
    )
    val = validate_template_candidate(tmpl, profile)
    assert val.is_valid is False
    assert any("exceeding template capacity" in issue for issue in val.issues)


def test_metadata_validation_rejects_image_shortage():
    """Validates that a template requiring multiple images is rejected if insufficient photos."""
    tmpl = normalize_template_metadata({
        "name": "Robotics Triple Frame",
        "template_metadata": {
            "template_id": "robotics_triple_frame",
            "page_type": "project_showcase",
            "supported_content_types": ["project_showcase"],
            "image_count": 3,
            "layout_constraints": {"min_images": 3},
            "text_capacity": {"max_words": 300},
        }
    })
    profile = build_content_profile(
        content="Autonomous quadruped prototype details.",
        page_type="project_showcase",
        available_photographs=[{"id": "only_one_photo"}],
    )
    val = validate_template_candidate(tmpl, profile)
    assert val.is_valid is False
    assert any("requires 3 image" in issue for issue in val.issues)


def test_dynamic_department_and_lab_matching_no_hardcoding():
    """
    Validates dynamic case-insensitive matching for arbitrary non-hardcoded
    departments and labs (e.g. Mechatronics, Quantum Computing).
    """
    candidates = [
        {
            "name": "Quantum Lab Showcase",
            "template_metadata": {
                "template_id": "quantum_lab_tmpl",
                "department": "Aeronautical Engineering",
                "lab": "Quantum Computing Lab",
                "page_type": "research",
                "supported_content_types": ["research", "article"],
                "image_count": 1,
                "text_capacity": {"max_words": 400},
            }
        },
        {
            "name": "Generic Article",
            "template_metadata": {
                "template_id": "generic_article_tmpl",
                "department": None,
                "lab": None,
                "page_type": "article",
                "supported_content_types": ["article", "research"],
                "image_count": 1,
                "text_capacity": {"max_words": 400},
            }
        },
    ]

    tmpl_quantum = normalize_template_metadata(candidates[0])
    profile_match = build_content_profile(
        content="Quantum entanglement experiment notes.",
        department="Aeronautical Engineering",
        lab="Quantum Computing Lab",
        page_type="research",
        available_photographs=[{"id": "q1"}],
    )
    val_match = validate_template_candidate(tmpl_quantum, profile_match)
    assert val_match.is_valid is True

    profile_mismatch = build_content_profile(
        content="Quantum experiment notes.",
        department="Civil Engineering",
        lab="Structural Dynamics Lab",
        page_type="research",
        available_photographs=[{"id": "q1"}],
    )
    val_mismatch = validate_template_candidate(tmpl_quantum, profile_mismatch)
    assert val_mismatch.is_valid is False
    assert any("department" in issue for issue in val_mismatch.issues)


@pytest.mark.asyncio
async def test_backend_validation_overrides_invalid_llm_advice(monkeypatch):
    """
    Verifies that if the LLM recommends an invalid candidate (e.g. image requirement violated),
    the backend strictly invalidates it and selects the best valid candidate.
    """
    # Simulate LLM recommending the 3-image robotics template
    mock_llm_output = {
        "candidates": [
            {"template_id": "robotics_triple_candidate", "confidence": 0.98}
        ]
    }

    async def mock_call_llm_json(*args, **kwargs):
        return mock_llm_output

    monkeypatch.setattr("app.modules.magazine.template_selection.call_llm_json", mock_call_llm_json)

    candidates = [
        {
            "name": "Robotics Triple Frame",
            "template_metadata": {
                "template_id": "robotics_triple_candidate",
                "page_type": "project_showcase",
                "supported_content_types": ["project_showcase"],
                "image_count": 3,
                "layout_constraints": {"min_images": 3},
                "text_capacity": {"max_words": 300},
            }
        },
        {
            "name": "Single Photo Project",
            "template_metadata": {
                "template_id": "single_photo_candidate",
                "page_type": "project_showcase",
                "supported_content_types": ["project_showcase"],
                "image_count": 1,
                "layout_constraints": {"min_images": 1},
                "text_capacity": {"max_words": 300},
            }
        },
    ]

    # Only 1 photograph available! The 3-image candidate MUST be rejected despite LLM advice.
    selected = await select_template(
        content="Autonomous vehicle prototype with lidar sensor.",
        page_type="project_showcase",
        available_images=[{"id": "photo_single"}],
        candidate_templates=candidates,
        use_llm=True,
    )

    assert selected["template_id"] == "single_photo_candidate"
    assert selected["page_type"] == "project_showcase"
    assert selected["validation"]["is_valid"] is True


# ============================================================================
# 2. FLOW DEMONSTRATIONS: At least three different template types
# ============================================================================

@pytest.mark.asyncio
async def test_demonstration_type_1_ai_lab_project_showcase():
    """
    Demonstration Type 1: AI Lab Project Showcase.
    Target: Project showcase with 2 images, technical writeup for an AI lab prototype.
    """
    ai_content = {
        "title": "Vision-Language Autonomous Agent for Edge Robotics",
        "description": "Applied AI Lab researchers deployed a multimodal compact vision model on embedded hardware.",
        "writeup": (
            "The Applied AI Lab team presented their latest edge agent capable of zero-shot visual navigation. "
            "Using quantized transformer backbones, the system processes 30 frames per second on battery-constrained "
            "micro-controllers while maintaining high spatial localization accuracy."
        ),
    }

    result = await select_template(
        content=ai_content,
        department="Computer Science & Engineering",
        lab="AI Lab",
        section="Projects",
        available_images=[
            {"id": "edge_board_1", "url": "/uploads/edge_board.jpg"},
            {"id": "field_test_2", "url": "/uploads/field_test.jpg"},
        ],
        use_llm=False,
    )

    # Output schema verification
    assert "template_id" in result
    assert "page_type" in result
    assert "confidence" in result
    assert "reason" in result
    assert result["template_id"] == "ai_lab_project_showcase"
    assert result["page_type"] == "project_showcase"
    assert result["confidence"] >= 0.85
    assert "AI Lab" in result["reason"] or "matches" in result["reason"]


@pytest.mark.asyncio
async def test_demonstration_type_2_student_achievement():
    """
    Demonstration Type 2: Student Achievement Spotlight.
    Target: Single-photo celebratory layout for a national hackathon win.
    """
    student_content = {
        "title": "Undergraduate Team Secures 1st Place at National Smart India Hackathon",
        "description": "Final year students won top prize with a ₹1,00,000 cash grant for their smart healthcare triage app.",
        "writeup": (
            "A four-member undergraduate team clinched the first prize at SIH 2026. "
            "Their platform provides automated patient queue optimization in rural clinical settings."
        ),
    }

    result = await select_template(
        content=student_content,
        section="Student achievements",
        available_images=[
            {"id": "award_ceremony", "url": "/uploads/award.jpg"}
        ],
        use_llm=False,
    )

    assert result["template_id"] == "student_achievement_spotlight"
    assert result["page_type"] == "student_achievement"
    assert result["confidence"] >= 0.70
    assert result["validation"]["is_valid"] is True


@pytest.mark.asyncio
async def test_demonstration_type_3_department_activities_digest():
    """
    Demonstration Type 3: Department Activities Quarterly Digest.
    Target: Multi-section editorial article format with long narrative.
    """
    dept_content = {
        "title": "Annual Department Symposium & Industry Collaborative Review",
        "description": "Over 500 delegates attended technical keynotes and industrial memorandum signings.",
        "writeup": (
            "The Department conducted its flagship quarterly academic symposium bringing together industry "
            "leaders, alumni fellows, and student researchers. Seven Memorandums of Understanding were executed "
            "with tier-1 engineering firms to establish co-developed research hubs. Multiple hands-on workshops "
            "in additive manufacturing and embedded firmware architectures were conducted throughout the week."
        ),
    }

    result = await select_template(
        content=dept_content,
        department="Mechanical Engineering",
        section="Department activities",
        available_images=[
            {"id": "symposium_stage", "url": "/uploads/stage.jpg"},
            {"id": "mou_signing", "url": "/uploads/mou.jpg"},
        ],
        use_llm=False,
    )

    assert result["template_id"] == "department_activities_digest"
    assert result["page_type"] == "article"
    assert result["confidence"] >= 0.75
    assert result["validation"]["is_valid"] is True


# ============================================================================
# 3. API INTEGRATION TEST: POST /api/v1/magazine/templates/select
# ============================================================================

@pytest.mark.asyncio
async def test_api_template_select_endpoint():
    """Tests the REST API endpoint for template selection."""
    payload = {
        "content": {
            "title": "Quadruped Autonomous Terrain Navigation",
            "description": "Robotics Lab prototype demo.",
        },
        "lab": "Robotics Lab",
        "section": "Projects",
        "available_images": [
            {"id": "robot_front"},
            {"id": "robot_side"},
            {"id": "robot_field"},
        ],
        "use_llm": False,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/magazine/templates/select", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        payload_data = data["data"]
        assert payload_data["template_id"] == "robotics_lab_autonomous_systems"
        assert payload_data["page_type"] == "project_showcase"
        assert payload_data["confidence"] >= 0.80
        assert "template_id" in payload_data
        assert "reason" in payload_data
