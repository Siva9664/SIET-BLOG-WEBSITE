import asyncio
import os
import fitz  # PyMuPDF
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import async_session_maker
from app.modules.media.models import Media
from app.modules.magazine.models import Magazine, MagazinePage, MagazineTOCEntry
from app.modules.magazine.pipeline import process_magazine_pdf


def create_sample_pdf(file_path: str, num_pages: int = 3, title_prefix: str = "SIET Tech Digest"):
    """Create a sample multi-page PDF document using PyMuPDF."""
    doc = fitz.open()
    
    headers = [
        "SIET TECH DIGEST — AUGUST 2026 EDITION\nAnnual Technical Report and Campus Research Review",
        "ARTIFICIAL INTELLIGENCE RESEARCH HIGHLIGHTS\nQuantum Edge Computing and LLM Quantization Models",
        "DEPARTMENT INNOVATION AND STUDENT AWARDS\nSmart India Hackathon First Place National Victory",
        "ROBOTICS & EMBEDDED SYSTEMS SPOTLIGHT\nAutonomous Warehouse Steering and RTOS Controllers",
    ]
    
    for i in range(num_pages):
        page = doc.new_page(width=595, height=842)  # A4 size
        header_text = headers[i % len(headers)]
        rect = fitz.Rect(50, 50, 545, 792)
        
        content = f"{title_prefix}\n\nPage {i + 1} of {num_pages}\n\n{header_text}\n\n"
        content += "Sri Shakthi Institute of Engineering & Technology (SIET), Autonomous Institution.\n"
        content += "This issue showcases interdisciplinary student innovations, peer-reviewed journal papers, and faculty laboratory updates.\n"
        
        page.insert_textbox(rect, content, fontsize=14, fontname="helv", align=0)
        
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    doc.save(file_path)
    doc.close()
    print(f"Created sample PDF at {file_path} with {num_pages} pages.")


async def main():
    print("=== Testing Magazine PDF Ingestion & Replacement Pipeline ===")
    
    pdf1_path = "uploads/test_issue_v1.pdf"
    pdf2_path = "uploads/test_issue_v2.pdf"
    
    create_sample_pdf(pdf1_path, num_pages=3, title_prefix="SIET Tech Digest Vol 1")
    create_sample_pdf(pdf2_path, num_pages=4, title_prefix="SIET Tech Digest Vol 1 (Updated)")
    
    async with async_session_maker() as session:
        # Create test magazine issue
        mag = Magazine(
            title="SIET Tech Digest — August 2026",
            slug="siet-tech-digest-august-2026-test",
            description="Official monthly tech newsletter issue.",
            publication_year=2026,
            magazine_type="monthly",
            pdf_url="/uploads/test_issue_v1.pdf",
            status="processing",
        )
        session.add(mag)
        await session.commit()
        await session.refresh(mag)
        mag_id = mag.id
        print(f"Created Magazine Issue #{mag_id} in database.")

    # 1. Run Initial Pipeline
    await process_magazine_pdf(mag_id, pdf1_path)

    async with async_session_maker() as session:
        res = await session.execute(
            select(Magazine)
            .options(selectinload(Magazine.pages), selectinload(Magazine.toc_entries))
            .where(Magazine.id == mag_id)
        )
        mag = res.scalars().first()
        
        print(f"\n--- Initial Pipeline Verification ---")
        print(f"Status: {mag.status}")
        print(f"Page Count: {mag.page_count}")
        print(f"Cover Image URL: {mag.cover_image_url}")
        print(f"Rendered Pages in DB: {len(mag.pages)}")
        print(f"TOC Entries in DB: {len(mag.toc_entries)}")
        
        assert mag.status == "published", f"Expected status published, got {mag.status}"
        assert mag.page_count == 3, f"Expected 3 pages, got {mag.page_count}"
        assert len(mag.pages) == 3, f"Expected 3 page rows, got {len(mag.pages)}"
        assert len(mag.toc_entries) == 3, f"Expected 3 TOC entries, got {len(mag.toc_entries)}"
        
        for p in mag.pages:
            print(f"  Page #{p.page_number}: image={p.image_url}, text_len={len(p.extracted_text or '')}")
            assert os.path.exists(p.image_url.lstrip("/")), f"Image file missing on disk: {p.image_url}"
            
        for t in mag.toc_entries:
            print(f"  TOC #{t.page_number}: heading='{t.heading}'")

    # 2. Test PDF Replacement Pipeline
    print(f"\n--- Testing PDF Replacement Pipeline (4 pages) ---")
    await process_magazine_pdf(mag_id, pdf2_path)

    async with async_session_maker() as session:
        res = await session.execute(
            select(Magazine)
            .options(selectinload(Magazine.pages), selectinload(Magazine.toc_entries))
            .where(Magazine.id == mag_id)
        )
        mag = res.scalars().first()
        
        print(f"Status after replacement: {mag.status}")
        print(f"Updated Page Count: {mag.page_count}")
        print(f"Updated Pages in DB: {len(mag.pages)}")
        print(f"Updated TOC Entries in DB: {len(mag.toc_entries)}")
        
        assert mag.status == "published", f"Expected status published, got {mag.status}"
        assert mag.page_count == 4, f"Expected 4 pages, got {mag.page_count}"
        assert len(mag.pages) == 4, f"Expected 4 page rows, got {len(mag.pages)}"
        assert len(mag.toc_entries) == 4, f"Expected 4 TOC entries, got {len(mag.toc_entries)}"

    print("\n✅ ALL MAGAZINE PIPELINE VERIFICATIONS PASSED PERFECTLY!")


if __name__ == "__main__":
    asyncio.run(main())
