import pytest
from app.modules.magazine.orchestrator import (
    create_editorial_plan,
    generate_plan_conditioned_content,
    review_assembled_issue,
    run_orchestrated_magazine_pipeline,
)
from app.modules.magazine.validator import (
    verify_section_quality,
    run_automated_self_check_and_retry,
)


@pytest.mark.asyncio
async def test_create_editorial_plan_dynamic(monkeypatch):
    monkeypatch.setenv("MAGAZINE_LLM_PROVIDER", "none")
    plan = await create_editorial_plan(
        source_text="Annual Hackathon proceedings and IoT prototypes presented by Mechanical students.",
        section_schema=[
            {"key": "title", "label": "Title", "enabled": True},
            {"key": "description", "label": "Description", "enabled": True},
            {"key": "writeup", "label": "Writeup", "enabled": True},
            {"key": "toc_summary", "label": "TOC", "enabled": True},
        ],
        template_name="SIET Custom Engineering Template",
        event_name="SIET IoT & Mechatronics Expo 2026",
    )

    assert "IoT & Mechatronics" in plan["real_issue_title"]
    assert "sections_plan" in plan
    assert "writeup" in plan["sections_plan"]
    assert plan["sections_plan"]["writeup"]["target_word_count"] > 100


@pytest.mark.asyncio
async def test_generate_plan_conditioned_content_dynamic(monkeypatch):
    monkeypatch.setenv("MAGAZINE_LLM_PROVIDER", "none")
    sample_text = (
        "SIET Mechatronics Expo 2026 convened 200 participants.\n"
        "Students unveiled an inverted pendulum self-balancing unicycle with brushless motor control.\n"
        "The project was awarded 1st prize by the industry evaluation jury.\n"
        "The jury highlighted the precision frequency response of the control loop."
    )

    plan = await create_editorial_plan(
        source_text=sample_text,
        section_schema=[
            {"key": "title", "label": "Title", "enabled": True},
            {"key": "description", "label": "Description", "enabled": True},
            {"key": "writeup", "label": "Writeup", "enabled": True},
            {"key": "toc_summary", "label": "TOC", "enabled": True},
        ],
        template_name="SIET Engineering Template",
        event_name="SIET Mechatronics Expo 2026",
    )

    content = await generate_plan_conditioned_content(
        editorial_plan=plan,
        source_text=sample_text,
    )

    assert "Mechatronics Expo" in content["magazine_issue_title"]
    assert len(content["writeup_text"]) > 50
    assert content["confidence_score"] >= 0.85
    assert "sections" in content


def test_verify_section_quality_word_budget():
    # Writeup with ~300 words should pass
    normal_writeup = " ".join(["word"] * 300)
    res_normal = verify_section_quality("writeup", normal_writeup)
    assert res_normal["passed"] is True

    # Section with forbidden cliché should fail
    cliche_text = "In today's fast-paced world, engineering students innovate."
    res_cliche = verify_section_quality("description", cliche_text)
    assert res_cliche["passed"] is False
    assert any("cliché" in issue for issue in res_cliche["issues"])


@pytest.mark.asyncio
async def test_run_automated_self_check_and_retry(monkeypatch):
    monkeypatch.setenv("MAGAZINE_LLM_PROVIDER", "none")
    content_payload = {
        "magazine_issue_title": "SIET AI Innovation Summit 2026",
        "description": "Executive review of AI innovations presented by undergraduate researchers.",
        "writeup_text": "Detailed proceedings of the annual symposium with faculty research mentors.",
        "toc_summary": "Comprehensive overview and index of event sessions.",
        "sections": {
            "title": {"content": "SIET AI Innovation Summit 2026"},
            "description": {"content": "In today's fast-paced world, students presented research."},  # Has cliché to trigger retry
            "writeup": {"content": "Detailed proceedings of the annual symposium with faculty research mentors."},
            "toc_summary": {"content": "Comprehensive overview and index of event sessions."},
        },
    }

    checked = await run_automated_self_check_and_retry(content_payload)
    assert "verifier_reports" in checked
    assert "description" in checked["verifier_reports"]
    assert checked["verifier_reports"]["description"]["retry_performed"] is True


@pytest.mark.asyncio
async def test_full_orchestrated_pipeline_execution(monkeypatch):
    monkeypatch.setenv("MAGAZINE_LLM_PROVIDER", "none")
    notes = (
        "National Conference on Sustainable Energy held at SIET campus on September 10, 2026.\n"
        "Keynote by Dr. Raman on solid-state battery electrolytes.\n"
        "Over 40 technical papers were presented across 3 tracks.\n"
        "Best paper award went to the solar perovskite efficiency study."
    )

    pipeline_res = await run_orchestrated_magazine_pipeline(
        event_name="SIET National Energy Conference 2026",
        raw_notes=notes,
        template_name="SIET Engineering Template",
        max_rework_rounds=1,
    )

    assert pipeline_res["status"] in ["published", "needs_review"]
    assert "Energy Conference" in pipeline_res["magazine_issue_title"]
    assert pipeline_res["orchestrator_score"] >= 0.80
    assert "sections" in pipeline_res
    assert len(pipeline_res["writeup_text"]) > 50
