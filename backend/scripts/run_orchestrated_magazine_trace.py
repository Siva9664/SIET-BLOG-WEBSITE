import asyncio
import json
import os
import time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
import app.modules.labs.models  # noqa: F401
import app.modules.domains.models  # noqa: F401
from app.modules.auth.models import User
from app.modules.media.models import Media
from app.modules.documents.models import SourceDocument, DocumentChunk
from app.modules.documents.embeddings import embed_text
from app.modules.magazine.models import Magazine, MagazineTemplate
from app.modules.magazine.orchestrator import (
    create_editorial_plan,
    generate_plan_conditioned_content,
    review_assembled_issue,
    run_orchestrated_magazine_pipeline,
)
from app.modules.magazine.pipeline import compile_magazine_pdf

REAL_DOCUMENT_TEXT = """
SIET INTERNATIONAL ENGINEERING & INNOVATION SYMPOSIUM 2026
Date: August 30, 2026
Location: Main Auditorium & Advanced AI Labs, Sri Shakthi Institute of Engineering and Technology (SIET), Coimbatore.

Executive Overview:
Sri Shakthi Institute of Engineering and Technology hosted the International Engineering & Innovation Symposium 2026.
The event brought together over 350 undergraduate researchers, 40 faculty delegates, and 15 industry keynote speakers.
Opening Keynote was delivered by Dr. S. Sharma (Head of AI & Autonomous Systems at Apex Robotics), who highlighted high-precision neural architecture search for edge robotics.

Key Project Models & Paper Presentations:
1. Team QuadRobo (1st Place Winner, ₹75,000 award): Autonomous quadruped legged robot using real-time spatial vision and low-latency motor microcontrollers.
2. Team VoltGrid (Runner-Up, ₹30,000 award): Smart micro-grid load balancer capable of predicting transformer thermal overloads using quantized edge neural networks.
3. Team NeuralCrop: Handheld diagnostic camera for early plant disease detection operating completely offline.

Jury Remarks:
Dr. S. Sharma commended SIET students for bridging theoretical control theory with robust, field-deployable hardware.
SIET Incubation Cell announced ₹500,000 in seed assistance for patenting and commercial scaling of the top 3 projects.
"""

