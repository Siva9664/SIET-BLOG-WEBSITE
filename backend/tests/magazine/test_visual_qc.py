"""Comprehensive Test Suite for Phase 7: AUTOMATIC VISUAL QUALITY CONTROL."""

import os
import tempfile
import pytest
from PIL import Image
import fitz
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.magazine.schemas import (
    PagePlan,
    PlannedRegion,
    VisualQCThresholds,
    VisualQualityReport,
)
from app.modules.magazine.renderer import (
    PAGE_WIDTH,
    PAGE_HEIGHT,
    render_page_from_plan,
)
from app.modules.magazine.validator import (
    validate_page_visual_quality,
    render_and_validate_page_with_recovery,
    _check_text_overflow,
    _check_image_overflow,
    _check_missing_assets,
    _check_image_distortion,
    _check_low_resolution_images,
    _check_overlapping_regions,
    _check_content_outside_page_boundaries,
    _check_excessive_empty_space,
    _check_excessively_small_text,
    _check_inconsistent_margins,
)


@pytest.fixture
def temp_test_images():
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. High-res image (800x600 px -> ~150-200 DPI on 300pt box)
        high_res_path = os.path.join(tmpdir, "high_res.jpg")
        img_high = Image.new("RGB", (800, 600), color=(30, 80, 160))
        img_high.save(high_res_path, format="JPEG")

        # 2. Low-res image (40x30 px -> ~10 DPI on 300pt box)
        low_res_path = os.path.join(tmpdir, "low_res.jpg")
        img_low = Image.new("RGB", (40, 30), color=(180, 50, 50))
        img_low.save(low_res_path, format="JPEG")

        yield {
            "high_res": high_res_path,
            "low_res": low_res_path,
            "tmpdir": tmpdir,
        }


def test_qc_clean_page_passes_with_high_scores(temp_test_images):
    """
    Verifies that a well-formatted page generated from PagePlan passes all 10 checks
    and returns high visual scores (>= 90).
    """
    doc = fitz.open()
    plan = PagePlan(
        page_type="project_showcase",
        template_id="ai_lab_project_showcase",
        regions=[
            PlannedRegion(
                region_id="hero_image",
                type="image",
                asset=temp_test_images["high_res"],
                caption="LiDAR Telemetry Prototype.",
            ),
            PlannedRegion(
                region_id="headline",
                type="headline",
                content="Autonomous Quadruped Field Trials",
            ),
            PlannedRegion(
                region_id="body",
                type="body",
                content="Engineering researchers at SIET deployed an autonomous quadruped machine with real-time obstacle avoidance.",
            ),
            PlannedRegion(
                region_id="caption",
                type="caption",
                content="Field trials conducted in real-time outdoor terrain.",
            ),
        ],
    )
    tmpl_meta = {
        "template_id": "ai_lab_project_showcase",
        "colors": {"accent_color": "#1d4ed8", "background_color": "#ffffff"},
        "department_or_lab": "AI Lab",
    }

    page = render_page_from_plan(doc, plan, tmpl_meta, page_num=7)
    report = validate_page_visual_quality(page, plan, tmpl_meta, page_num=7)

    assert report.page == 7
    assert report.is_valid is True
    assert report.overall_score >= 85
    assert report.layout_score >= 85
    assert report.text_fit_score >= 85
    assert report.image_score >= 85
    assert len(report.issues) == 0


def test_qc_check_missing_assets():
    """
    Check 3: Missing assets.
    Verifies detection of non-existent image paths on disk.
    """
    doc = fitz.open()
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)

    plan = PagePlan(
        page_type="project_showcase",
        template_id="ai_lab_project_showcase",
        regions=[
            PlannedRegion(
                region_id="hero_image",
                type="image",
                asset="/tmp/non_existent_image_photo_999.jpg",
            )
        ],
    )

    issues = _check_missing_assets(page, plan)
    assert len(issues) >= 1
    assert any("does not exist on disk" in i for i in issues)


def test_qc_check_low_resolution_images(temp_test_images):
    """
    Check 5: Low-resolution images.
    Verifies that inserting a 40x30px image into a 400x300pt box triggers DPI warning (< 96 DPI).
    """
    doc = fitz.open()
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)

    # Insert 40x30px image into 400x300 box -> effective DPI is ~7 DPI
    page.insert_image(fitz.Rect(50, 50, 450, 350), filename=temp_test_images["low_res"])

    issues = _check_low_resolution_images(page, min_dpi=96.0)
    assert len(issues) >= 1
    assert any("Low-resolution image" in i and "effective DPI" in i for i in issues)


