"""Comprehensive Test Suite for Phase 4: MAGAZINE LAYOUT PLANNER."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.magazine.layout_planner import (
    _count_words,
    _truncate_to_word_limit,
    page_plan_to_magazine_data,
    plan_page_layout,
    resolve_template,
    validate_page_plan,
)
from app.modules.magazine.schemas import (
    PagePlan,
    PlannedRegion,
)
from app.modules.magazine.template_schema import (
    TemplateMetadata,
    TemplateRegionDefinition,
    default_regions_for_page_type,
)


@pytest.fixture
def sample_article():
    return {
        "title": "Students Build an Autonomous Robot",
        "headline": "Students Build an Autonomous Robot",
        "description": "Engineering students demonstrate a multi-terrain quadruped prototype at the national robotics hackathon.",
        "writeup": (
            "Undergraduate engineering students designed, fabricated, and field-tested an autonomous "
            "quadruped robotics platform capable of traversing unstructured terrains and transmitting "
            "telemetry in real time. The project incorporates custom lidar sensors and custom motor controllers."
        ),
        "caption": "Students demonstrating the prototype.",
        "section": "Projects",
    }


@pytest.fixture
def sample_photos():
    return [
        {
            "id": "photo_17.jpg",
            "filename": "photo_17.jpg",
            "url": "uploads/magazine/photo_17.jpg",
            "aspect_ratio": 1.50,
            "orientation": "landscape",
            "caption": "Students demonstrating the prototype.",
        },
        {
            "id": "photo_21.jpg",
            "filename": "photo_21.jpg",
            "url": "uploads/magazine/photo_21.jpg",
            "aspect_ratio": 1.77,
            "orientation": "landscape",
            "caption": "Sensor telemetry calibration.",
        },
    ]


# ============================================================================
# 1. Deterministic Page Plan Generation (Prompt Example)
# ============================================================================

@pytest.mark.asyncio
async def test_deterministic_page_plan_generation_exact_example(sample_article, sample_photos):
    """
    Validates the prompt's exact target example:
    {
      "page_type": "project_showcase",
      "template_id": "AI_LAB_03",
      "regions": [
        {"region_id": "hero_image", "type": "image", "asset": "photo_17.jpg"},
        {"region_id": "headline", "type": "headline", "content": "Students Build an Autonomous Robot"},
        {"region_id": "body", "type": "body", "content": "..."},
        {"region_id": "caption", "type": "caption", "content": "Students demonstrating the prototype."}
      ]
    }
    """
    plan, validation = await plan_page_layout(
        content=sample_article,
        department_or_lab="AI Lab",
        selected_template="AI_LAB_03",
        available_images=sample_photos,
        use_llm=False,  # deterministic heuristic path
    )

    assert plan.page_type == "project_showcase"
    assert "ai_lab" in plan.template_id.lower() or plan.template_id == "AI_LAB_03"
    assert len(plan.regions) >= 4

    region_map = {r.region_id: r for r in plan.regions}
    assert "hero_image" in region_map
    assert "headline" in region_map
    assert "body" in region_map
    assert "caption" in region_map

    # Check types and values
    assert region_map["hero_image"].type == "image"
    assert region_map["hero_image"].asset == "photo_17.jpg"

    assert region_map["headline"].type == "headline"
    assert region_map["headline"].content == "Students Build an Autonomous Robot"

    assert region_map["body"].type == "body"
    assert "quadruped robotics platform" in region_map["body"].content

    assert region_map["caption"].type == "caption"
    assert "Students demonstrating the prototype." in region_map["caption"].content

    # Strict backend validation passes
    assert validation.is_valid is True
    assert len(validation.violations) == 0


# ============================================================================
# 2. Region Existence Validation
# ============================================================================

def test_validate_region_existence():
    """Verifies rejection of unknown/undeclared regions not in template."""
    tmpl = TemplateMetadata(
        template_id="TEST_TMPL",
        name="Test Template",
        page_type="project_showcase",
        regions=[
            TemplateRegionDefinition(region_id="headline", type="headline", required=True),
            TemplateRegionDefinition(region_id="body", type="body", required=True),
        ],
    )

    # Valid plan
    valid_plan = PagePlan(
        page_type="project_showcase",
        template_id="TEST_TMPL",
        regions=[
            PlannedRegion(region_id="headline", type="headline", content="Valid Title"),
            PlannedRegion(region_id="body", type="body", content="Valid Body"),
        ],
    )
    report_valid = validate_page_plan(valid_plan, tmpl)
    assert report_valid.is_valid is True

    # Plan with rogue region
    invalid_plan = PagePlan(
        page_type="project_showcase",
        template_id="TEST_TMPL",
        regions=[
            PlannedRegion(region_id="headline", type="headline", content="Valid Title"),
            PlannedRegion(region_id="body", type="body", content="Valid Body"),
            PlannedRegion(region_id="unauthorized_sidebar_ad", type="body", content="Spam"),
        ],
    )
    report_invalid = validate_page_plan(invalid_plan, tmpl)
    assert report_invalid.is_valid is False
    assert any("Unknown region 'unauthorized_sidebar_ad'" in v for v in report_invalid.violations)


# ============================================================================
# 3. Maximum Text Length Validation & Auto-Correction
# ============================================================================

def test_validate_maximum_text_length():
    """Verifies that text regions exceeding word capacity are flagged."""
    tmpl = TemplateMetadata(
        template_id="TEST_LIMITS",
        name="Test Limits",
        page_type="article",
        regions=[
            TemplateRegionDefinition(region_id="headline", type="headline", required=True, max_words=10),
            TemplateRegionDefinition(region_id="body", type="body", required=True, max_words=25),
        ],
    )

    # Long body text (40 words)
    long_body = " ".join(["word"] * 40)
    overflow_plan = PagePlan(
        page_type="article",
        template_id="TEST_LIMITS",
        regions=[
            PlannedRegion(region_id="headline", type="headline", content="Short Title"),
            PlannedRegion(region_id="body", type="body", content=long_body),
        ],
    )

    report = validate_page_plan(overflow_plan, tmpl, strict=True)
    assert report.is_valid is False
    assert any("exceeds maximum word limit (40 words > max 25)" in v for v in report.violations)

    # Truncation helper test
    truncated = _truncate_to_word_limit(long_body, 25)
    assert _count_words(truncated) == 25


# ============================================================================
# 4. Image Count Constraints Validation
# ============================================================================

def test_validate_image_count_constraints():
    """Verifies that templates requiring specific min/max image counts are strictly enforced."""
    tmpl = TemplateMetadata(
        template_id="MULTI_IMAGE_TMPL",
        name="Multi Image Template",
        page_type="project_showcase",
        regions=[
            TemplateRegionDefinition(region_id="hero_image", type="image", required=True),
            TemplateRegionDefinition(region_id="detail_image", type="image", required=True),
            TemplateRegionDefinition(region_id="headline", type="headline", required=True),
            TemplateRegionDefinition(region_id="body", type="body", required=True),
        ],
        layout_constraints={"min_images": 2, "max_images": 3},
    )

    # Plan with only 1 image when 2 are required
    sparse_plan = PagePlan(
        page_type="project_showcase",
        template_id="MULTI_IMAGE_TMPL",
        regions=[
            PlannedRegion(region_id="hero_image", type="image", asset="photo_1.jpg"),
            PlannedRegion(region_id="detail_image", type="image", asset=None),
            PlannedRegion(region_id="headline", type="headline", content="Title"),
            PlannedRegion(region_id="body", type="body", content="Body"),
        ],
    )

    report = validate_page_plan(sparse_plan, tmpl)
    assert report.is_valid is False
    assert any("Insufficient images: template requires at least 2" in v for v in report.violations)


# ============================================================================
# 5. Image Aspect Ratio Validation
# ============================================================================

def test_validate_image_aspect_ratio():
    """Verifies that images violating target aspect ratio tolerance are rejected."""
    tmpl = TemplateMetadata(
        template_id="HERO_LANDSCAPE_TMPL",
        name="Hero Landscape",
        page_type="project_showcase",
        regions=[
            TemplateRegionDefinition(
                region_id="hero_image",
                type="image",
                required=True,
                target_aspect_ratio=1.60,  # 16:10 wide landscape
                tolerance=0.20,             # Acceptable: 1.40 to 1.80
            ),
            TemplateRegionDefinition(region_id="headline", type="headline", required=True),
            TemplateRegionDefinition(region_id="body", type="body", required=True),
        ],
    )

    photos = [
        {"id": "tall_portrait.jpg", "aspect_ratio": 0.67},   # Portrait (ratio 0.67)
        {"id": "wide_landscape.jpg", "aspect_ratio": 1.60},  # Matching landscape (ratio 1.60)
    ]

    # Assigning tall portrait to landscape hero
    bad_ratio_plan = PagePlan(
        page_type="project_showcase",
        template_id="HERO_LANDSCAPE_TMPL",
        regions=[
            PlannedRegion(region_id="hero_image", type="image", asset="tall_portrait.jpg"),
            PlannedRegion(region_id="headline", type="headline", content="Title"),
            PlannedRegion(region_id="body", type="body", content="Body"),
        ],
    )
    report = validate_page_plan(bad_ratio_plan, tmpl, available_images=photos)
    assert report.is_valid is False
    assert any("violates region 'hero_image' target ratio 1.60" in v for v in report.violations)

    # Assigning correct landscape photo
    good_ratio_plan = PagePlan(
        page_type="project_showcase",
        template_id="HERO_LANDSCAPE_TMPL",
        regions=[
            PlannedRegion(region_id="hero_image", type="image", asset="wide_landscape.jpg"),
            PlannedRegion(region_id="headline", type="headline", content="Title"),
            PlannedRegion(region_id="body", type="body", content="Body"),
        ],
    )
    report_good = validate_page_plan(good_ratio_plan, tmpl, available_images=photos)
    assert report_good.is_valid is True


# ============================================================================
# 6. Required Regions Validation
# ============================================================================

def test_validate_required_regions():
    """Verifies that missing or unpopulated required regions are caught."""
    tmpl = TemplateMetadata(
        template_id="STRICT_TMPL",
        name="Strict Template",
        page_type="article",
        regions=[
            TemplateRegionDefinition(region_id="headline", type="headline", required=True),
            TemplateRegionDefinition(region_id="body", type="body", required=True),
            TemplateRegionDefinition(region_id="hero_image", type="image", required=True),
            TemplateRegionDefinition(region_id="caption", type="caption", required=False),
        ],
    )

    # Missing headline entirely
    missing_plan = PagePlan(
        page_type="article",
        template_id="STRICT_TMPL",
        regions=[
            PlannedRegion(region_id="body", type="body", content="Some text"),
            PlannedRegion(region_id="hero_image", type="image", asset="img.jpg"),
        ],
    )
    report = validate_page_plan(missing_plan, tmpl)
    assert report.is_valid is False
    assert any("Missing required region 'headline'" in v for v in report.violations)


# ============================================================================
# 7. Clean Service Boundary: PagePlan -> Renderer Data Adapter
# ============================================================================

def test_clean_service_boundary_renderer_adapter():
    """Verifies that PagePlan cleanly translates into renderer input without semantic renderer choices."""
    plan = PagePlan(
        page_type="project_showcase",
        template_id="AI_LAB_03",
        regions=[
            PlannedRegion(region_id="hero_image", type="image", asset="photo_17.jpg", caption="Test caption"),
            PlannedRegion(region_id="headline", type="headline", content="Students Build an Autonomous Robot"),
            PlannedRegion(region_id="body", type="body", content="Full writeup body text."),
            PlannedRegion(region_id="caption", type="caption", content="Test caption"),
        ],
    )

    renderer_data = page_plan_to_magazine_data(plan)

    assert renderer_data["writeup_headline"] == "Students Build an Autonomous Robot"
    assert renderer_data["writeup_text"] == "Full writeup body text."
    assert len(renderer_data["cover_pages"]) == 1
    assert renderer_data["cover_pages"][0]["url"] == "photo_17.jpg"
    assert renderer_data["layout_plan"]["page_type"] == "project_showcase"
    assert renderer_data["layout_plan"]["template_id"] == "AI_LAB_03"


# ============================================================================
# 8. REST API Endpoint (/api/v1/magazine/layout/plan)
# ============================================================================

@pytest.mark.asyncio
async def test_api_layout_plan_endpoint(sample_article, sample_photos):
    """Verifies the HTTP POST /api/v1/magazine/layout/plan API endpoint."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        payload = {
            "content": sample_article,
            "department_or_lab": "AI Lab",
            "selected_template": "AI_LAB_03",
            "available_images": sample_photos,
            "use_llm": False,
        }

        resp = await client.post("/api/v1/magazine/layout/plan", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        data = resp.json()
        assert data["success"] is True
        result = data["data"]

        plan = result["plan"]
        validation = result["validation"]

        assert plan["page_type"] == "project_showcase"
        assert len(plan["regions"]) >= 4
        assert validation["is_valid"] is True
        assert len(validation["violations"]) == 0
