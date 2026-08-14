import os
import re
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.modules.contract_helpers import (
    get_media_map,
    normalize_limit,
    normalize_page,
    paginated_payload,
    search_filter,
    serialize_magazine,
)
from app.modules.engagement.router import (
    bookmark_contract,
    bookmark_status_contract,
    like_contract,
    like_status_contract,
    unbookmark_contract,
    unlike_contract,
)
from app.modules.magazine.models import Magazine, MagazinePage, MagazineTOCEntry
from app.modules.magazine.pipeline import process_magazine_pdf
from app.shared.auth.dependencies import require_admin, require_super_admin
from app.shared.exceptions.custom import NotFoundException
from app.shared.types.content import ContentKind, ContentStatus, MagazineType

router = APIRouter(prefix="/magazine", tags=["Magazine"])
admin_router = APIRouter(prefix="/admin/magazine", tags=["Admin Magazine"])


def _current_user_id(request: Request) -> int | None:
    return int(request.state.user) if getattr(request.state, "user", None) else None


def slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s or f"issue-{int(datetime.now().timestamp())}"


async def _magazine_page(
    db: AsyncSession,
    request: Request,
    page: int,
    limit: int,
    magazine_type: str | None = None,
    year: int | None = None,
    q: str | None = None,
):
    page = normalize_page(page)
    limit = normalize_limit(limit)
    
    # Show published issues for public
    pub_statuses = ["published", ContentStatus.PUBLISHED]
    query = (
        select(Magazine)
        .options(
            selectinload(Magazine.pages),
            selectinload(Magazine.toc_entries),
            selectinload(Magazine.achievements),
            selectinload(Magazine.project_links),
        )
        .where(Magazine.status.in_(pub_statuses))
    )
    count_query = select(func.count()).select_from(Magazine).where(Magazine.status.in_(pub_statuses))

    if magazine_type:
        target = magazine_type.strip().lower()
        NATIVE_DB_TYPES = {"monthly", "quarterly", "annual", "special"}
        if target in NATIVE_DB_TYPES:
            matched_enum = MagazineType(target)
            query = query.where(Magazine.magazine_type == matched_enum)
            count_query = count_query.where(Magazine.magazine_type == matched_enum)
        else:
            return paginated_payload([], page, limit, 0)

    if year:
        query = query.where(Magazine.publication_year == year)
        count_query = count_query.where(Magazine.publication_year == year)

    if q:
        predicate = search_filter(Magazine, q)
        query = query.where(predicate)
        count_query = count_query.where(predicate)

    total = await db.scalar(count_query) or 0
    result = await db.execute(
        query.order_by(Magazine.published_at.desc().nullslast(), Magazine.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = list(result.scalars().all())
    media = await get_media_map(db)
    items = [await serialize_magazine(db, row, media=media, current_user_id=_current_user_id(request)) for row in rows]
    return paginated_payload(items, page, limit, total)


@router.get("")
async def list_magazine(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    q: str | None = None,
    type: str | None = None,
    year: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await _magazine_page(db, request, page, limit, magazine_type=type, year=year, q=q)


@router.get("/type/{type}")
async def magazine_by_type(
    type: str,
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await _magazine_page(db, request, page, limit, magazine_type=type)


@router.get("/year/{year}")
async def magazine_by_year(
    year: int,
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await _magazine_page(db, request, page, limit, year=year)


@router.get("/{slug_or_id}")
async def get_magazine_by_slug_or_id(slug_or_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    query = (
        select(Magazine)
        .options(
            selectinload(Magazine.pages),
            selectinload(Magazine.toc_entries),
            selectinload(Magazine.achievements),
            selectinload(Magazine.project_links),
        )
    )
    if slug_or_id.isdigit():
        query = query.where(Magazine.id == int(slug_or_id))
    else:
        query = query.where(Magazine.slug == slug_or_id)

    row = (await db.execute(query)).scalars().first()
    if not row:
        raise NotFoundException("Magazine item not found.")
    return await serialize_magazine(db, row, current_user_id=_current_user_id(request))


@router.get("/{slug}/like/status")
async def magazine_like_status(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await like_status_contract(db, request, Magazine, slug, ContentKind.MAGAZINE)


@router.post("/{slug}/like")
async def magazine_like(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await like_contract(db, request, Magazine, slug, ContentKind.MAGAZINE)


@router.delete("/{slug}/like")
async def magazine_unlike(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await unlike_contract(db, request, Magazine, slug, ContentKind.MAGAZINE)


@router.get("/{slug}/bookmark/status")
async def magazine_bookmark_status(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await bookmark_status_contract(db, request, Magazine, slug, ContentKind.MAGAZINE)


@router.post("/{slug}/bookmark")
async def magazine_bookmark(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await bookmark_contract(db, request, Magazine, slug, ContentKind.MAGAZINE)


@router.delete("/{slug}/bookmark")
async def magazine_unbookmark(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await unbookmark_contract(db, request, Magazine, slug, ContentKind.MAGAZINE)


# ─── ADMIN MAGAZINE ENDPOINTS ──────────────────────────────────────────────────

@admin_router.get("")
async def admin_list_magazines(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    query = select(Magazine).options(
        selectinload(Magazine.pages),
        selectinload(Magazine.toc_entries),
    ).order_by(Magazine.id.desc())
    rows = list((await db.execute(query)).scalars().all())
    return [
        {
            "id": str(m.id),
            "title": m.title,
            "slug": m.slug,
            "description": m.description,
            "year": m.publication_year,
            "type": m.magazine_type.value if hasattr(m.magazine_type, "value") else str(m.magazine_type),
            "status": m.status,
            "pageCount": m.page_count,
            "pdfUrl": m.pdf_url,
            "coverImageUrl": m.cover_image_url,
            "failureReason": m.failure_reason,
            "issueDate": m.issue_date.isoformat() if m.issue_date else m.created_at.isoformat(),
            "processedAt": m.processed_at.isoformat() if m.processed_at else None,
            "createdAt": m.created_at.isoformat(),
        }
        for m in rows
    ]


@admin_router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_magazine_issue(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    description: str = Form(None),
    publication_year: int = Form(datetime.now().year),
    magazine_type: str = Form("monthly"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_super_admin),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a PDF document.")

    file_bytes = await file.read()
    max_pdf_bytes = 50 * 1024 * 1024  # 50 MB
    if len(file_bytes) > max_pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded PDF exceeds maximum allowed size of 50 MB.")

    os.makedirs("uploads/magazines", exist_ok=True)
    pdf_filename = f"issue_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6]}.pdf"
    pdf_save_path = os.path.join("uploads", "magazines", pdf_filename)

    with open(pdf_save_path, "wb") as f:
        f.write(file_bytes)

    base_slug = slugify(title)
    slug = base_slug
    idx = 1
    while await db.scalar(select(func.count()).select_from(Magazine).where(Magazine.slug == slug)):
        slug = f"{base_slug}-{idx}"
        idx += 1

    try:
        mag_type_enum = MagazineType(magazine_type.lower())
    except ValueError:
        mag_type_enum = MagazineType.MONTHLY

    magazine = Magazine(
        title=title.strip(),
        slug=slug,
        description=description.strip() if description else None,
        publication_year=publication_year,
        magazine_type=mag_type_enum,
        pdf_url=f"/uploads/magazines/{pdf_filename}",
        status="processing",
        issue_date=datetime.now(timezone.utc),
    )
    db.add(magazine)
    await db.commit()
    await db.refresh(magazine)

    # Trigger async background PDF processing pipeline
    background_tasks.add_task(process_magazine_pdf, magazine.id, pdf_save_path)

    return {
        "message": "Magazine issue uploaded successfully. Background PDF page extraction & TOC generation started.",
        "id": str(magazine.id),
        "slug": magazine.slug,
        "status": magazine.status,
    }


@admin_router.post("/{magazine_id}/replace-pdf")
async def replace_magazine_pdf(
    magazine_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_super_admin),
):
    magazine = await db.get(Magazine, magazine_id)
    if not magazine:
        raise NotFoundException("Magazine issue not found.")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a PDF document.")

    os.makedirs("uploads/magazines", exist_ok=True)
    pdf_filename = f"issue_{magazine_id}_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6]}.pdf"
    pdf_save_path = os.path.join("uploads", "magazines", pdf_filename)

    file_bytes = await file.read()
    with open(pdf_save_path, "wb") as f:
        f.write(file_bytes)

    magazine.pdf_url = f"/uploads/magazines/{pdf_filename}"
    magazine.status = "processing"
    magazine.failure_reason = None
    await db.commit()

    # Re-trigger pipeline for replacement
    background_tasks.add_task(process_magazine_pdf, magazine.id, pdf_save_path)

    return {
        "message": f"PDF replaced for magazine issue #{magazine_id}. Background processing re-started.",
        "id": str(magazine.id),
        "status": magazine.status,
    }


@admin_router.delete("/{magazine_id}")
async def delete_magazine_issue(
    magazine_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_super_admin),
):
    magazine = await db.get(Magazine, magazine_id)
    if not magazine:
        raise NotFoundException("Magazine issue not found.")

    await db.delete(magazine)
    await db.commit()
    return {"message": "Magazine issue deleted successfully."}
