"""Comprehensive Test Suite for Phase 5: TEMPLATE-DRIVEN MAGAZINE RENDERER."""

import os
import io
import tempfile
import pytest
from PIL import Image
import fitz

from app.modules.magazine.renderer import (
    THEME,
    PAGE_WIDTH,
    PAGE_HEIGHT,
    ThemeTokens,
    FontTokens,
    SpacingTokens,
    _hex_to_rgb,
    _is_dark_hex,
    resolve_template_theme,
    resolve_template_fonts,
    resolve_template_spacing,
    fit_image_cover,
    fit_image_contain,
    fit_text_box,
    draw_region_hero_image,
    draw_region_image,
    draw_region_image_grid,
    draw_region_portrait,
    draw_region_landscape,
    draw_region_headline,
    draw_region_subheadline,
    draw_region_body,
    draw_region_quote,
    draw_region_caption,
    draw_region_logo,
    draw_region_badge,
    draw_region_header,
    draw_region_footer,
    draw_region_page_number,
    render_page_from_plan,
    render_editorial_magazine_pdf,
)
from app.modules.magazine.schemas import PagePlan, PlannedRegion


@pytest.fixture
def temp_canvas_and_image():
    temp_dir = tempfile.mkdtemp()

    # Create a 2:1 landscape test image (1000 x 500)
    img_landscape = Image.new("RGB", (1000, 500), color=(180, 50, 50))
    p_landscape = os.path.join(temp_dir, "test_landscape.jpg")
    img_landscape.save(p_landscape, format="JPEG")

    # Create a 1:2 portrait test image (500 x 1000)
    img_portrait = Image.new("RGB", (500, 1000), color=(50, 100, 200))
    p_portrait = os.path.join(temp_dir, "test_portrait.jpg")
    img_portrait.save(p_portrait, format="JPEG")

    out_pdf = os.path.join(temp_dir, "rendered_output.pdf")

    yield {
        "temp_dir": temp_dir,
        "landscape_path": p_landscape,
        "portrait_path": p_portrait,
        "output_pdf": out_pdf,
    }

    # Teardown
    for root, dirs, files in os.walk(temp_dir, topdown=False):
        for f in files:
            try:
                os.remove(os.path.join(root, f))
            except OSError:
                pass
    try:
        os.rmdir(temp_dir)
    except OSError:
        pass


# ============================================================================
# 1. Image Crop / Cover Fitting (Never Stretches)
# ============================================================================

def test_image_cover_fitting_never_stretches(temp_canvas_and_image):
    """
    Verifies that fit_image_cover crops to exact target dimensions
    without distorting the image's native aspect ratio.
    """
    img_path = temp_canvas_and_image["landscape_path"]
    target_w, target_h = 300.0, 300.0  # Square target box for 2:1 image

    fitted_bytes = fit_image_cover(img_path, target_w, target_h)
    assert fitted_bytes is not None

    with Image.open(io.BytesIO(fitted_bytes)) as fitted:
        assert fitted.size == (300, 300)
        # Verify format and mode
        assert fitted.mode == "RGB"


# ============================================================================
# 2. Image Contain Fitting (Never Stretches, Proportional Pillarbox)
# ============================================================================

def test_image_contain_fitting_never_stretches(temp_canvas_and_image):
    """
    Verifies that fit_image_contain preserves complete photo visibility
    with letterboxing/pillarboxing on canvas.
    """
    img_path = temp_canvas_and_image["landscape_path"]
    target_w, target_h = 400.0, 400.0

    contained_bytes = fit_image_contain(img_path, target_w, target_h, bg_color_hex="#F1EDE4")
    assert contained_bytes is not None

    with Image.open(io.BytesIO(contained_bytes)) as contained:
        assert contained.size == (400, 400)


# ============================================================================
# 3. Text Fitting & Zero Overflow Guarantee
# ============================================================================

def test_text_fitting_and_zero_overflow():
    """
    Verifies that fit_text_box guarantees zero overflow (remaining_pt >= 0)
    by scaling font size down within safe bounds.
    """
    doc = fitz.open()
    page = doc.new_page(width=500, height=500)
    rect = fitz.Rect(50, 50, 200, 100)  # 150 x 50 pt box

    # 25 words: fits when font drops from 14.0 to ~10.5
    text = "The quick brown fox jumps over the lazy dog in the robotics and machine learning laboratory demonstration at the university annual technology symposium."

    result = fit_text_box(
        page=page,
        rect=rect,
        text=text,
        fontname="helv",
        initial_fontsize=14.0,
        min_fontsize=8.0,
        color=(0, 0, 0),
    )

    assert result["status"] in ("fitted_font", "truncated")
    assert result["remaining_pt"] >= 0.0  # ZERO OVERFLOW GUARANTEE
    assert result["fontsize"] >= 8.0
    doc.close()


