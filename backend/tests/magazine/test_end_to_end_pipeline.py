"""Comprehensive Integration Test Suite for End-to-End AI Magazine Generation Pipeline.

Verifies the full 9-stage workflow:
1. Reading documents
2. Extracting content
3. Understanding sections (RAG + Qwen)
4. Selecting templates
5. Matching photographs (SigLIP)
6. Planning pages (Multi-Page & Layout Planner)
7. Rendering pages (Template-Driven PyMuPDF)
8. Validating pages (Visual QC + Recovery)
9. Finalizing magazine (PDF, Previews, TOC, Publishing)
"""

import io
import os
import tempfile
import pytest
from PIL import Image
import fitz
import docx
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.magazine.end_to_end_pipeline import (
    run_end_to_end_magazine_pipeline,
    PIPELINE_STAGES,
)
from app.modules.magazine.schemas import PipelineProgressStage


@pytest.fixture
def temp_assets():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a sample photograph and save it BOTH in the temp dir (for the
        # DOCX embedding) AND in uploads/magazines/ (where the renderer's
        # _resolve_image_path looks for image files).
        photo_name = "robotics_photo.jpg"
        photo_path_tmp = os.path.join(tmpdir, photo_name)
        img = Image.new("RGB", (640, 480), color=(50, 100, 200))
        img.save(photo_path_tmp, format="JPEG")

        uploads_mag_dir = os.path.join(os.getcwd(), "uploads", "magazines")
        os.makedirs(uploads_mag_dir, exist_ok=True)
        photo_path_uploads = os.path.join(uploads_mag_dir, photo_name)
        img.save(photo_path_uploads, format="JPEG")

        # Create a DOCX document
        doc = docx.Document()
        doc.add_heading("Robotics & AI Lab Annual Symposium", level=0)
        doc.add_paragraph("Event Date: 2026-04-15")
        doc.add_heading("Autonomous Navigation Prototype", level=1)
        doc.add_paragraph(
            "Students and faculty from the Robotics Lab demonstrated a quadcopter prototype "
            "with visual-inertial odometry and real-time obstacle avoidance. The project "
            "achieved a 99.4% waypoint navigation accuracy in indoor GPS-denied environments."
        )
        doc.add_heading("Student Achievements", level=1)
        doc.add_paragraph(
            "The team won first prize at the National Robotics Championship 2026. "
            "Lead researcher Ananya Rao received the Best Innovation Award."
        )
        # Embed photo into docx
        doc.add_picture(photo_path_tmp, width=docx.shared.Inches(3))

        docx_buf = io.BytesIO()
        doc.save(docx_buf)
        docx_bytes = docx_buf.getvalue()

        # Create a PDF document
        pdf_doc = fitz.open()
        p = pdf_doc.new_page(width=595, height=842)
        p.insert_text((50, 80), "IoT and Cyber Security Summit 2026", fontsize=18)
        p.insert_text((50, 120), "Event Date: 2026-05-10\nDepartment: Cyber Security Lab", fontsize=12)
        p.insert_text(
            (50, 160),
            "Faculty and student researchers convened to demonstrate edge encryption, "
            "intrusion detection systems, and secure mesh protocols for smart infrastructure.",
            fontsize=11,
        )
        pdf_bytes = pdf_doc.write()
        pdf_doc.close()

        yield {
            "tmpdir": tmpdir,
            "photo_path": photo_path_uploads,
            "photo_name": photo_name,
            "docx_bytes": docx_bytes,
            "pdf_bytes": pdf_bytes,
        }

        # Clean up the uploads/magazines copy if it is no longer needed by
        # any other test (best-effort; never raise on failure).
        try:
            if os.path.exists(photo_path_uploads):
                os.remove(photo_path_uploads)
        except OSError:
            pass


@pytest.mark.asyncio
async def test_end_to_end_pipeline_docx_full_flow(temp_assets):
    """
    Tests complete 9-stage pipeline from uploaded DOCX, real photo matching,
    template selection, multi-page planning, rendering, QC, to final PDF.
    """
    real_photos = [
        {
            "id": "photo_symp_01",
            "url": f"/uploads/magazines/robotics_photo.jpg",
            "file_path": temp_assets["photo_path"],
            "filename": "robotics_photo.jpg",
        }
    ]

    result = await run_end_to_end_magazine_pipeline(
        file_bytes=temp_assets["docx_bytes"],
        filename="symposium_report.docx",
        real_photos=real_photos,
        department_or_lab="Robotics Lab",
        target_page_budget=3,
        publish_immediately=True,
        use_llm=False,
        max_qc_attempts=3,
    )

    # Assert response structure and publication
    assert result is not None
    assert result.status == "published"
    assert "Robotics" in result.title or "Symposium" in result.title
    assert result.total_pages >= 2
    assert result.pdf_url is not None
    assert result.pdf_url.endswith(".pdf")

    # Assert physical PDF exists and can be opened
    actual_pdf_path = result.pdf_url.lstrip("/")
    assert os.path.exists(actual_pdf_path)
    verify_doc = fitz.open(actual_pdf_path)
    assert len(verify_doc) == result.total_pages
    verify_doc.close()

    # Assert high-res page previews generated
    assert len(result.page_previews) == result.total_pages
    for p_url in result.page_previews:
        assert os.path.exists(p_url.lstrip("/"))

    # Assert grounded TOC entries
    assert len(result.toc_entries) == result.total_pages
    assert result.toc_entries[0]["page_number"] == 1

    # Assert Stage telemetry has all 9 stages completed
    assert len(result.stage_telemetry) == 9
    stage_numbers = [s.stage_number for s in result.stage_telemetry]
    assert stage_numbers == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    for st in result.stage_telemetry:
        assert st.status == "completed"

    # Assert Visual Quality Control score
    assert result.overall_quality_score >= 80.0
    assert len(result.qc_reports) == result.total_pages


@pytest.mark.asyncio
async def test_end_to_end_pipeline_pdf_full_flow(temp_assets):
    """
    Tests complete pipeline with PDF source document.
    """
    result = await run_end_to_end_magazine_pipeline(
        file_bytes=temp_assets["pdf_bytes"],
        filename="cyber_summit.pdf",
        department_or_lab="Cyber Security Lab",
        target_page_budget=2,
        publish_immediately=True,
        use_llm=False,
    )

    assert result.status == "published"
    assert result.total_pages >= 2
    assert result.pdf_url is not None
    assert os.path.exists(result.pdf_url.lstrip("/"))
    assert len(result.page_previews) == result.total_pages
    assert len(result.stage_telemetry) == 9
    assert result.overall_quality_score >= 80.0


@pytest.mark.asyncio
async def test_end_to_end_progress_callback_all_stages(temp_assets):
    """
    Verifies that the progress callback receives all 9 stages in exact sequential order.
    """
    emitted_stages = []

    async def progress_listener(stage: PipelineProgressStage):
        emitted_stages.append({
            "stage_number": stage.stage_number,
            "stage_name": stage.stage_name,
            "status": stage.status,
        })

    result = await run_end_to_end_magazine_pipeline(
        raw_notes="AI Lab edge intelligence workshop with 15 prototypes demonstrated.",
        department_or_lab="AI Lab",
        target_page_budget=2,
        use_llm=False,
        on_progress=progress_listener,
    )

    # Verify that in_progress and completed were emitted for the stages
    assert len(emitted_stages) >= 9

    completed_stages = [s for s in emitted_stages if s["status"] == "completed"]
    completed_numbers = [s["stage_number"] for s in completed_stages]
    assert completed_numbers == [1, 2, 3, 4, 5, 6, 7, 8, 9]

    expected_names = [
        "Reading documents",
        "Extracting content",
        "Understanding sections",
        "Selecting templates",
        "Matching photographs",
        "Planning pages",
        "Rendering pages",
        "Validating pages",
        "Finalizing magazine",
    ]
    for s, expected in zip(completed_stages, expected_names):
        assert s["stage_name"] == expected


@pytest.mark.asyncio
async def test_end_to_end_qc_recovery_on_potential_overflow(temp_assets):
    """
    Verifies that the Visual Quality Validator (Stage 8) executes the 10 checks,
    evaluates layout quality, and produces compliant pages.
    """
    dense_notes = "\n\n".join([
        f"Research Section {i}: Detailed analysis of algorithm efficiency and benchmarking."
        for i in range(12)
    ])

    result = await run_end_to_end_magazine_pipeline(
        raw_notes=dense_notes,
        department_or_lab="Research Lab",
        target_page_budget=3,
        use_llm=False,
        max_qc_attempts=3,
    )

    assert result.status == "published"
    assert len(result.qc_reports) == result.total_pages
    for r in result.qc_reports:
        assert r["layout_score"] >= 70
        assert r["overall_score"] >= 80


@pytest.mark.asyncio
async def test_end_to_end_api_endpoints(temp_assets, client, db_session, admin_user):
    """
    Tests FastAPI HTTP endpoints:
    - POST /admin/magazine/generate/end-to-end-json
    - POST /admin/magazine/generate/end-to-end (multipart)

    Uses the persisted ``admin_user`` fixture (real row, real id) as the
    ``require_lab_admin`` principal so ``Magazine.created_by_id`` FKs hold on
    a fresh scratch DB.
    """
    from app.shared.auth.dependencies import require_lab_admin

    app.dependency_overrides[require_lab_admin] = lambda: admin_user

    try:
        # 1. Test JSON endpoint
        json_payload = {
            "department_or_lab": "IoT Lab",
            "event_name": "IoT Embedded Systems Expo",
            "raw_notes": "Sensors and smart telemetry units designed by students.",
            "target_page_budget": 2,
            "publish_immediately": True,
            "use_llm": False,
        }
        res = await client.post("/api/v1/admin/magazine/generate/end-to-end-json", json=json_payload)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data.get("success") is True
        mag_data = data["data"]
        assert mag_data["total_pages"] >= 1  # one sentence of notes cannot honestly fill 2 pages; no filler padding
        assert mag_data["pdf_url"] is not None
        assert len(mag_data["stage_telemetry"]) == 9

        # 2. Test Multipart endpoint
        files = {
            "file": ("notes.txt", b"AI Computer Vision Workshop notes and lab presentations.", "text/plain"),
            "photos": ("event_snap.jpg", open(temp_assets["photo_path"], "rb"), "image/jpeg"),
        }
        form_data = {
            "department_or_lab": "AI Lab",
            "event_name": "Vision AI Workshop",
            "target_page_budget": "2",
            "use_llm": "false",
        }
        res_mp = await client.post("/api/v1/admin/magazine/generate/end-to-end", data=form_data, files=files)
        assert res_mp.status_code == 200, res_mp.text
        data_mp = res_mp.json()
        assert data_mp.get("success") is True
        assert data_mp["data"]["total_pages"] >= 1  # one sentence cannot honestly fill 2 pages; no filler padding
    finally:
        app.dependency_overrides.pop(require_lab_admin, None)


@pytest.mark.asyncio
async def test_end_to_end_pipeline_chosen_template_applied(temp_assets):
    """
    Verifies that when an explicit template_id is supplied by the admin,
    Stage 4 resolves and forces it for matching sections, Stage 6 multi-page
    planning prioritizes it, and the chosen template is recorded in telemetry.
    """
    chosen_tid = "ai_lab_project_showcase"
    result = await run_end_to_end_magazine_pipeline(
        raw_notes="Autonomous AI Drone Navigation and Multi-Agent Swarm Intelligence.",
        department_or_lab="AI Lab",
        template_id=chosen_tid,
        target_page_budget=2,
        use_llm=False,
    )

    assert result is not None
    assert result.status == "published"
    assert result.total_pages >= 1  # one sentence of notes cannot honestly fill 2 pages; no filler padding

    # Check Stage 4 telemetry
    stage_4 = next((s for s in result.stage_telemetry if s.stage_number == 4), None)
    assert stage_4 is not None
    assert stage_4.details is not None
    assert stage_4.details.get("chosen_template_id") == chosen_tid

    # Check that project_showcase section used the chosen template
    selected_tmpls = stage_4.details.get("selected_templates", {})
    assert "project_showcase" in selected_tmpls
    assert selected_tmpls["project_showcase"]["template_id"] == chosen_tid
    assert selected_tmpls["project_showcase"]["confidence"] == 1.0


@pytest.mark.asyncio
async def test_end_to_end_api_endpoints_chosen_template(temp_assets, client, db_session, admin_user):
    """
    Verifies that POST /admin/magazine/generate/end-to-end multipart form data
    and POST /admin/magazine/generate/end-to-end-json properly accept and enforce template_id.

    Uses the persisted ``admin_user`` fixture (real row, real id) as the
    ``require_lab_admin`` principal so ``Magazine.created_by_id`` FKs hold on
    a fresh scratch DB.
    """
    from app.shared.auth.dependencies import require_lab_admin

    app.dependency_overrides[require_lab_admin] = lambda: admin_user

    try:
        # 1. JSON endpoint with template_id
        json_payload = {
            "department_or_lab": "AI Lab",
            "event_name": "AI Swarm Symposium",
            "raw_notes": "Reinforcement learning for quadcopter formation flying.",
            "target_page_budget": 2,
            "template_id": "ai_lab_project_showcase",
            "publish_immediately": True,
            "use_llm": False,
        }
        res = await client.post("/api/v1/admin/magazine/generate/end-to-end-json", json=json_payload)
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        stage_4 = next((s for s in data["stage_telemetry"] if s["stage_number"] == 4), None)
        assert stage_4 is not None
        assert stage_4["details"]["chosen_template_id"] == "ai_lab_project_showcase"

        # 2. Multipart endpoint with template_id form field
        files = {
            "file": ("notes.txt", b"Robotics prototype demonstration notes.", "text/plain"),
        }
        form_data = {
            "department_or_lab": "Robotics Lab",
            "event_name": "Robotics Autonomous Rover",
            "template_id": "robotics_lab_autonomous",
            "target_page_budget": "2",
            "use_llm": "false",
        }
        res_mp = await client.post("/api/v1/admin/magazine/generate/end-to-end", data=form_data, files=files)
        assert res_mp.status_code == 200, res_mp.text
        data_mp = res_mp.json()["data"]
        stage_4_mp = next((s for s in data_mp["stage_telemetry"] if s["stage_number"] == 4), None)
        assert stage_4_mp is not None
        assert stage_4_mp["details"]["chosen_template_id"] == "robotics_lab_autonomous_systems"
    finally:
        app.dependency_overrides.pop(require_lab_admin, None)


async def _ensure_lab(db_session, lab_id: int, name: str) -> None:
    """Create the target lab row (if missing) so Magazine.lab_id's FK holds.

    The magazine pipeline inserts with lab_id as a plain foreign key, so the
    lab must exist in the database before the endpoint is called.
    """
    from app.modules.labs.models import Lab

    existing = await db_session.get(Lab, lab_id)
    if existing is None:
        db_session.add(
            Lab(id=lab_id, name=name, code=f"TEST{lab_id}", slug=f"test-lab-{lab_id}")
        )
        await db_session.flush()


@pytest.mark.asyncio
async def test_end_to_end_json_endpoint_requires_lab_admin(temp_assets, client, db_session):
    """
    Verifies that POST /admin/magazine/generate/end-to-end-json is protected
    by require_lab_admin and rejects unauthenticated callers (issue #4).
    """
    # Ensure no dependency override is active for require_lab_admin
    from app.shared.auth.dependencies import require_lab_admin
    app.dependency_overrides.pop(require_lab_admin, None)

    json_payload = {
        "department_or_lab": "AI Lab",
        "event_name": "Unauthorized Attempt",
        "raw_notes": "This should be rejected.",
        "target_page_budget": 1,
        "publish_immediately": False,
        "use_llm": False,
    }
    res = await client.post("/api/v1/admin/magazine/generate/end-to-end-json", json=json_payload)
    assert res.status_code in (401, 403), f"Expected 401/403, got {res.status_code}: {res.text}"


@pytest.mark.asyncio
async def test_end_to_end_json_endpoint_resolves_lab_and_creator(temp_assets, client, db_session, admin_user):
    """
    Verifies that the JSON endpoint resolves the caller's lab via
    resolve_creation_lab and tags the magazine with lab_id/created_by_id
    (issue #4), same as the form-based /generate/end-to-end endpoint.
    """
    from app.shared.auth.dependencies import require_lab_admin

    app.dependency_overrides[require_lab_admin] = lambda: admin_user

    try:
        await _ensure_lab(db_session, 42, "Robotics Test Lab")
        json_payload = {
            "department_or_lab": "Robotics Lab",
            "event_name": "Lab Resolution Test",
            "raw_notes": "Autonomous navigation prototype demonstrated at the annual symposium.",
            "target_page_budget": 2,
            "publish_immediately": True,
            "use_llm": False,
            "lab_id": 42,
        }
        res = await client.post("/api/v1/admin/magazine/generate/end-to-end-json", json=json_payload)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data.get("success") is True
        mag_data = data["data"]
        assert mag_data["total_pages"] >= 1

        # Verify the magazine was persisted with the resolved lab and creator
        from app.modules.magazine.models import Magazine
        from sqlalchemy import select

        stmt = select(Magazine).order_by(Magazine.id.desc()).limit(1)
        mag = (await db_session.execute(stmt)).scalars().first()
        assert mag is not None
        assert mag.lab_id == 42
        assert mag.created_by_id == admin_user.id
        assert mag.status == "published"
    finally:
        app.dependency_overrides.pop(require_lab_admin, None)


@pytest.mark.asyncio
async def test_end_to_end_json_endpoint_sets_photo_filename_to_saved_name(temp_assets, client, db_session, admin_user):
    """
    Verifies that the JSON endpoint normalizes photo dicts so that the
    'filename' field is set to the saved name (basename of file_path/url),
    enabling the layout planner's asset-name fallback chain (issue #2).
    """
    from app.shared.auth.dependencies import require_lab_admin

    app.dependency_overrides[require_lab_admin] = lambda: admin_user

    try:
        await _ensure_lab(db_session, 7, "IoT Test Lab")
        json_payload = {
            "department_or_lab": "IoT Lab",
            "event_name": "Photo Filename Normalization",
            "raw_notes": "Smart sensor telemetry units designed and demonstrated by students.",
            "target_page_budget": 2,
            "publish_immediately": True,
            "use_llm": False,
            "lab_id": 7,
            "photos": [
                {
                    "id": "photo_01",
                    "file_path": temp_assets["photo_path"],
                    "url": "/uploads/magazines/robotics_photo.jpg",
                    "filename": "original_upload.jpg",
                }
            ],
        }
        res = await client.post("/api/v1/admin/magazine/generate/end-to-end-json", json=json_payload)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data.get("success") is True
        mag_data = data["data"]
        assert mag_data["total_pages"] >= 1

        # The magazine must have been created with the photo's saved name
        from app.modules.magazine.models import Magazine
        from sqlalchemy import select

        stmt = select(Magazine).order_by(Magazine.id.desc()).limit(1)
        mag = (await db_session.execute(stmt)).scalars().first()
        assert mag is not None
        assert mag.lab_id == 7
        assert mag.created_by_id == admin_user.id
    finally:
        app.dependency_overrides.pop(require_lab_admin, None)


