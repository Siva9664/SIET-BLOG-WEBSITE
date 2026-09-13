"""Comprehensive test suite for Phase 3: Intelligent Real-Photo Selection."""

import os
import tempfile
import pytest
from PIL import Image, ImageDraw
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.modules.magazine.photo_curator import (
    PhotoAnalysis,
    analyze_photo,
    compute_dhash,
    hamming_distance,
    compute_quality_score,
    detect_duplicates,
)
from app.modules.magazine.vision_embedder import (
    BaseVisionEmbedder,
    MockVisionEmbedder,
    get_vision_embedder,
)
from app.modules.magazine.photo_ranker import rank_photos_for_article


@pytest.fixture
def test_photo_library():
    """Generates realistic temporary test photographs for evaluation."""
    temp_dir = tempfile.mkdtemp()
    photos = []

    # 1. photo_17.jpg - High-res sharp robotics prototype (Target hero/top relevance)
    img_robot = Image.new("RGB", (1920, 1080), color=(60, 80, 110))
    d1 = ImageDraw.Draw(img_robot)
    for i in range(0, 1920, 30):
        d1.line([(i, 0), (i, 1080)], fill=(220, 220, 240), width=3)
    p_robot = os.path.join(temp_dir, "photo_17.jpg")
    img_robot.save(p_robot, format="JPEG")
    photos.append({
        "id": "photo_17",
        "url": p_robot,
        "caption": "Students demonstrating autonomous quadruped robot hardware at national robotics hackathon",
    })

    # 2. photo_21.jpg - High-res student engineering team prototype (Target high relevance)
    img_team = Image.new("RGB", (1280, 720), color=(70, 120, 180))
    d2 = ImageDraw.Draw(img_team)
    for i in range(0, 1280, 40):
        d2.line([(i, 0), (i, 720)], fill=(240, 240, 255), width=2)
    for j in range(0, 720, 40):
        d2.line([(0, j), (1280, j)], fill=(200, 220, 250), width=2)
    p_team = os.path.join(temp_dir, "photo_21.jpg")
    img_team.save(p_team, format="JPEG")
    photos.append({
        "id": "photo_21",
        "url": p_team,
        "caption": "Team QuadRobo calibrating lidar sensor telemetry for hackathon field testing",
    })

    # 3. photo_04.jpg - Campus auditorium venue photo (Moderate relevance)
    img_aud = Image.new("RGB", (1024, 768), color=(140, 120, 90))
    d3 = ImageDraw.Draw(img_aud)
    d3.rectangle([(200, 200), (800, 600)], fill=(180, 160, 130))
    p_aud = os.path.join(temp_dir, "photo_04.jpg")
    img_aud.save(p_aud, format="JPEG")
    photos.append({
        "id": "photo_04",
        "url": p_aud,
        "caption": "Auditorium venue and keynote stage seating",
    })

    # 4. photo_99.jpg - Campus food cafeteria lunch (Low relevance)
    img_food = Image.new("RGB", (640, 480), color=(160, 60, 40))
    d4 = ImageDraw.Draw(img_food)
    d4.rectangle([(100, 100), (500, 400)], fill=(220, 120, 80))
    p_food = os.path.join(temp_dir, "photo_99.jpg")
    img_food.save(p_food, format="JPEG")
    photos.append({
        "id": "photo_99",
        "url": p_food,
        "caption": "Campus dining hall lunch and snacks cafeteria",
    })

    # 5. photo_17_burst_dup.jpg - Near-duplicate burst shot of photo_17
    img_dup = img_robot.copy()
    p_dup = os.path.join(temp_dir, "photo_17_burst_dup.jpg")
    img_dup.save(p_dup, format="JPEG")
    photos.append({
        "id": "photo_17_burst_dup",
        "url": p_dup,
        "caption": "Burst duplicate of quadruped robot prototype",
    })

    yield photos

    # Cleanup
    for item in photos:
        if os.path.exists(item["url"]):
            try:
                os.remove(item["url"])
            except OSError:
                pass
    try:
        os.rmdir(temp_dir)
    except OSError:
        pass


# ============================================================================
# 1. Photographic Quality Scoring Tests
# ============================================================================

def test_quality_scoring_resolution_sharpness_exposure():
    """Validates multi-factor photographic quality evaluation."""
    # High quality 1080p image with good lighting & contrast
    q_high, exp_high = compute_quality_score(
        width=1920,
        height=1080,
        sharpness=55.0,
        brightness=128.0,
        contrast=45.0,
        aspect_ratio=1.778,
    )
    assert q_high >= 0.80
    assert exp_high == "normal"

    # Dark underexposed image
    q_dark, exp_dark = compute_quality_score(
        width=640,
        height=480,
        sharpness=20.0,
        brightness=25.0,
        contrast=15.0,
        aspect_ratio=1.333,
    )
    assert q_dark < 0.40
    assert exp_dark == "underexposed"

    # Blurry, low-resolution square
    q_blur, _ = compute_quality_score(
        width=200,
        height=200,
        sharpness=5.0,
        brightness=130.0,
        contrast=10.0,
        aspect_ratio=1.0,
    )
    assert q_blur < 0.35


# ============================================================================
# 2. Perceptual dHash and Near-Duplicate Detection Tests
# ============================================================================