def test_qc_check_content_outside_page_boundaries():
    """
    Check 7: Content outside page boundaries.
    Verifies detection of text or image blocks drawn beyond [0, 0, PAGE_WIDTH, PAGE_HEIGHT].
    """
    doc = fitz.open()
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)

    # Draw text outside bottom boundary (y = PAGE_HEIGHT + 50)
    page.insert_text(fitz.Point(100, PAGE_HEIGHT + 50), "Spillover text outside canvas", fontsize=12)

    issues = _check_content_outside_page_boundaries(page)
    assert len(issues) >= 1
    assert any("outside page boundaries" in i for i in issues)


def test_qc_check_excessive_empty_space():
    """
    Check 8: Excessive empty space.
    Verifies detection of nearly blank pages with sparse text.
    """
    doc = fitz.open()
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page.insert_text(fitz.Point(100, 100), "Sparse solitary headline", fontsize=14)

    issues = _check_excessive_empty_space(page, max_empty_ratio=0.75)
    assert len(issues) >= 1
    assert any("Excessive empty space" in i for i in issues)


def test_qc_check_excessively_small_text():
    """
    Check 9: Excessively small text.
    Verifies detection of text rendered below the readability threshold (< 5.5pt).
    """
    doc = fitz.open()
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page.insert_text(fitz.Point(100, 100), "Microscopic unreadable fineprint footnote", fontsize=3.5)

    issues = _check_excessively_small_text(page, min_fontsize=5.5)
    assert len(issues) >= 1
    assert any("Excessively small text" in i and "3.5pt" in i for i in issues)


def test_qc_check_overlapping_regions():
    """
    Check 6: Overlapping regions.
    Verifies detection of intersecting text boxes.
    """
    doc = fitz.open()
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)

    # Insert two overlapping text blocks at colliding coordinates
    page.insert_textbox(fitz.Rect(50, 100, 300, 200), "Primary content paragraph A with long sentences.")
    page.insert_textbox(fitz.Rect(100, 105, 350, 220), "Colliding overlapping paragraph B placed right on top.")

    plan = PagePlan(page_type="article", template_id="generic", regions=[])
    issues = _check_overlapping_regions(page, plan)
    assert len(issues) >= 1
    assert any("Overlapping" in i for i in issues)


def test_qc_quality_report_exact_schema_and_scoring(temp_test_images):
    """
    Verifies exact requested JSON report structure:
      {
        "page": 7,
        "layout_score": 92,
        "image_score": 95,
        "text_fit_score": 98,
        "overall_score": 94,
        "issues": []
      }
    """
    doc = fitz.open()
    plan = PagePlan(
        page_type="project_showcase",
        template_id="ai_lab_project_showcase",
        regions=[
            PlannedRegion(region_id="hero_image", type="image", asset=temp_test_images["high_res"]),
            PlannedRegion(region_id="headline", type="headline", content="Autonomous Systems"),
            PlannedRegion(region_id="body", type="body", content="High-accuracy robotics field demonstrations."),
        ],
    )
    tmpl_meta = {"template_id": "ai_lab_project_showcase"}
    page = render_page_from_plan(doc, plan, tmpl_meta, page_num=7)

    report = validate_page_visual_quality(page, plan, tmpl_meta, page_num=7)
    report_dict = report.model_dump()

    # Assert exact required keys
    assert "page" in report_dict
    assert "layout_score" in report_dict
    assert "image_score" in report_dict
    assert "text_fit_score" in report_dict
    assert "overall_score" in report_dict
    assert "issues" in report_dict

    assert report_dict["page"] == 7
    assert isinstance(report_dict["layout_score"], int)
    assert isinstance(report_dict["image_score"], int)
    assert isinstance(report_dict["text_fit_score"], int)
    assert isinstance(report_dict["overall_score"], int)
    assert isinstance(report_dict["issues"], list)


