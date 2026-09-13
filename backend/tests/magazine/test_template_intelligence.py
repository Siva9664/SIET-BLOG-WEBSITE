import pytest

from app.modules.magazine.file_parser import parse_template_file
from app.modules.magazine.template_schema import normalize_template_metadata
from app.modules.magazine.template_selection import (
    build_content_profile,
    recommend_template,
    validate_template_candidate,
)


def test_parse_template_file_adds_professional_metadata():
    parsed = parse_template_file(
        b"""
        Template ID: AI Lab Project 03
        Department: Computer Science
        Lab: Applied AI Lab
        Section: Projects
        Page Type: Project Showcase
        Supported Content Types: project showcase, research
        Image Count: 2
        Text Capacity: 220

        PROJECT SHOWCASE
        Gallery:
        """,
        "ai-lab-project-template.txt",
    )

    metadata = parsed["style_rules"]["metadata"]

    assert metadata["template_id"] == "ai_lab_project_03"
    assert metadata["department"] == "Computer Science"
    assert metadata["lab"] == "Applied AI Lab"
    assert metadata["page_type"] == "project_showcase"
    assert metadata["supported_content_types"] == ["project_showcase", "research"]
    assert metadata["image_count"] == 2
    assert metadata["text_capacity"]["max_words"] == 220


def test_normalize_template_metadata_supports_legacy_template_dict():
    metadata = normalize_template_metadata(
        {
            "id": 7,
            "name": "Research Gallery",
            "section_schema": [
                {"section_type": "research", "label": "Research Highlights", "enabled": True},
                {"section_type": "gallery", "label": "Photo Gallery", "enabled": True},
            ],
            "style_rules": {
                "accent_color": "#0055aa",
                "font_body": "Georgia",
            },
        }
    )

    assert metadata.template_id == "7"
    assert metadata.page_type == "photo_gallery"
    assert "research" in metadata.supported_content_types
    assert "photo_gallery" in metadata.supported_content_types
    assert metadata.colors["accent_color"] == "#0055aa"


def test_validate_template_candidate_rejects_constraint_violations():
    template = normalize_template_metadata(
        {
            "name": "Two Photo Project",
            "style_rules": {
                "metadata": {
                    "template_id": "PROJECT_TWO_PHOTO",
                    "department": "ECE",
                    "page_type": "project_showcase",
                    "supported_content_types": ["project_showcase"],
                    "image_count": 2,
                    "text_capacity": {"max_words": 20},
                }
            },
        }
    )
    profile = build_content_profile(
        "A long project description " * 30,
        department="CSE",
        page_type="project_showcase",
        available_photographs=[{"id": "photo_1"}],
    )

    result = validate_template_candidate(template, profile)

    assert result.is_valid is False
    assert any("department" in issue for issue in result.issues)
    assert any("requires 2 image" in issue for issue in result.issues)
    assert any("exceeding template capacity" in issue for issue in result.issues)


@pytest.mark.asyncio
async def test_recommend_template_selects_best_valid_candidate_without_hardcoded_departments():
    templates = [
        {
            "name": "Generic Article",
            "style_rules": {
                "metadata": {
                    "template_id": "GENERIC_ARTICLE",
                    "page_type": "article",
                    "supported_content_types": ["article"],
                    "image_count": 0,
                    "text_capacity": {"max_words": 500},
                }
            },
        },
        {
            "name": "AI Lab Project Showcase",
            "style_rules": {
                "metadata": {
                    "template_id": "AI_LAB_PROJECT_03",
                    "department": "Computer Science",
                    "lab": "Applied AI Lab",
                    "section": "Projects",
                    "page_type": "project_showcase",
                    "supported_content_types": ["project_showcase", "research"],
                    "image_count": 1,
                    "text_capacity": {"max_words": 180},
                    "typography": {"headline": {"font_size_pt": 24}},
                    "colors": {"accent_color": "#1d4ed8"},
                }
            },
        },
        {
            "name": "Wrong Lab Project",
            "style_rules": {
                "metadata": {
                    "template_id": "OTHER_LAB_PROJECT",
                    "department": "Mechanical",
                    "page_type": "project_showcase",
                    "supported_content_types": ["project_showcase"],
                    "image_count": 1,
                    "text_capacity": {"max_words": 180},
                }
            },
        },
    ]

    recommendation = await recommend_template(
        content={
            "title": "Students Develop an Autonomous Navigation System",
            "description": "The Applied AI Lab team built a navigation prototype.",
        },
        templates=templates,
        section="Projects",
        department="Computer Science",
        lab="Applied AI Lab",
        page_type="project_showcase",
        available_photographs=[{"id": "photo_17"}],
    )

    assert recommendation.template_id == "AI_LAB_PROJECT_03"
    assert recommendation.page_type == "project_showcase"
    assert recommendation.validation.is_valid is True
    assert recommendation.confidence >= 0.8

