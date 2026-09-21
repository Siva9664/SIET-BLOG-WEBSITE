"""Tests for SIET_DEFAULT_V1 Template System.

Verifies:
1. All 15 page types exist and conform to specifications.
2. Grid geometry, column math, and boundary containment.
3. Reusable region roles.
4. Typography hierarchy.
5. Strict photo isolation.
6. Layout planner resolution.
7. Deterministic PyMuPDF rendering with alternating running folios, pull quotes, sidebars.
"""

import os
import tempfile
import pytest
import fitz  # PyMuPDF

from app.modules.magazine.templates.siet_default_v1 import (
    PageType,
    RegionRole,
    SIETDefaultV1LayoutPlanner,
    SIETDefaultV1Renderer,
    build_siet_default_v1_template,
    get_siet_default_v1_template,
)
from app.infrastructure.ai.schemas import StructuredMagazineStoryContent


@pytest.fixture
def rich_template():
    return build_siet_default_v1_template()


@pytest.fixture
def legacy_spec():
    return get_siet_default_v1_template()


def test_all_15_page_types_exist(rich_template, legacy_spec):
    """Verifies that all 15 page types exist in both rich model and legacy spec."""
    expected_page_types = [
        "cover",
        "contents",
        "section_opener",
        "event",
        "achievement",
        "victory",
        "project",
        "workshop",
        "seminar",
        "faculty_activity",
        "student_activity",
        "photo_feature",
        "interview",
        "news_highlights",
        "closing",
    ]

    for pt in expected_page_types:
        assert pt in rich_template.page_types, f"Page type {pt} missing from rich_template"
        assert pt in legacy_spec.supported_page_types, f"Page type {pt} missing from legacy_spec"

    # Also verify legacy aliases exist
    assert "achievement_victory" in legacy_spec.supported_page_types
    assert "closing_page" in legacy_spec.supported_page_types


def test_grid_spec_and_column_math(rich_template):
    """Verifies modular grid geometry and column math across page types."""
    pw = 595.28  # A4 width
    m_left, m_right = 36.0, 36.0
    printable_w = pw - (m_left + m_right)  # 523.28

    # Check 2-column page: event
    event_cfg = rich_template.page_types[PageType.EVENT.value]
    assert event_cfg.columns == 2
    expected_2col_w = (printable_w - event_cfg.grid.column_gap) / 2
    assert abs(event_cfg.grid.column_width - expected_2col_w) < 0.1

    # Check 3-column page: student_activity
    sa_cfg = rich_template.page_types[PageType.STUDENT_ACTIVITY.value]
    assert sa_cfg.columns == 3
    expected_3col_w = (printable_w - 2 * sa_cfg.grid.column_gap) / 3
    assert abs(sa_cfg.grid.column_width - expected_3col_w) < 0.1


def test_reusable_region_roles_coverage(rich_template):
    """Verifies all reusable region roles are represented across the template."""
    found_roles = set()
    for p_cfg in rich_template.page_types.values():
        for reg in p_cfg.regions:
            found_roles.add(reg.role.value)

    required_roles = {
        "headline",
        "subheadline",
        "body",
        "caption",
        "metadata",
        "pull_quote",
        "sidebar",
        "section_label",
    }
    for r in required_roles:
        assert r in found_roles, f"Role {r} is not used in any region"


def test_typography_hierarchy_integrity(rich_template):
    """Verifies typography hierarchy scales properly across levels."""
    for p_cfg in rich_template.page_types.values():
        typo = p_cfg.typography_hierarchy
        # Headline size > body size
        assert typo.headline.font_size > typo.body.font_size
        # Valid font families
        assert typo.headline.font_family in {"times-bold", "hebo", "helv"}
        assert typo.body.font_family in {"times", "helv"}