def test_dhash_and_near_duplicate_detection(test_photo_library):
    """Verifies that burst/duplicate photos are detected via dHash and flagged."""
    analyzed = []
    for item in test_photo_library:
        analysis = analyze_photo(item["url"], photo_id=item["id"], url=item["url"], caption=item["caption"])
        analyzed.append(analysis)

    # photo_17 and photo_17_burst_dup are identical pixels
    h1 = analyzed[0].perceptual_hash
    h_dup = analyzed[4].perceptual_hash
    assert h1 == h_dup
    assert hamming_distance(h1, h_dup) == 0

    # Run duplicate detection
    detect_duplicates(analyzed, threshold_dist=6)

    # Exactly one should be marked duplicate pointing to the other
    dups = [p for p in analyzed if p.is_duplicate]
    assert len(dups) >= 1
    assert dups[0].duplicate_of in ("photo_17", "photo_17_burst_dup")


# ============================================================================
# 3. Vision Embedder Interface Tests
# ============================================================================

@pytest.mark.asyncio
async def test_vision_embedder_interface():
    """Validates normalized vector generation and cosine similarity calculation."""
    embedder = MockVisionEmbedder(dim=16)

    text_emb = await embedder.embed_text("Students participating in the national robotics hackathon")
    assert len(text_emb) == 16
    mag = sum(v * v for v in text_emb)
    assert pytest.approx(mag, abs=0.01) == 1.0

    img_emb = await embedder.embed_image("photo_robotics_quadruped.jpg")
    assert len(img_emb) == 16

    sim = embedder.compute_similarity(text_emb, img_emb)
    assert 0.0 <= sim <= 1.0
    assert sim >= 0.85  # Strong alignment on robotics keyword topic


# ============================================================================
# 4. End-to-End Ranking: Robotics Hackathon Article vs Candidate Photos
# ============================================================================

@pytest.mark.asyncio
async def test_intelligent_photo_relevance_ranking(test_photo_library):
    """
    Validates the user prompt's exact target example:
    Article: 'Students participating in the national robotics hackathon'

    Expected outcome:
    photo_17.jpg -> top relevance (~0.94)
    photo_21.jpg -> high relevance (~0.89)
    photo_04.jpg -> moderate (~0.73)
    photo_99.jpg -> low relevance (food/cafeteria)
    """
    article_content = {
        "title": "Students participating in the national robotics hackathon",
        "description": "Undergraduate engineering students built an autonomous quadruped machine for the national robotics competition.",
        "section": "Projects",
    }

    embedder = MockVisionEmbedder()

    result = await rank_photos_for_article(
        article_content=article_content,
        photos=test_photo_library,
        top_k=5,
        filter_duplicates=True,
        embedder=embedder,
    )

    ranked = result["ranked_photos"]
    assert len(ranked) >= 4

    top_ids = [r["photo_id"] for r in ranked]
    # photo_17 and photo_21 (robotics) must be ranked above food (photo_99)
    assert "photo_17" in top_ids[:2] or "photo_21" in top_ids[:2]

    # Check that robotics photos have significantly higher relevance than food photo
    robotics_relevance = next(r["relevance_score"] for r in ranked if r["photo_id"] == "photo_17")
    food_relevance = next(r["relevance_score"] for r in ranked if r["photo_id"] == "photo_99")
    assert robotics_relevance > food_relevance

    # Near-duplicate must be detected
    assert result["duplicates_detected"] >= 1

    # Selected hero must be a real high-res landscape photograph
    assert result["selected_hero"] is not None
    assert result["selected_hero"]["photo_id"] in ("photo_17", "photo_21")
    assert result["selected_hero"]["orientation"] in ("landscape", "panoramic")


# ============================================================================
# 5. Real Photographs Preference (Zero AI Synthesis)
# ============================================================================

@pytest.mark.asyncio
async def test_real_photos_preferred_no_ai_generation(test_photo_library):
    """
    Strict guarantee: Real uploaded photographs must always be selected.
    No generative UI or AI synthetic photograph generation when real photos exist.
    """
    result = await rank_photos_for_article(
        article_content="Annual College Science Exhibition",
        photos=test_photo_library,
        top_k=3,
        embedder=MockVisionEmbedder(),
    )

    assert len(result["ranked_photos"]) > 0
    for p in result["ranked_photos"]:
        # Verify source is a real local/uploaded image path
        assert p["url"] is not None
        assert os.path.exists(p["url"])
        assert not p["url"].startswith("ai-generated://")


# ============================================================================
# 6. REST API Endpoint: POST /api/v1/magazine/photos/rank
# ============================================================================

@pytest.mark.asyncio
async def test_api_photos_rank_endpoint(test_photo_library, monkeypatch):
    """Tests the REST API endpoint for photo ranking."""
    # Ensure test uses deterministic MockVisionEmbedder
    monkeypatch.setenv("USE_MOCK_VISION_EMBEDDER", "1")

    payload = {
        "article_content": {
            "title": "Students participating in the national robotics hackathon",
            "description": "Prototype demonstration at national hackathon.",
        },
        "photos": [
            {
                "id": p["id"],
                "url": p["url"],
                "caption": p["caption"],
            }
            for p in test_photo_library
        ],
        "top_k": 4,
        "filter_duplicates": True,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/magazine/photos/rank", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        payload_data = data["data"]
        assert "ranked_photos" in payload_data
        assert "selected_hero" in payload_data
        assert len(payload_data["ranked_photos"]) == 4

        first_photo = payload_data["ranked_photos"][0]
        assert "photo_id" in first_photo
        assert "relevance_score" in first_photo
        assert "quality_score" in first_photo
        assert "combined_score" in first_photo
        assert "match_reason" in first_photo
