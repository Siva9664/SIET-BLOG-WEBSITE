"""Comprehensive Test Suite for Phase 6: AUTOMATIC MULTI-PAGE MAGAZINE PLANNING."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.magazine.multi_page_planner import (
    plan_multi_page_magazine,
    _normalize_content_items,
    _find_candidate_templates_for_section,
    _extract_template_capacities,
)
from app.modules.magazine.template_library import (
    get_standard_templates,
    get_template_by_id,
)
from app.modules.magazine.template_schema import (
    TemplateMetadata,
    normalize_template_metadata,
)


def test_multi_page_small_content():
    """
    Tests small content input:
      - 1 lab intro, 1 project, 1 student achievement, 2 photos.
    Verifies:
      - Clean 3-page sequence without excessive empty pages.
      - Sequential page numbering (1, 2, 3).
      - No page overloading.
    """
    small_content = {
        "department_or_lab": "AI Lab",
        "sections": {
            "introduction": {
                "title": "AI Lab Vision 2026",
                "body": "Accelerating trustworthy autonomy through neural-symbolic systems.",
            },
            "projects": [
                {
                    "id": "proj_quadruped",
                    "title": "Autonomous Quadruped Robot",
                    "body": "Students engineered a terrain-adaptive quadruped with onboard LiDAR.",
                }
            ],
            "achievements": [
                {
                    "id": "achieve_national_hackathon",
                    "title": "National AI Hackathon 1st Prize",
                    "body": "Team SIET claimed first place among 450 engineering institutions.",
                }
            ],
        },
    }
    photos = ["quadruped.jpg", "hackathon_team.jpg"]

    res = plan_multi_page_magazine(
        structured_content=small_content,
        department_or_lab="AI Lab",
        available_images=photos,
    )

    assert res.total_pages == 3
    assert len(res.pages) == 3

    # Page 1: Introduction
    assert res.pages[0].page_number == 1
    assert res.pages[0].page_type == "introduction"
    assert res.pages[0].content_ids == ["introduction_01"]

    # Page 2: Project Showcase
    assert res.pages[1].page_number == 2
    assert res.pages[1].page_type == "project_showcase"
    assert res.pages[1].content_ids == ["proj_quadruped"]
    assert len(res.pages[1].assigned_images) >= 1

    # Page 3: Student Achievement
    assert res.pages[2].page_number == 3
    assert res.pages[2].page_type == "student_achievement"
    assert res.pages[2].content_ids == ["achieve_national_hackathon"]

    # Monotonic page numbering
    assert [p.page_number for p in res.pages] == [1, 2, 3]


def test_multi_page_medium_content():
    """
    Tests medium content input:
      - 5 projects, 4 achievements, 3 events, 8 photos.
    Verifies:
      - Appropriate page count sequence (~6-8 pages).
      - Capacity packing respects template limits.
      - Layout alternation avoids repetitive spreads.
      - Section ordering is preserved.
    """
    medium_content = {
        "department_or_lab": "AI Lab",
        "sections": {
            "introduction": {"title": "AI Lab Overview", "body": "Overview of lab research directions."},
            "projects": [
                {"id": f"p_{i+1}", "title": f"Project Prototype {i+1}", "estimated_words": 140}
                for i in range(5)
            ],
            "achievements": [
                {"id": f"a_{i+1}", "title": f"Student Honor {i+1}", "estimated_words": 90}
                for i in range(4)
            ],
            "events": [
                {"id": f"e_{i+1}", "title": f"Symposium Keynote {i+1}", "estimated_words": 110}
                for i in range(3)
            ],
        },
    }
    photos = [f"photo_{i+1:02d}.jpg" for i in range(8)]

    res = plan_multi_page_magazine(
        structured_content=medium_content,
        department_or_lab="AI Lab",
        available_images=photos,
    )

    # 1 intro + 3 project pages (2, 2, 1) + 1 or 2 achievement pages + 2 event pages
    assert 6 <= res.total_pages <= 9
    assert [p.page_number for p in res.pages] == list(range(1, res.total_pages + 1))

    # Verify section sequence flow: Introduction -> Projects -> Achievements -> Events
    sections_seen = []
    for p in res.pages:
        sec = p.section
        if not sections_seen or sections_seen[-1] != sec:
            sections_seen.append(sec)

    assert sections_seen == ["Introduction", "Project Showcase", "Student Achievement", "Event"]

    # Verify layout alternation within Projects
    project_pages = [p for p in res.pages if p.page_type == "project_showcase"]
    assert len(project_pages) >= 2
    # Consecutive project pages should alternate template or layout_variant
    for idx in range(len(project_pages) - 1):
        p_curr = project_pages[idx]
        p_next = project_pages[idx + 1]
        assert (p_curr.template_id != p_next.template_id) or (p_curr.layout_variant != p_next.layout_variant)


def test_multi_page_very_large_content_exact_prompt_example():
    """
    Target prompt example:
      AI Lab:
        - 25 projects
        - 18 achievements
        - 40 photographs
        - 10 events
    Verifies:
      - Automatically calculates required page sequence.
      - Never overloads pages beyond template capacity.
      - Never leaves excessive empty space (each page has at least 1 valid item).
      - All 25 projects, 18 achievements, and 10 events are fully accounted for.
      - Unassigned photographs are automatically accommodated into a photo gallery spread.
      - Page numbering is strictly sequential from 1 to total_pages.
    """
    large_content = {
        "department_or_lab": "AI Lab",
        "sections": {
            "introduction": {"title": "AI Lab Annual Report", "body": "Comprehensive review."},
            "projects": 25,
            "achievements": 18,
            "events": 10,
        },
    }
    photos = [f"campus_photo_{i+1:02d}.jpg" for i in range(40)]

    res = plan_multi_page_magazine(
        structured_content=large_content,
        department_or_lab="AI Lab",
        available_images=photos,
    )

    assert res.total_pages >= 20
    assert [p.page_number for p in res.pages] == list(range(1, res.total_pages + 1))

    # Verify all project IDs are tracked
    all_project_ids = []
    for p in res.pages:
        if p.page_type == "project_showcase":
            all_project_ids.extend(p.content_ids)
    assert len(all_project_ids) == 25
    assert len(set(all_project_ids)) == 25  # No duplicates

    # Verify all achievement IDs are tracked
    all_achievement_ids = []
    for p in res.pages:
        if p.page_type == "student_achievement":
            all_achievement_ids.extend(p.content_ids)
    assert len(all_achievement_ids) == 18
    assert len(set(all_achievement_ids)) == 18

    # Verify all event IDs are tracked
    all_event_ids = []
    for p in res.pages:
        if p.page_type == "event":
            all_event_ids.extend(p.content_ids)
    assert len(all_event_ids) == 10
    assert len(set(all_event_ids)) == 10

    # Verify no page is empty or overloaded
    for p in res.pages:
        assert len(p.content_ids) >= 1
        assert len(p.content_ids) <= 4  # maximum capacity bound


def test_multi_page_missing_images_zero_photos():
    """
    Tests graceful degradation when zero photographs are available:
      - available_images = []
    Verifies:
      - System does not raise an exception or fail.
      - Successfully generates complete multi-page plan.
      - Pages have empty assigned_images or rely on typography.
    """
    content = {
        "department_or_lab": "AI Lab",
        "sections": {
            "introduction": {"title": "Theoretical Foundations", "body": "Mathematical formulations."},
            "projects": 3,
            "achievements": 2,
        },
    }

    res = plan_multi_page_magazine(
        structured_content=content,
        department_or_lab="AI Lab",
        available_images=[],  # 0 images available
    )

    assert res.total_pages >= 3
    for p in res.pages:
        assert p.page_number >= 1
        assert p.template_id is not None
        assert len(p.content_ids) >= 1
        assert isinstance(p.assigned_images, list)


def test_multi_page_insufficient_template_types_single_template():
    """
    Tests system behavior when only 1 candidate template exists in the environment:
      - available_templates = [only_one_template]
    Verifies:
      - System does not crash.
      - Correctly allows multiple pages of the same template ("allow multiple pages of the same template").
      - Rotates layout_variant across pages to provide visual variety.
      - Automatic sequential page numbering is preserved (1, 2, 3, 4).
    """
    single_template = {
        "template_id": "ai_lab_project_showcase",
        "name": "AI Lab Project Showcase",
        "page_type": "project_showcase",
        "lab": "AI Lab",
        "image_count": 2,
        "layout_constraints": {"min_items": 1, "max_items": 2},
    }

    content = {
        "department_or_lab": "AI Lab",
        "sections": {
            "projects": [
                {"id": "proj_1", "title": "Robot Arm"},
                {"id": "proj_2", "title": "Vision Telemetry"},
                {"id": "proj_3", "title": "Drone Navigation"},
                {"id": "proj_4", "title": "Edge TPU"},
            ]
        },
    }

    res = plan_multi_page_magazine(
        structured_content=content,
        department_or_lab="AI Lab",
        available_templates=[single_template],
    )

    assert res.total_pages == 2
    assert res.pages[0].template_id == "ai_lab_project_showcase"
    assert res.pages[1].template_id == "ai_lab_project_showcase"
    assert res.pages[0].page_number == 1
    assert res.pages[1].page_number == 2

    # Verify that layout variant rotates between consecutive pages
    assert res.pages[0].layout_variant != res.pages[1].layout_variant


def test_multi_page_lab_specific_templates():
    """
    Verifies that the planner selects lab-appropriate templates:
      - AI Lab selects AI Lab templates.
      - Robotics Lab selects Robotics Lab templates.
      - IoT Lab selects IoT Lab templates.
    """
    content = {
        "sections": {
            "projects": [
                {"id": "p1", "title": "Project Alpha"},
                {"id": "p2", "title": "Project Beta"},
            ]
        }
    }

    # 1. AI Lab
    res_ai = plan_multi_page_magazine(structured_content=content, department_or_lab="AI Lab")
    assert any("ai_lab" in p.template_id for p in res_ai.pages)

    # 2. Robotics Lab
    res_robotics = plan_multi_page_magazine(structured_content=content, department_or_lab="Robotics Lab")
    assert any("robotics_lab" in p.template_id for p in res_robotics.pages)

    # 3. IoT Lab
    res_iot = plan_multi_page_magazine(structured_content=content, department_or_lab="IoT Lab")
    assert any("iot_lab" in p.template_id for p in res_iot.pages)


def test_multi_page_custom_section_ordering():
    """
    Verifies that user-specified magazine_section_order is strictly followed.
    """
    content = {
        "sections": {
            "projects": [{"id": "p1", "title": "Project 1"}],
            "events": [{"id": "e1", "title": "Event 1"}],
            "introduction": {"title": "Intro", "body": "Welcome"},
            "achievements": [{"id": "a1", "title": "Award 1"}],
        }
    }

    # Custom order: Events first, then Achievements, then Projects, then Intro
    custom_order = ["events", "achievements", "projects", "introduction"]
    res = plan_multi_page_magazine(
        structured_content=content,
        magazine_section_order=custom_order,
    )

    page_sections = [p.section for p in res.pages]
    assert page_sections == ["Event", "Student Achievement", "Project Showcase", "Introduction"]


@pytest.mark.asyncio
async def test_api_multi_page_plan_endpoint():
    """
    Tests HTTP POST on /api/v1/magazine/pages/plan.
    Verifies the exact output JSON structure:
      {
        "pages": [
          {
            "page_number": 1,
            "template_id": "...",
            "content_ids": [...]
          }
        ]
      }
    """
    payload = {
        "structured_content": {
            "department_or_lab": "AI Lab",
            "sections": {
                "introduction": {"title": "Lab Vision", "body": "Core AI breakthroughs."},
                "projects": [
                    {"id": "ai_p1", "title": "Autonomous Drone"},
                    {"id": "ai_p2", "title": "Edge Neural Processor"},
                ],
                "achievements": [
                    {"id": "ach_1", "title": "Smart India Hackathon Winner"}
                ],
            },
        },
        "department_or_lab": "AI Lab",
        "available_images": ["drone.jpg", "team.jpg"],
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/magazine/pages/plan", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data.get("success") is True
        result = data.get("data")
        assert "pages" in result
        assert len(result["pages"]) >= 2

        # Check required fields on each page
        for p in result["pages"]:
            assert "page_number" in p
            assert "template_id" in p
            assert "content_ids" in p
            assert isinstance(p["content_ids"], list)
            assert len(p["content_ids"]) >= 1

        assert result["pages"][0]["page_number"] == 1
        assert result["pages"][1]["page_number"] == 2
