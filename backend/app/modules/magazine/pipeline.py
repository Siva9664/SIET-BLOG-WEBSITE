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
