import os
import tempfile
import pytest
from PIL import Image, ImageDraw

from app.modules.magazine.photo_curator import (
    analyze_photo,
    curate_photos_for_magazine,
)


@pytest.fixture
def sample_images():
    temp_dir = tempfile.mkdtemp()
    images = []

    # 1. High-res landscape image (hero candidate)
    img_hero = Image.new("RGB", (1920, 1080), color=(180, 50, 50))
    draw = ImageDraw.Draw(img_hero)
    for i in range(0, 1920, 40):
        draw.line([(i, 0), (i, 1080)], fill=(255, 255, 255), width=3)
    p_hero = os.path.join(temp_dir, "hero.jpg")
    img_hero.save(p_hero, format="JPEG")
    images.append({"url": p_hero, "caption": "Opening Keynote Stage"})

    # 2. Medium landscape image (feature candidate)
    img_feature = Image.new("RGB", (1200, 800), color=(50, 120, 200))
    p_feat = os.path.join(temp_dir, "feature.jpg")
    img_feature.save(p_feat, format="JPEG")
    images.append({"url": p_feat, "caption": "Autonomous Robot Demo"})

    # 3. Square gallery photo
    img_gal1 = Image.new("RGB", (800, 800), color=(50, 200, 100))
    p_gal1 = os.path.join(temp_dir, "gal1.jpg")
    img_gal1.save(p_gal1, format="JPEG")
    images.append({"url": p_gal1, "caption": "Student Project Poster Presentation"})

    # 4. Another gallery photo
    img_gal2 = Image.new("RGB", (900, 600), color=(220, 180, 50))
    p_gal2 = os.path.join(temp_dir, "gal2.jpg")
    img_gal2.save(p_gal2, format="JPEG")
    images.append({"url": p_gal2, "caption": "Award Ceremony Dignitaries"})

    yield images

    # Teardown
    for item in images:
        if os.path.exists(item["url"]):
            try:
                os.remove(item["url"])
            except OSError:
                pass
    try:
        os.rmdir(temp_dir)
    except OSError:
        pass


def test_analyze_photo_attributes(sample_images):
    hero_path = sample_images[0]["url"]
    analysis = analyze_photo(hero_path, photo_id="hero_1", url=hero_path, caption="Keynote")

    assert analysis.width == 1920
    assert analysis.height == 1080
    assert analysis.orientation == "landscape"
    assert analysis.sharpness_score > 0
    assert analysis.recommended_slot == "hero_cover"
    assert analysis.caption == "Keynote"


def test_analyze_photo_missing_raises():
    with pytest.raises(FileNotFoundError):
        analyze_photo("/non_existent_image_path.jpg")


def test_curate_photos_slot_assignment(sample_images):
    curated = curate_photos_for_magazine(
        photos_input=sample_images,
        target_page_budget=5,
    )

    assert curated["hero_cover"] is not None
    assert curated["feature_story"] is not None
    assert len(curated["gallery"]) >= 1
    assert len(curated["all_analyzed"]) == len(sample_images)


def test_curate_photos_empty_input():
    curated = curate_photos_for_magazine(photos_input=[])
    assert curated["hero_cover"] is None
    assert curated["feature_story"] is None
    assert curated["gallery"] == []
