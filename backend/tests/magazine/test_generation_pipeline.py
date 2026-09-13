"""
Unit tests for the template-driven AI College Magazine Generation Pipeline.
Uses synthetic fixtures with zero external network or model downloads.
"""

import os
import tempfile
import pytest
from typing import Any, Dict, List, Optional, Type

from app.infrastructure.ai.base import BaseAIProvider, T
from app.infrastructure.ai.manager import AIServiceManager
from app.infrastructure.ai.schemas import StructuredMagazineStoryContent
from app.modules.magazine.templates.siet_default_v1 import get_siet_default_v1_template
from app.modules.magazine.generation_pipeline import MagazineGenerationPipeline
from app.modules.magazine.advanced_validator import AdvancedMagazineValidator
from app.modules.magazine.admin_actions import AdminMagazineEditor


class MockGroundedQwenProvider(BaseAIProvider):
    """Mock Qwen3-14B provider returning strictly grounded structured content."""

    provider_name: str = "qwen_mock"

    async def generate_text(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        if "shorter" in prompt.lower():
            return "Edge AI Workshop"
        if "caption" in prompt.lower():
            return "Students participating in the AI laboratory."
        return "Polished editorial text grounded strictly in the source."

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        *,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> T:
        if schema == StructuredMagazineStoryContent:
            # Check prompt for Event A or Event B
            if "HackFest" in prompt or "Prize" in prompt:
                return StructuredMagazineStoryContent(
                    section="Competitions & Victories",
                    story_type="achievement_victory",
                    headline="SIET Team Champions at National HackFest 2026",
                    subheadline="First Prize and Gold Medal Secured",
                    polished_body=(
                        "Engineering students from Sri Shakthi Institute of Engineering & Technology "
                        "secured First Prize and bagged the Gold Medal at National HackFest on August 20, 2026. "
                        "The team was awarded a cash prize of INR 50,000 for their automated smart irrigation system."
                    ),
                    short_summary="SIET wins First Prize with INR 50,000 cash award at National HackFest 2026.",
                    photo_captions=[
                        "Winning team receiving the First Prize trophy and cash award.",
                        "Team demonstrating their automated smart irrigation prototype.",
                    ],
                    keywords=["HackFest", "Gold Medal", "First Prize", "IoT"],
                    page_type="achievement_victory",
                    layout_intent="achievement_feature",
                    recommended_image_count=2,
                    decorative_asset_category="trophy_3d",
                )
            else:
                return StructuredMagazineStoryContent(
                    section="Technical Workshops",
                    story_type="workshop",
                    headline="Hands-on Workshop on Edge AI and TinyML Systems",
                    subheadline="Department of Electronics & Communication Engineering",
                    polished_body=(
                        "The Department of Electronics and Communication Engineering conducted a two-day "
                        "hands-on workshop on Edge AI and TinyML on July 18, 2026. Over 85 participating students "
                        "deployed anomaly detection models on ESP32-S3 microcontroller hardware."
                    ),
                    short_summary="85 undergraduates deploy TinyML anomaly models at SIET ECE workshop.",
                    photo_captions=[
                        "Undergraduates configuring sensor modules in the laboratory.",
                        "Live demonstration of quantized neural inference on hardware.",
                        "Group photograph of workshop participants and coordinators.",
                    ],
                    keywords=["Edge AI", "TinyML", "ESP32", "ECE"],
                    page_type="workshop",
                    layout_intent="image_grid",
                    recommended_image_count=2,
                    decorative_asset_category="tech_circuit",
                )

        raise NotImplementedError(f"Mock does not support schema {schema}")

    async def health(self) -> dict:
        return {"status": "healthy", "provider": "qwen"}


@pytest.fixture
def synthetic_fixture():
    """
    Synthetic fixture containing:
    Event A: Workshop on Edge AI + 3 photos
    Event B: HackFest 2026 Victory + 2 photos
    """
    event_a_text = (
        "# Hands-on Workshop on Edge AI and TinyML Systems\n\n"
        "Department of Electronics & Communication Engineering conducted a two-day hands-on workshop "
        "on July 18, 2026. 85 registered students deployed anomaly detection models on ESP32-S3 microcontrollers."
    )
    event_b_text = (
        "# National HackFest 2026 Championship Victory\n\n"
        "Computer Science students won First Prize and Gold Medal with INR 50,000 cash award at National HackFest "
        "on August 20, 2026 for their automated irrigation system."
    )

    combined_source = f"{event_a_text}\n\n---\n\n{event_b_text}"

    event_photos_map = {
        "story_1": ["photo_a_1.png", "photo_a_2.png", "photo_a_3.png"],
        "story_2": ["photo_b_1.png", "photo_b_2.png"],
    }

    return {
        "source_text": combined_source,
        "event_a_text": event_a_text,
        "event_b_text": event_b_text,
        "event_photos_map": event_photos_map,
    }


@pytest.fixture
def pipeline():
    ai_service = AIServiceManager(primary_provider="qwen")
    ai_service.register_provider("qwen", MockGroundedQwenProvider())
    template = get_siet_default_v1_template()
    return MagazineGenerationPipeline(ai_service=ai_service, template_spec=template)


# =============================================================================
# 1. Photo Association & Invariant Tests
# =============================================================================

@pytest.mark.asyncio
async def test_photo_isolation_event_a_never_receives_event_b_photos(pipeline, synthetic_fixture):
    """
    CRITICAL REQUIREMENT:
    Verify that Event A never receives Event B's photos.
    Event A (3 photos) retains its photos; Event B (2 photos) retains its photos.
    """
    stories = pipeline.parse_source_document(synthetic_fixture["source_text"])
    stories = pipeline.associate_event_photos(stories, synthetic_fixture["event_photos_map"])

    story_a = next(s for s in stories if s["story_id"] == "story_1")
    story_b = next(s for s in stories if s["story_id"] == "story_2")

    # Invariant checks
    assert "photo_b_1.png" not in story_a["attached_photos"]
    assert "photo_b_2.png" not in story_a["attached_photos"]
    assert len(story_a["attached_photos"]) == 3
    assert story_a["attached_photos"] == ["photo_a_1.png", "photo_a_2.png", "photo_a_3.png"]

    assert "photo_a_1.png" not in story_b["attached_photos"]
    assert "photo_a_2.png" not in story_b["attached_photos"]
    assert "photo_a_3.png" not in story_b["attached_photos"]
    assert len(story_b["attached_photos"]) == 2
    assert story_b["attached_photos"] == ["photo_b_1.png", "photo_b_2.png"]


@pytest.mark.asyncio
async def test_validator_catches_cross_event_photo_contamination(pipeline, synthetic_fixture):
    """
    Verify that if a photo from Event B is erroneously placed in Event A's page,
    the validator catches the violation and marks the page invalid.
    """
    contaminated_page = {
        "page_number": 3,
        "page_type": "workshop",
        "story_id": "story_1",  # Event A
        "headline": "Hands-on Workshop on Edge AI",
        "body": "Students attended the workshop on July 18, 2026.",
        "attached_photos": ["photo_a_1.png", "photo_b_1.png"],  # photo_b_1 belongs to Event B!
    }

    result = pipeline.validator.validate_page(
        page_data=contaminated_page,
        source_story={"source_text": synthetic_fixture["event_a_text"]},
        all_event_photos_map=synthetic_fixture["event_photos_map"],
    )

    assert not result.is_valid
    assert len(result.photo_issues) > 0
    assert any("PHOTO ISOLATION VIOLATION" in issue for issue in result.photo_issues)


# =============================================================================
# 2. Strict Grounding Validation Tests
# =============================================================================

@pytest.mark.asyncio
async def test_grounding_validation_catches_unsupported_facts(pipeline, synthetic_fixture):
    """
    Verify that generated content cannot introduce unsupported dates or rankings.
    """
    hallucinated_page = {
        "page_number": 3,
        "page_type": "workshop",
        "story_id": "story_1",
        "headline": "Workshop in 2038",  # 2038 is not in source
        "body": "The students secured First Prize and 9900 participants attended.",  # First prize & 9900 not in workshop
        "attached_photos": ["photo_a_1.png"],
    }

    result = pipeline.validator.validate_page(
        page_data=hallucinated_page,
        source_story={"source_text": synthetic_fixture["event_a_text"]},
        all_event_photos_map=synthetic_fixture["event_photos_map"],
    )

    assert not result.is_valid
    assert len(result.grounding_issues) > 0
    grounding_str = " ".join(result.grounding_issues)
    assert "2038" in grounding_str or "9900" in grounding_str or "first prize" in grounding_str.lower()


# =============================================================================
# 3. Template Schema Conformity Tests
# =============================================================================

def test_template_schema_conformity():
    """
    Verify that SIET_DEFAULT_V1 conforms to template specifications
    and defines all 11 required page types with explicit regions.
    """
    template = get_siet_default_v1_template()
    assert template.template_id == "SIET_DEFAULT_V1"

    required_page_types = [
        "cover",
        "contents",
        "event",
        "achievement_victory",
        "project",
        "workshop",
        "seminar",
        "faculty_activity",
        "student_activity",
        "photo_feature",
        "closing_page",
    ]

    for p_type in required_page_types:
        assert p_type in template.supported_page_types, f"Missing required page type: {p_type}"
        spec = template.supported_page_types[p_type]
        assert len(spec.text_regions) > 0, f"Page type '{p_type}' must have text regions"
        assert spec.maximum_images >= 1 or p_type in {"contents"}
        assert spec.headline_limits["max_words"] > 0
        assert spec.body_limits["max_words"] > 0


# =============================================================================
# 4. End-to-End Pipeline Integration Test
# =============================================================================

@pytest.mark.asyncio
async def test_end_to_end_source_to_magazine_page_model(pipeline, synthetic_fixture):
    """
    End-to-end integration test:
    source → structured content → template → magazine page model → PDF
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_pdf = os.path.join(tmp_dir, "test_magazine.pdf")

        pages, report, pdf_path = await pipeline.generate_magazine(
            source_text_or_path=synthetic_fixture["source_text"],
            department="Department of ECE & CSE",
            issue_title="SIET Engineering Highlights 2026",
            event_photos_map=synthetic_fixture["event_photos_map"],
            output_pdf_path=output_pdf,
        )

        # 1. Output structure check
        assert len(pages) == 5  # Cover, Contents, Story 1 (Workshop), Story 2 (Victory), Closing = 5 pages total
        assert pages[0]["page_type"] == "cover"
        assert pages[1]["page_type"] == "contents"
        assert pages[2]["page_type"] in {"workshop", "event"}
        assert pages[3]["page_type"] in {"achievement_victory", "event"}
        assert pages[4]["page_type"] == "closing_page"

        # 2. Photo isolation verified on generated pages
        story_1_page = pages[2]
        story_2_page = pages[3]
        for p in story_1_page["attached_photos"]:
            assert p.startswith("photo_a_"), f"Story 1 page contaminated with {p}"
        for p in story_2_page["attached_photos"]:
            assert p.startswith("photo_b_"), f"Story 2 page contaminated with {p}"

        # 3. Validation passed
        assert report.is_valid
        assert len(report.pages_needing_regeneration) == 0

        # 4. PDF generated
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 0


# =============================================================================
# 5. Targeted Single-Page Regeneration Test
# =============================================================================

@pytest.mark.asyncio
async def test_targeted_single_page_regeneration(pipeline, synthetic_fixture):
    """
    Verify that single page can be regenerated without rerunning whole magazine.
    """
    stories = pipeline.parse_source_document(synthetic_fixture["source_text"])
    stories = pipeline.associate_event_photos(stories, synthetic_fixture["event_photos_map"])
    story_a = stories[0]

    initial_page = {
        "page_number": 3,
        "page_type": "event",
        "story_id": "story_1",
        "headline": "Old Rough Headline",
        "body": "Rough text.",
        "attached_photos": ["photo_a_1.png"],
    }

    updated_page = await pipeline.regenerate_page(
        page_data=initial_page,
        source_story=story_a,
        department="ECE",
        admin_instructions="Make the tone more professional.",
    )

    assert updated_page["headline"] == "Hands-on Workshop on Edge AI and TinyML Systems"
    assert "July 18, 2026" in updated_page["body"]
    assert updated_page["page_number"] == 3


# =============================================================================
# 6. Admin Actions & Natural Language Instructions
# =============================================================================

@pytest.mark.asyncio
async def test_admin_actions_natural_language_instructions(pipeline, synthetic_fixture):
    """
    Verify admin editing actions:
    - Swap photo position
    - Shorten headline
    - Give more whitespace
    """
    editor = AdminMagazineEditor(pipeline)

    page = {
        "page_number": 3,
        "page_type": "workshop",
        "headline": "Very Long Headline Exceeding The Desired Length In Words",
        "body": "First sentence here. Second sentence here. Third sentence here. Fourth sentence here.",
        "attached_photos": ["photo_a_1.png", "photo_a_2.png"],
    }

    # Action 1: "Use the second photo as the main image."
    updated_1 = await editor.apply_admin_layout_instruction(
        page_data=page,
        source_story={"source_text": synthetic_fixture["event_a_text"]},
        department="ECE",
        instruction="Use the second photo as the main image.",
    )
    assert updated_1["attached_photos"][0] == "photo_a_2.png"
    assert updated_1["attached_photos"][1] == "photo_a_1.png"

    # Action 2: "Make this headline shorter."
    updated_2 = await editor.apply_admin_layout_instruction(
        page_data=page,
        source_story={"source_text": synthetic_fixture["event_a_text"]},
        department="ECE",
        instruction="Make this headline shorter.",
    )
    assert len(updated_2["headline"].split()) < len("Very Long Headline Exceeding The Desired Length In Words".split())

    # Action 3: "Give this page more whitespace."
    updated_3 = await editor.apply_admin_layout_instruction(
        page_data=page,
        source_story={"source_text": synthetic_fixture["event_a_text"]},
        department="ECE",
        instruction="Give this page more whitespace.",
    )
    assert len(updated_3["body"].split()) < len("First sentence here. Second sentence here. Third sentence here. Fourth sentence here.".split())
