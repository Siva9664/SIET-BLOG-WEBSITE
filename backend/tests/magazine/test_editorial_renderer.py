import os
import tempfile
import pytest
from PIL import Image

from app.modules.magazine.renderer import render_editorial_magazine_pdf
from app.modules.magazine.validator import validate_rendered_magazine


@pytest.fixture
def magazine_payload():
    temp_dir = tempfile.mkdtemp()

    # Generate a couple of test images
    img1 = Image.new("RGB", (1600, 1000), color=(180, 40, 40))
    p1 = os.path.join(temp_dir, "cover.jpg")
    img1.save(p1, format="JPEG")

    img2 = Image.new("RGB", (1200, 800), color=(40, 80, 180))
    p2 = os.path.join(temp_dir, "feature.jpg")
    img2.save(p2, format="JPEG")

    out_pdf = os.path.join(temp_dir, "test_magazine.pdf")

    payload = {
        "magazine_data": {
            "title": "SIET AI & Autonomous Systems Conclave 2026",
            "slug": "siet-ai-conclave-2026",
            "description": "Sri Shakthi Institute of Engineering & Technology convened leading researchers, engineers, and faculty mentors for two days of deep technical workshops and demonstrations.",
            "event_name": "SIET AI Conclave 2026",
            "event_date": "2026-09-12",
            "department_name": "Artificial Intelligence & Data Science",
            "publication_year": 2026,
            "magazine_type": "special",
            "cover_pages": [{"url": p1, "caption": "Inaugural Session Keynote"}],
            "body_pages": [
                {
                    "url": p2,
                    "caption": "Real-time edge compute cluster demonstration",
                    "headline": "Breakthrough Edge Intelligence at SIET Labs",
                    "text": (
                        "During the plenary technical symposium, researchers demonstrated a 4-node clustered edge computing "
                        "architecture capable of executing quantized vision transformers at 90 FPS under 15W power envelope. "
                        "The system was developed entirely in-house by interdisciplinary undergraduate teams from Electronics "
                        "and Computer Science departments, under the mentorship of the SIET AI Incubation Laboratory.\n\n"
                        "Industry evaluators praised the thermal stability and real-time inference latency benchmarks achieved by "
                        "the student investigators, awarding top commendation honors and commercial prototyping grants."
                    ),
                }
            ],
            "gallery_images": [
                {"url": p1, "caption": "Opening ceremony ribbon cutting"},
                {"url": p2, "caption": "Student hardware bench test"},
            ],
        },
        "output_pdf_path": out_pdf,
        "latest_ai_news": [
            {
                "title": "Open-Source Foundation Models Reach Real-Time Reasoning Parity",
                "source": "MIT Tech Review",
                "date": "Sep 2026",
            },
            {
                "title": "Neuromorphic Vision Sensors Deployed for Micro-Robotics",
                "source": "IEEE Spectrum",
                "date": "Sep 2026",
            },
        ],
    }

    yield payload

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


def test_render_editorial_magazine_pdf(magazine_payload):
    result = render_editorial_magazine_pdf(
        magazine_data=magazine_payload["magazine_data"],
        output_pdf_path=magazine_payload["output_pdf_path"],
        latest_ai_news=magazine_payload["latest_ai_news"],
    )

    assert result["success"] is True
    assert result["total_pages"] == 5
    assert os.path.exists(result["pdf_path"])
    assert os.path.getsize(result["pdf_path"]) > 1000

    # Verify previews
    assert len(result["page_previews"]) == 5
    for prev in result["page_previews"]:
        local_p = prev if os.path.exists(prev) else prev.lstrip("/")
        assert os.path.exists(local_p)
        assert os.path.getsize(local_p) > 0

    # Verify TOC entries
    assert len(result["toc_entries"]) >= 4
    headings = [t["heading"] for t in result["toc_entries"]]
    assert "Contents & Executive Overview" in headings
    assert "Featured Research Story" in headings


def test_validate_rendered_magazine(magazine_payload):
    result = render_editorial_magazine_pdf(
        magazine_data=magazine_payload["magazine_data"],
        output_pdf_path=magazine_payload["output_pdf_path"],
        latest_ai_news=magazine_payload["latest_ai_news"],
    )

    content_mock = {
        "sources": [{"score": 0.88}],
        "overall_confidence_band": "auto_publish_eligible",
    }
    blueprint_mock = {
        "pages": [
            {"page_number": 1, "regions": [{"region_key": "hero", "width_pt": 500, "height_pt": 300}]},
            {"page_number": 2, "regions": [{"region_key": "overview", "width_pt": 500, "height_pt": 400}]},
        ]
    }

    val_res = validate_rendered_magazine(
        pdf_path=result["pdf_path"],
        page_previews=result["page_previews"],
        content=content_mock,
        blueprint=blueprint_mock,
    )

    assert val_res["is_valid"] is True
    assert val_res["overall_score"] >= 0.80
    assert len(val_res["issues"]) == 0
