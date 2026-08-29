from datetime import datetime, timezone
import os
import re
import fitz  # PyMuPDF
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.core.logging import logger
from app.modules.magazine.models import Magazine, MagazinePage, MagazineTOCEntry


def extract_page_heading(text: str, page_num: int) -> str:
    """Extract a grounded short heading from a magazine page text."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    # Ignore generic headers like page numbers or 'SIET TECH DIGEST'
    filtered = []
    for line in lines:
        clean = line.strip()
        if len(clean) > 3 and not re.match(r"^(page|\d+|siet|volume|issue|digest)", clean, re.IGNORECASE):
            filtered.append(clean)
            
    if filtered:
        heading = filtered[0]
        if len(heading) > 80:
            heading = heading[:77] + "..."
        return heading
        
    return f"Page {page_num} Overview"


async def process_magazine_pdf(magazine_id: int, pdf_path: str):
    """
    Background worker that renders PDF pages as images, extracts text,
    generates grounded TOC entries, and updates the magazine issue record.
    """
    logger.info(f"Starting PDF processing for magazine_id={magazine_id}, path={pdf_path}")
    
    async with async_session_maker() as session:
        magazine = await session.get(Magazine, magazine_id)
        if not magazine:
            logger.error(f"Magazine issue #{magazine_id} not found in database.")
            return

        try:
            # Mark processing
            magazine.status = "processing"
            magazine.failure_reason = None
            await session.commit()

            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"PDF file not found at {pdf_path}")

            # Open PDF document with PyMuPDF
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            logger.info(f"Loaded PDF with {total_pages} pages.")

            if total_pages == 0:
                raise ValueError("PDF document contains 0 pages.")

            # Replace-in-place: Delete old pages and TOC entries if re-processing
            await session.execute(delete(MagazinePage).where(MagazinePage.magazine_id == magazine_id))
            await session.execute(delete(MagazineTOCEntry).where(MagazineTOCEntry.magazine_id == magazine_id))
            await session.commit()

            os.makedirs("uploads/magazines", exist_ok=True)

            pages_to_create = []
            toc_to_create = []
            cover_image_url = None

            for i in range(total_pages):
                page_num = i + 1
                page = doc[i]

                # 1. Render page to high-res PNG image (150 DPI produces ~1200-1600px width)
                pix = page.get_pixmap(dpi=150)
                image_filename = f"mag_{magazine_id}_p{page_num}_{int(datetime.now().timestamp())}.png"
                image_rel_path = f"/uploads/magazines/{image_filename}"
                image_full_path = os.path.join("uploads", "magazines", image_filename)
                
                pix.save(image_full_path)

                if page_num == 1:
                    cover_image_url = image_rel_path

                # 2. Extract page raw text
                extracted_text = page.get_text("text") or ""

                # 3. Create MagazinePage row
                pages_to_create.append(
                    MagazinePage(
                        magazine_id=magazine_id,
                        page_number=page_num,
                        image_url=image_rel_path,
                        extracted_text=extracted_text,
                    )
                )

                # 4. Generate TOC entry for this page
                heading = extract_page_heading(extracted_text, page_num)
                toc_to_create.append(
                    MagazineTOCEntry(
                        magazine_id=magazine_id,
                        page_number=page_num,
                        heading=heading,
                    )
                )

            # Bulk save pages & TOC entries
            session.add_all(pages_to_create)
            session.add_all(toc_to_create)

            # Update Magazine record
            magazine.page_count = total_pages
            magazine.cover_image_url = cover_image_url
            magazine.status = "published"
            magazine.processed_at = datetime.now(timezone.utc)
            magazine.published_at = datetime.now(timezone.utc)

            await session.commit()
            logger.info(f"Successfully processed magazine #{magazine_id} ({total_pages} pages).")

        except Exception as e:
            logger.error(f"Error processing magazine PDF #{magazine_id}: {e}", exc_info=True)
            await session.rollback()
            magazine.status = "failed"
            magazine.failure_reason = str(e)
            await session.commit()


def compile_magazine_pdf(magazine: Magazine, pages: list[MagazinePage], ai_news: list[dict]) -> str:
    """
    Compiles full magazine issue into a single downloadable PDF including all pages
    and the 'Latest in AI' closing section. Caches result in uploads/magazines/generated/{slug}_full.pdf.
    """
    os.makedirs("uploads/magazines/generated", exist_ok=True)
    target_path = f"uploads/magazines/generated/{magazine.slug}_full.pdf"

    # Return cached PDF if already exists
    if os.path.exists(target_path):
        return target_path

    out_doc = fitz.open()

    # 1. Check if source PDF exists
    source_pdf_path = None
    if magazine.pdf_url:
        clean_url = magazine.pdf_url.lstrip("/")
        if os.path.exists(clean_url):
            source_pdf_path = clean_url

    if source_pdf_path:
        try:
            src = fitz.open(source_pdf_path)
            out_doc.insert_pdf(src)
            src.close()
        except Exception as e:
            logger.warning(f"Could not open source PDF {source_pdf_path}: {e}")

    # 2. If no source PDF or source PDF failed, compile from page images / text
    if len(out_doc) == 0 and pages:
        sorted_pages = sorted(pages, key=lambda p: p.page_number)
        for p in sorted_pages:
            img_rel = (p.image_url or "").lstrip("/")
            if img_rel and os.path.exists(img_rel):
                try:
                    img_doc = fitz.open(img_rel)
                    pdf_bytes = img_doc.convert_to_pdf()
                    img_doc.close()
                    img_pdf = fitz.open("pdf", pdf_bytes)
                    out_doc.insert_pdf(img_pdf)
                    img_pdf.close()
                except Exception as e:
                    logger.warning(f"Could not convert page image {img_rel} to PDF page: {e}")
            elif p.extracted_text:
                page = out_doc.new_page(width=595, height=842)
                page.insert_textbox(fitz.Rect(40, 40, 555, 800), p.extracted_text, fontsize=11, fontname="helv")

    # 3. If still empty, create title cover page
    if len(out_doc) == 0:
        cover_page = out_doc.new_page(width=595, height=842)
        cover_page.insert_textbox(fitz.Rect(40, 100, 555, 180), magazine.title, fontsize=24, fontname="helv", color=(0.1, 0.1, 0.1))
        if magazine.description:
            cover_page.insert_textbox(fitz.Rect(40, 190, 555, 300), magazine.description, fontsize=12, fontname="helv", color=(0.3, 0.3, 0.3))

    # 4. Append 'Latest in AI' Closing Section Page
    if ai_news:
        ai_page = out_doc.new_page(width=595, height=842)
        
        # Header banner
        ai_page.draw_rect(fitz.Rect(40, 40, 555, 42), color=(0.1, 0.1, 0.1), fill=(0.1, 0.1, 0.1))
        ai_page.insert_textbox(fitz.Rect(40, 55, 555, 80), "CLOSING FEATURE: LATEST IN AI", fontsize=16, fontname="helv", color=(0.85, 0.15, 0.15))
        ai_page.insert_textbox(fitz.Rect(40, 82, 555, 100), "Curated Artificial Intelligence News & Research Summary", fontsize=10, fontname="helv", color=(0.4, 0.4, 0.4))
        ai_page.draw_line(fitz.Point(40, 105), fitz.Point(555, 105), color=(0.8, 0.8, 0.8), width=1)

        y_offset = 120
        for idx, news in enumerate(ai_news[:5]):
            if y_offset + 110 > 800:
                ai_page = out_doc.new_page(width=595, height=842)
                y_offset = 50

            source_name = news.get("source_name", "SIET Tech News").upper()
            pub_date = str(news.get("published_at", ""))[:10]
            source_line = f"#{idx+1}  ·  {source_name}  ·  {pub_date}"
            ai_page.insert_textbox(fitz.Rect(40, y_offset, 555, y_offset + 15), source_line, fontsize=9, fontname="helv", color=(0.7, 0.2, 0.2))
            
            title = news.get("title", "")
            ai_page.insert_textbox(fitz.Rect(40, y_offset + 16, 555, y_offset + 42), title, fontsize=12, fontname="helv", color=(0.1, 0.1, 0.1))
            
            summary = news.get("simple_explanation", "")
            if summary:
                ai_page.insert_textbox(fitz.Rect(40, y_offset + 44, 555, y_offset + 85), summary, fontsize=9.5, fontname="helv", color=(0.3, 0.3, 0.3))

            y_offset += 95
            ai_page.draw_line(fitz.Point(40, y_offset - 8), fitz.Point(555, y_offset - 8), color=(0.9, 0.9, 0.9), width=0.5)

    out_doc.save(target_path)
    out_doc.close()
    return target_path