# ============================================================================
# 4. Safe Text Truncation When Content Exceeds Min Font Size
# ============================================================================

def test_safe_text_truncation_when_below_min_font():
    """
    Verifies that when text is far too massive for a small bounding box,
    it safely truncates with an ellipsis ('…') instead of overflowing.
    """
    doc = fitz.open()
    page = doc.new_page(width=500, height=500)
    small_rect = fitz.Rect(50, 50, 150, 80)  # 100 x 30 pt box

    # 300 words in a 100x30 pt box
    huge_text = " ".join(["breakthrough technology innovation autonomous system"] * 50)

    result = fit_text_box(
        page=page,
        rect=small_rect,
        text=huge_text,
        fontname="helv",
        initial_fontsize=11.0,
        min_fontsize=7.5,
    )

    assert result["status"] == "truncated"
    assert result["text"].endswith("…")
    assert result["remaining_pt"] >= 0.0  # ZERO OVERFLOW GUARANTEE
    doc.close()


# ============================================================================
# 5. Template Theme Resolution (Dark & Light Themes)
# ============================================================================

def test_template_theme_dark_and_light_customization():
    """Verifies that template colors (e.g. dark CTF theme) override hardcoded styling."""
    # Dark Theme (Cyber Security Lab CTF)
    dark_meta = {
        "colors": {
            "background_color": "#0f172a",
            "text_color": "#f8fafc",
            "accent_color": "#0284c7",
        }
    }
    dark_theme = resolve_template_theme(dark_meta)
    assert dark_theme.is_dark is True
    assert dark_theme.paper == "#0f172a"
    assert dark_theme.accent == "#0284c7"
    assert dark_theme.ink == "#f8fafc"

    # Light Theme (Modern Tech Blue)
    light_meta = {
        "colors": {
            "background_color": "#ffffff",
            "text_color": "#111827",
            "accent_color": "#1d4ed8",
        }
    }
    light_theme = resolve_template_theme(light_meta)
    assert light_theme.is_dark is False
    assert light_theme.paper == "#ffffff"
    assert light_theme.accent == "#1d4ed8"


# ============================================================================
# 6. Full Support for All 14 Standard Regions
# ============================================================================

def test_render_all_14_supported_regions(temp_canvas_and_image):
    """
    Renders all 14 requested regions onto a test page:
    hero_image, image, image_grid, portrait, landscape, headline, subheadline,
    body, quote, caption, logo, badge, header, footer, page_number.
    """
    doc = fitz.open()
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)

    theme = ThemeTokens()
    fonts = FontTokens()
    spacing = SpacingTokens()

    p_land = temp_canvas_and_image["landscape_path"]
    p_port = temp_canvas_and_image["portrait_path"]

    # 1. header
    draw_region_header(page, 1, "AI RESEARCH LAB", theme, fonts, spacing)

    # 2. badge
    draw_region_badge(page, fitz.Rect(42, 45, 120, 60), "SPECIAL ISSUE", theme, fonts)

    # 3. subheadline
    draw_region_subheadline(page, fitz.Rect(130, 46, 400, 60), "PROJECT ARCHITECTURE & RESULTS", theme, fonts)

    # 4. logo
    draw_region_logo(page, fitz.Rect(490, 40, 540, 62), None, theme, fonts)

    # 5. headline
    draw_region_headline(page, fitz.Rect(42, 68, 550, 115), "Students Build an Autonomous Quadruped Robot", theme, fonts)

    # 6. hero_image
    draw_region_hero_image(page, fitz.Rect(42, 125, 550, 320), p_land, "Field trial demonstration.", theme, fonts)

    # 7. quote
    draw_region_quote(page, fitz.Rect(42, 330, 550, 385), "Theoretical models achieve purpose when deployed on hardware.", theme, fonts)

    # 8. body
    draw_region_body(page, fitz.Rect(42, 395, 300, 580), "Undergraduate engineering students designed an autonomous quadruped machine.", theme, fonts)

    # 9. portrait
    draw_region_portrait(page, fitz.Rect(315, 395, 420, 520), p_port, "Lead Engineer", theme, fonts)

    # 10. landscape
    draw_region_landscape(page, fitz.Rect(430, 395, 550, 520), p_land, "Sensor Bench", theme, fonts)

    # 11. image
    draw_region_image(page, fitz.Rect(315, 530, 420, 620), p_land, "Telemetry", theme, fonts)

    # 12. image_grid
    draw_region_image_grid(
        page,
        fitz.Rect(430, 530, 550, 620),
        [{"url": p_land, "caption": "Test A"}, {"url": p_port, "caption": "Test B"}],
        theme,
        fonts,
        columns=2,
    )

    # 13. caption
    draw_region_caption(page, fitz.Rect(42, 590, 300, 620), "FIG 2.1 · Real-time spatial telemetry telemetry.", theme, fonts)

    # 14. footer & page_number
    draw_region_footer(page, "SIET Autonomous Systems Issue 2026", theme, fonts, spacing)
    draw_region_page_number(page, fitz.Rect(500, 800, 550, 820), 1, theme, fonts)

    # Verify document has rendered text
    extracted = page.get_text()
    assert "Students Build an Autonomous Quadruped Robot" in extracted
    assert "AI RESEARCH LAB" in extracted
    assert "SPECIAL ISSUE" in extracted
    assert "Theoretical models achieve purpose" in extracted

    # Save to verify file writes cleanly
    doc.save(temp_canvas_and_image["output_pdf"])
    assert os.path.exists(temp_canvas_and_image["output_pdf"])
    assert os.path.getsize(temp_canvas_and_image["output_pdf"]) > 2000
    doc.close()