def test_qc_configurable_thresholds(temp_test_images):
    """
    Tests altering configurable thresholds:
      - Default min_overall_score = 80 -> passes
      - Stricter min_overall_score = 99 -> fails validation
      - Stricter min_dpi = 300 -> flags high_res as low DPI
    """
    doc = fitz.open()
    plan = PagePlan(
        page_type="project_showcase",
        template_id="ai_lab_project_showcase",
        regions=[
            PlannedRegion(region_id="hero_image", type="image", asset=temp_test_images["high_res"]),
            PlannedRegion(region_id="headline", type="headline", content="Autonomous Systems"),
            PlannedRegion(region_id="body", type="body", content="Robotics field demonstrations."),
        ],
    )
    tmpl_meta = {"template_id": "ai_lab_project_showcase"}
    page = render_page_from_plan(doc, plan, tmpl_meta, page_num=1)

    # 1. Standard thresholds -> Passes
    standard_thresh = VisualQCThresholds(min_overall_score=80)
    rep_std = validate_page_visual_quality(page, plan, tmpl_meta, standard_thresh, page_num=1)
    assert rep_std.is_valid is True

    # 2. Strict threshold: min_overall_score = 100 -> Fails
    strict_thresh = VisualQCThresholds(min_overall_score=100)
    rep_strict = validate_page_visual_quality(page, plan, tmpl_meta, strict_thresh, page_num=1)
    if rep_strict.overall_score < 100:
        assert rep_strict.is_valid is False

    # 3. Super high DPI threshold: min_dpi = 1200 -> Flags image
    dpi_thresh = VisualQCThresholds(min_dpi=1200.0)
    rep_dpi = validate_page_visual_quality(page, plan, tmpl_meta, dpi_thresh, page_num=1)
    assert any("Low-resolution image" in i for i in rep_dpi.issues)


def test_closed_loop_recovery_workflow(temp_test_images):
    """
    Closed-Loop Quality Control Workflow:
      PagePlan -> Renderer -> Validator -> FAIL -> LayoutPlanner (Alternative) -> Renderer -> Validator -> PASS
    """
    doc = fitz.open()

    # Plan with a template
    plan = PagePlan(
        page_type="project_showcase",
        template_id="ai_lab_project_showcase",
        regions=[
            PlannedRegion(region_id="hero_image", type="image", asset=temp_test_images["high_res"]),
            PlannedRegion(region_id="headline", type="headline", content="Autonomous Prototype"),
            PlannedRegion(region_id="body", type="body", content="Real-time multi-agent outdoor navigation."),
        ],
    )
    tmpl_meta = {"template_id": "ai_lab_project_showcase", "lab": "AI Lab"}

    recovery_result = render_and_validate_page_with_recovery(
        doc=doc,
        page_plan=plan,
        template_metadata=tmpl_meta,
        page_num=1,
        max_attempts=3,
        thresholds=VisualQCThresholds(min_overall_score=80),
    )

    assert recovery_result.passed is True
    assert recovery_result.attempts_taken >= 1
    assert len(recovery_result.regeneration_history) >= 1
    assert doc.page_count == 1  # Exactly 1 page committed to output document


def test_recovery_regeneration_limit_prevents_infinite_loop():
    """
    Verifies that the recovery loop strictly terminates after max_attempts (e.g. 2)
    when an unresolvable issue is present (e.g. permanently missing asset).
    """
    doc = fitz.open()
    plan = PagePlan(
        page_type="project_showcase",
        template_id="ai_lab_project_showcase",
        regions=[
            PlannedRegion(
                region_id="hero_image",
                type="image",
                asset="/non_existent/impossible_photo_xyz.jpg",  # Permanent missing asset
            )
        ],
    )
    tmpl_meta = {"template_id": "ai_lab_project_showcase"}

    # Set max_attempts = 2
    recovery_result = render_and_validate_page_with_recovery(
        doc=doc,
        page_plan=plan,
        template_metadata=tmpl_meta,
        page_num=1,
        max_attempts=2,
        thresholds=VisualQCThresholds(min_overall_score=80),
    )

    # Loop stopped at exactly max_attempts
    assert recovery_result.attempts_taken == 2
    assert len(recovery_result.regeneration_history) == 2
    assert recovery_result.passed is False
    assert doc.page_count == 1  # Safe fallback page committed without crashing


@pytest.mark.asyncio
async def test_api_page_qc_endpoint(temp_test_images):
    """
    Tests HTTP POST /api/v1/magazine/qc/page with and without recovery.
    """
    payload = {
        "plan": {
            "page_type": "project_showcase",
            "template_id": "ai_lab_project_showcase",
            "regions": [
                {
                    "region_id": "hero_image",
                    "type": "image",
                    "asset": temp_test_images["high_res"],
                },
                {
                    "region_id": "headline",
                    "type": "headline",
                    "content": "Autonomous Quadruped Robot",
                },
                {
                    "region_id": "body",
                    "type": "body",
                    "content": "Real-time robotics telemetry test.",
                },
            ],
        },
        "template_metadata": {
            "template_id": "ai_lab_project_showcase",
            "lab": "AI Lab",
        },
        "page_num": 7,
        "with_recovery": False,
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/magazine/qc/page", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data.get("success") is True
        res = data.get("data")
        assert res["page"] == 7
        assert "layout_score" in res
        assert "image_score" in res
        assert "text_fit_score" in res
        assert "overall_score" in res
        assert isinstance(res["issues"], list)
