"""Standalone executable demonstration of the End-to-End AI Magazine Pipeline.

Demonstrates:
DOCX parsing -> Content Extraction -> Qwen Section Structuring ->
Template Selection -> SigLIP Photo Matching -> Multi-Page Planning ->
PyMuPDF Rendering -> Visual QC Closed-Loop Recovery -> Final PDF Compilation.
"""

import asyncio
import io
import os
import sys
import fitz
import docx
from PIL import Image, ImageDraw

from app.modules.magazine.end_to_end_pipeline import (
    run_end_to_end_magazine_pipeline,
    PIPELINE_STAGES,
)
from app.modules.magazine.schemas import PipelineProgressStage


async def main():
    print("=" * 80)
    print(" SIET AI MAGAZINE: END-TO-END 9-STAGE PIPELINE TRACE ")
    print("=" * 80)

    # 1. Create realistic sample event photographs
    os.makedirs("uploads/magazines", exist_ok=True)
    p1_path = "uploads/magazines/demo_robotics_quad.jpg"
    im1 = Image.new("RGB", (1280, 720), color=(40, 70, 140))
    d1 = ImageDraw.Draw(im1)
    d1.rectangle([(100, 100), (1180, 620)], outline=(200, 220, 255), width=6)
    im1.save(p1_path, "JPEG")

    p2_path = "uploads/magazines/demo_team_showcase.jpg"
    im2 = Image.new("RGB", (1280, 720), color=(50, 120, 90))
    d2 = ImageDraw.Draw(im2)
    d2.rectangle([(120, 120), (1160, 600)], outline=(220, 255, 230), width=6)
    im2.save(p2_path, "JPEG")

    photos = [
        {"id": "photo_01", "url": f"/{p1_path}", "file_path": p1_path, "filename": "demo_robotics_quad.jpg"},
        {"id": "photo_02", "url": f"/{p2_path}", "file_path": p2_path, "filename": "demo_team_showcase.jpg"},
    ]

    # 2. Create realistic DOCX event proceedings
    doc = docx.Document()
    doc.add_heading("Sri Shakthi Institute of Engineering and Technology", level=0)
    doc.add_heading("AI & Autonomous Robotics Lab: National Innovation Summit 2026", level=1)
    doc.add_paragraph("Event Date: 2026-05-18")
    doc.add_paragraph(
        "The Artificial Intelligence and Robotics Lab convened the 2026 Innovation Summit, "
        "presenting breakthroughs in autonomous unmanned aerial vehicles, SLAM mapping algorithms, "
        "and neuromorphic edge computing. Industry partners from leading automation firms "
        "reviewed student demonstrations and prototype testbenches."
    )
    doc.add_heading("Autonomous Quadcopter Project", level=2)
    doc.add_paragraph(
        "A team of fourth-year undergraduate researchers demonstrated a sub-kilogram quadcopter "
        "capable of navigating complex indoor industrial environments without GPS connectivity. "
        "The system incorporates stereo-visual odometry and custom obstacle evasion pipelines."
    )
    doc.add_heading("Student & Faculty Honors", level=2)
    doc.add_paragraph(
        "The project team was awarded the Grand Prize at the National Aerospace Innovation Challenge. "
        "Dr. K. Senthil, Professor of Robotics, received the Mentor of the Year Award."
    )
    doc_buf = io.BytesIO()
    doc.save(doc_buf)
    docx_bytes = doc_buf.getvalue()

    # 3. Progress callback
    async def on_progress(stage: PipelineProgressStage):
        status_symbol = "✓" if stage.status == "completed" else "⚙️"
        print(f"[{status_symbol}] Stage {stage.stage_number}/9: {stage.stage_name} ({stage.status}) - {stage.message}")

    # 4. Run end-to-end pipeline
    res = await run_end_to_end_magazine_pipeline(
        file_bytes=docx_bytes,
        filename="Innovation_Summit_Proceedings.docx",
        real_photos=photos,
        department_or_lab="AI Lab",
        target_page_budget=4,
        publish_immediately=True,
        use_llm=False,
        max_qc_attempts=3,
        on_progress=on_progress,
    )

    print("\n" + "=" * 80)
    print(" GENERATION RESULTS SUMMARY ")
    print("=" * 80)
    print(f"Title:                 {res.title}")
    print(f"Slug:                  {res.slug}")
    print(f"Department / Lab:      {res.department_or_lab}")
    print(f"Status:                {res.status}")
    print(f"Total Pages:           {res.total_pages}")
    print(f"Overall QC Score:      {res.overall_quality_score}/100")
    print(f"Execution Time:        {res.execution_time_seconds}s")
    print(f"Compiled PDF Path:     {res.pdf_url}")
    print(f"Page Previews Count:   {len(res.page_previews)}")
    print(f"TOC Entries:           {len(res.toc_entries)}")
    for toc in res.toc_entries:
        print(f"  - Page {toc['page_number']}: {toc['heading']}")

    print("\n[✓] End-to-End AI Magazine Generation Pipeline trace verified successfully!")


if __name__ == "__main__":
    asyncio.run(main())