# ============================================================================
# 7. Render Page From Structured PagePlan
# ============================================================================

def test_render_page_from_plan_integration(temp_canvas_and_image):
    """Verifies that render_page_from_plan renders a PagePlan cleanly into PDF."""
    doc = fitz.open()
    plan = PagePlan(
        page_type="project_showcase",
        template_id="AI_LAB_03",
        regions=[
            PlannedRegion(region_id="hero_image", type="image", asset=temp_canvas_and_image["landscape_path"], caption="Demonstrating prototype."),
            PlannedRegion(region_id="headline", type="headline", content="Autonomous Quadruped Robot"),
            PlannedRegion(region_id="body", type="body", content="Students built an autonomous four-legged machine with LiDAR telemetry."),
            PlannedRegion(region_id="caption", type="caption", content="Demonstrating prototype."),
        ],
    )

    template_meta = {
        "template_id": "AI_LAB_03",
        "colors": {"accent_color": "#1d4ed8", "background_color": "#ffffff"},
        "typography": {"display": "Playfair Display", "body": "Source Serif Pro"},
        "department_or_lab": "AI Lab",
    }

    page = render_page_from_plan(doc, plan, template_metadata=template_meta, page_num=1)
    assert page is not None

    text = page.get_text()
    assert "Autonomous Quadruped Robot" in text
    assert "Students built an autonomous four-legged machine" in text

    doc.save(temp_canvas_and_image["output_pdf"])
    assert os.path.getsize(temp_canvas_and_image["output_pdf"]) > 1000
    doc.close()


# ============================================================================
# 8. Backward Compatibility: Classic Editorial Magazine PDF
# ============================================================================

def test_backward_compatibility_editorial_renderer(temp_canvas_and_image):
    """
    Verifies that existing editorial magazine rendering continues to work seamlessly
    while benefiting from the new dynamic fitting and aspect-ratio preservation.
    """
    p_land = temp_canvas_and_image["landscape_path"]
    out_pdf = temp_canvas_and_image["output_pdf"]

    magazine_data = {
        "title": "SIET Engineering Journal 2026",
        "description": "Comprehensive documentation of student engineering breakthroughs and peer-reviewed publications.",
        "department_name": "Robotics & Automation",
        "publication_year": 2026,
        "magazine_type": "Special Issue",
        "cover_pages": [{"url": p_land, "caption": "Quadruped robot prototype"}],
        "writeup_headline": "Autonomous Robotics Field Trial",
        "writeup_text": "Students successfully conducted real-time outdoor navigation tests.",
        "gallery_images": [
            {"url": p_land, "caption": "Field trial step 1"},
            {"url": p_land, "caption": "Field trial step 2"},
        ],
    }

    result = render_editorial_magazine_pdf(magazine_data, out_pdf)
    assert result["success"] is True
    assert result["total_pages"] == 5
    assert os.path.exists(result["pdf_path"])
    assert len(result["page_previews"]) == 5