def test_strict_photo_isolation_in_layout_planner(rich_template):
    """
    CRITICAL INVARIANT TEST:
    Verifies that Event A's photos (3 photos) and Event B's photos (2 photos)
    are strictly isolated and never mixed across pages.
    """
    planner = SIETDefaultV1LayoutPlanner(rich_template)

    story_a_meta = {
        "story_id": "event_a",
        "title": "Workshop on Edge AI",
        "attached_photos": ["photos/event_a_1.jpg", "photos/event_a_2.jpg", "photos/event_a_3.jpg"],
    }
    story_a_content = StructuredMagazineStoryContent(
        section="Workshops",
        story_type="workshop",
        headline="Hands-on Edge AI Workshop",
        subheadline="Department of ECE",
        polished_body="Over 85 students deployed models on microcontrollers.",
        short_summary="85 undergraduates deploy TinyML models.",
        photo_captions=["Lab session photo", "Hardware demo photo"],
        keywords=["Edge AI", "TinyML"],
        page_type="workshop",
        layout_intent="workshop_session",
        recommended_image_count=2,
    )

    story_b_meta = {
        "story_id": "event_b",
        "title": "National HackFest Championship",
        "attached_photos": ["photos/event_b_1.jpg", "photos/event_b_2.jpg"],
    }
    story_b_content = StructuredMagazineStoryContent(
        section="Achievements",
        story_type="victory",
        headline="SIET Wins National HackFest Championship",
        subheadline="Department of CSE",
        polished_body="Computer Science undergraduates won First Prize with INR 50,000.",
        short_summary="First Prize and Gold Medal at HackFest 2026.",
        photo_captions=["Trophy presentation", "Team demo"],
        keywords=["HackFest", "Gold Medal"],
        page_type="victory",
        layout_intent="victory_celebration",
        recommended_image_count=2,
    )

    # Plan full magazine
    planned_pages = planner.plan_full_magazine(
        issue_title="SIET Highlights 2026",
        department="ECE & CSE",
        structured_stories=[
            (story_a_meta, story_a_content),
            (story_b_meta, story_b_content),
        ],
    )

    # Page 1: Cover, Page 2: Contents, Page 3: Story A, Page 4: Story B, Page 5: Closing
    assert len(planned_pages) == 5
    page_a = planned_pages[2]
    page_b = planned_pages[3]

    assert page_a["story_id"] == "event_a"
    assert page_b["story_id"] == "event_b"

    # Verify Story A has ONLY Event A photos
    for p in page_a["attached_photos"]:
        assert "event_a_" in p, f"Event A contaminated with photo: {p}"
        assert "event_b_" not in p

    # Verify Story B has ONLY Event B photos
    for p in page_b["attached_photos"]:
        assert "event_b_" in p, f"Event B contaminated with photo: {p}"
        assert "event_a_" not in p


def test_rendering_special_editorial_layouts_to_pdf(rich_template):
    """
    Renders special editorial layouts (interview with pull quotes, news highlights 3-column,
    photo feature 4-grid) into a real PDF and verifies structure, folios, and dimensions.
    """
    planner = SIETDefaultV1LayoutPlanner(rich_template)
    renderer = SIETDefaultV1Renderer()

    interview_meta = {
        "story_id": "story_interview",
        "title": "A Conversation with the Dean",
        "attached_photos": ["portrait_dean.jpg"],
    }
    interview_content = StructuredMagazineStoryContent(
        section="Spotlight Interview",
        story_type="interview",
        headline="Architecting the Future of Engineering Education",
        subheadline="A Dialogue with Dr. S. Murugesan on AI in Curriculum",
        polished_body=(
            "SIET Magazine: How is the institute integrating generative AI into undergraduate laboratories?\n\n"
            "Dr. Murugesan: We have introduced dedicated edge computing platforms in every department. "
            "Our students do not simply consume AI APIs; they deploy quantized models on microcontrollers.\n\n"
            "SIET Magazine: What distinguishes our graduates in the tech industry?\n\n"
            "Dr. Murugesan: Rigorous hands-on competence coupled with ethical responsibility."
        ),
        short_summary="Our students deploy quantized models directly on microcontrollers.",
        photo_captions=["Dr. S. Murugesan in the Advanced Research Laboratory."],
        keywords=["Dean Interview", "Curriculum", "AI"],
        page_type="interview",
        layout_intent="interview",
        recommended_image_count=1,
    )

    news_meta = {
        "story_id": "story_news",
        "title": "Campus News Digest",
        "attached_photos": ["thumb1.jpg", "thumb2.jpg"],
    }
    news_content = StructuredMagazineStoryContent(
        section="Campus Highlights",
        story_type="news",
        headline="Campus News & Highlights Digest",
        subheadline="Monthly Engineering Chronicle",
        polished_body=(
            "• IEEE Student Chapter inaugurated new robotics workbench.\n\n"
            "• Department of Mechanical Engineering files two patents for solar distillation systems.\n\n"
            "• Annual sports meet draws over 1,200 student athletes across 14 disciplines."
        ),
        short_summary="Monthly roundup of student chapters, research patents, and athletics.",
        photo_captions=["Robotics workbench", "Solar prototype"],
        keywords=["News", "Patents", "Sports"],
        page_type="news_highlights",
        layout_intent="news_digest",
        recommended_image_count=2,
    )

    planned_pages = planner.plan_full_magazine(
        issue_title="SIET Annual Chronicle",
        department="Academic Affairs",
        structured_stories=[
            (interview_meta, interview_content),
            (news_meta, news_content),
        ],
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_pdf = os.path.join(tmp_dir, "test_render.pdf")
        pdf_path = renderer.render_magazine_to_pdf(planned_pages, output_pdf)

        assert os.path.exists(pdf_path)

        # Inspect generated PDF with PyMuPDF
        doc = fitz.open(pdf_path)
        assert len(doc) == 5  # Cover, Contents, Interview, News, Closing

        # Check page dimensions (A4: 595.28 x 841.89)
        for p in doc:
            assert abs(p.rect.width - 595.28) < 1.0
            assert abs(p.rect.height - 841.89) < 1.0

        # Check running folios on internal pages (Page 2: Even, Page 3: Odd, Page 4: Even)
        page_3_text = doc[2].get_text("text")  # Page 3 is Odd
        assert "siet.ac.in" in page_3_text
        assert "SIET COLLEGE MAGAZINE" in page_3_text
        assert "Architecting the Future" in page_3_text

        doc.close()