async def run_orchestrator_trace():
    print("=" * 75)
    print("🚀 MASTER TRACE: ORCHESTRATOR AGENT (PLANNING -> GENERATION -> SCORING)")
    print("=" * 75)

    trace_summary = {}

    async with async_session_maker() as db:
        # ---------------------------------------------------------------------
        # PART 1: Pre-generation Planning Pass (Orchestrator Agent)
        # ---------------------------------------------------------------------
        print("\n--- [PART 1: PRE-GENERATION PLANNING PASS (ORCHESTRATOR)] ---")
        
        # Ensure active template exists
        stmt_tmpl = select(MagazineTemplate).where(MagazineTemplate.is_active == True)
        tmpl = (await db.execute(stmt_tmpl)).scalars().first()
        if not tmpl:
            tmpl = MagazineTemplate(
                name="Siet Magazine Template",
                is_active=True,
                section_schema=[
                    {"key": "title", "label": "Issue Title", "enabled": True},
                    {"key": "description", "label": "Executive Overview", "enabled": True},
                    {"key": "writeup", "label": "Featured Story", "enabled": True},
                    {"key": "toc_summary", "label": "TOC Summary", "enabled": True},
                ],
                style_rules={"tone": "authoritative, crisp, inspirational"},
            )
            db.add(tmpl)
            await db.commit()

        schema = tmpl.section_schema or []
        editorial_plan = await create_editorial_plan(
            source_text=REAL_DOCUMENT_TEXT,
            section_schema=schema,
            template_name=tmpl.name,
            event_name="SIET International Innovation Symposium 2026",
        )

        print(f"✓ Real Issue Title: \"{editorial_plan.get('real_issue_title')}\"")
        print(f"✓ Title Placement:  {editorial_plan.get('title_placement')}")
        print(f"✓ Visual Lead:       {editorial_plan.get('visual_lead_section')}")
        print(f"✓ Editorial Plan Sections:\n{json.dumps(editorial_plan.get('sections_plan'), indent=2)}")

        trace_summary["part1_plan"] = editorial_plan

        # ---------------------------------------------------------------------
        # PART 2 & 3: Plan-Conditioned Generation & Section Verification
        # ---------------------------------------------------------------------
        print("\n--- [PART 2 & 3: PLAN-CONDITIONED GENERATION & VERIFICATION] ---")
        
        pipeline_res = await run_orchestrated_magazine_pipeline(
            event_name="SIET International Innovation Symposium 2026",
            raw_notes=REAL_DOCUMENT_TEXT,
            template_name=tmpl.name,
            db=db,
            max_rework_rounds=2,
        )

        print("\n✓ Generated & Verified Sections:")
        sections = pipeline_res.get("sections", {})
        for sec_k, sinfo in sections.items():
            print(f"  • Section [{sec_k.upper()}]:")
            print(f"    - Content: \"{sinfo['content']}\"")
            print(f"    - Grounding Explanation: {sinfo['simple_explanation']}")

        trace_summary["part2_3_sections"] = {k: v["content"] for k, v in sections.items()}
        trace_summary["verifier_reports"] = pipeline_res.get("verifier_reports", {})

        # ---------------------------------------------------------------------
        # PART 4 & 5: Post-Generation Orchestrator Review & Rework Loop
        # ---------------------------------------------------------------------
        print("\n--- [PART 4 & 5: HOLISTIC DESIGN SCORING & REWORK LOOP] ---")
        
        orch_review = pipeline_res.get("orchestrator_review", {})
        orch_score = pipeline_res.get("orchestrator_score", 0.0)
        rework_rounds = pipeline_res.get("rework_rounds_performed", 0)
        final_status = pipeline_res.get("status", "draft")

        print(f"✓ Orchestrator Design Score: {orch_score} / 1.0")
        print(f"✓ Rework Rounds Performed:  {rework_rounds}")
        print(f"✓ Final Issue Status:        {final_status}")
        print(f"✓ Orchestrator Feedback:\n{json.dumps(orch_review.get('section_feedback'), indent=2)}")

        trace_summary["part4_5_review"] = {
            "orchestrator_score": orch_score,
            "rework_rounds_performed": rework_rounds,
            "final_status": final_status,
            "orchestrator_feedback": orch_review.get("section_feedback"),
        }

        # ---------------------------------------------------------------------
        # PART 6: Database Persistence & Output Render Trace
        # ---------------------------------------------------------------------
        print("\n--- [PART 6: DATABASE PERSISTENCE & OUTPUT SYNC] ---")

        slug = f"siet-symposium-orchestrated-{int(time.time())}"
        mag = Magazine(
            title=pipeline_res.get("magazine_issue_title"),
            slug=slug,
            description=pipeline_res.get("description"),
            event_name="SIET International Innovation Symposium 2026",
            publication_year=2026,
            status=final_status,
            is_featured=True,
            page_count=4,
            editorial_plan=editorial_plan,
            orchestrator_score=orch_score,
        )
        db.add(mag)
        await db.commit()
        await db.refresh(mag)

        pdf_path = compile_magazine_pdf(mag, [], [
            {"title": "OpenAI Unveils GPT-5 Multimodal Reasoning", "source_name": "AI Tech Daily", "published_at": "2026-08-30", "simple_explanation": "Breakthrough reasoning benchmark scores across STEM datasets."},
        ])

        print(f"✓ Saved Magazine Issue #{mag.id} to Database with `editorial_plan` & `orchestrator_score` ({mag.orchestrator_score}).")
        print(f"✓ Single-Source Web Flipbook URL: http://localhost:3000/magazine/{mag.slug}")
        print(f"✓ Downloadable PDF File Path:      {os.path.abspath(pdf_path)}")

        trace_summary["part6_output"] = {
            "magazine_id": mag.id,
            "magazine_slug": mag.slug,
            "persisted_score": mag.orchestrator_score,
            "editorial_plan_saved": bool(mag.editorial_plan),
            "web_viewer_url": f"http://localhost:3000/magazine/{mag.slug}",
            "compiled_pdf_path": os.path.abspath(pdf_path),
        }

        # ---------------------------------------------------------------------
        # CONSOLIDATED REPORT
        # ---------------------------------------------------------------------
        print("\n" + "=" * 75)
        print("📊 CONSOLIDATED ORCHESTRATOR TRACE REPORT")
        print("=" * 75)
        print(json.dumps(trace_summary, indent=2))
        print("=" * 75)
        print("✅ ORCHESTRATOR AGENT WORKFLOW COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_orchestrator_trace())
