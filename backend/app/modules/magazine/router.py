"""
Extended Magazine Router with event-based upload flow.

Admin Endpoints:
  POST   /admin/magazine/create          - Create event magazine entry (no file yet)
  POST   /admin/magazine/{id}/cover      - Upload cover pages (images, max 2)
  POST   /admin/magazine/{id}/body       - Upload body content pages (images)
  POST   /admin/magazine/{id}/gallery    - Upload event gallery images (batch)
  POST   /admin/magazine/{id}/pdf        - Upload/replace full PDF (existing flow)
  POST   /admin/magazine/{id}/publish    - Publish draft
  POST   /admin/magazine/{id}/unpublish  - Unpublish to draft
  DELETE /admin/magazine/{id}            - Delete magazine
  GET    /admin/magazine                 - List all magazines (admin view)

Public Endpoints:
  GET    /magazine                       - All published (default: featured=true first)
  GET    /magazine/featured              - Only is_featured=True magazines (<90 days)
  GET    /magazine/archive               - is_featured=False magazines (>90 days, last 12 months)
  GET    /magazine/{slug}                - Single magazine reader view
"""
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form,
    HTTPException, Query, Request, UploadFile, status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.shared.responses.helpers import success
from app.modules.contract_helpers import (
    get_media_map, normalize_limit, normalize_page,
    paginated_payload, search_filter, serialize_magazine,
)
from app.modules.engagement.router import (
    bookmark_contract, bookmark_status_contract,
    like_contract, like_status_contract,
    unbookmark_contract, unlike_contract,
)
from app.modules.magazine.models import Magazine, MagazinePage, MagazineTOCEntry
from app.modules.magazine.pipeline import process_magazine_pdf
from app.modules.magazine.ai_service import (
    generate_full_magazine_content,
    generate_event_overview,
    generate_writeup_article,
    generate_gallery_captions,
    generate_toc_entry,
)
from app.shared.auth.dependencies import require_admin, require_super_admin
from app.shared.exceptions.custom import NotFoundException
from app.shared.types.content import ContentKind, MagazineType

UPLOAD_DIR = "uploads/magazines"
MAGAZINE_FEATURED_DAYS = 90

router = APIRouter(prefix="/magazine", tags=["Magazine"])
admin_router = APIRouter(prefix="/admin/magazine", tags=["Admin Magazine"])


def _current_user_id(request: Request) -> int | None:
    return int(request.state.user) if getattr(request.state, "user", None) else None


def slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s or f"event-{int(datetime.now().timestamp())}"


async def _unique_slug(db: AsyncSession, base: str) -> str:
    slug = base
    idx = 1
    while await db.scalar(select(func.count()).select_from(Magazine).where(Magazine.slug == slug)):
        slug = f"{base}-{idx}"
        idx += 1
    return slug


def _save_upload(file_bytes: bytes, ext: str, prefix: str = "img") -> str:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"{prefix}_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6]}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(file_bytes)
    return f"/{UPLOAD_DIR}/{filename}"


def _magazine_row(m: Magazine) -> dict:
    return {
        "id": str(m.id),
        "title": m.title,
        "slug": m.slug,
        "description": m.description,
        "eventName": m.event_name,
        "eventDate": m.event_date.isoformat() if m.event_date else None,
        "year": m.publication_year,
        "type": m.magazine_type.value if hasattr(m.magazine_type, "value") else str(m.magazine_type),
        "status": m.status,
        "isFeatured": m.is_featured,
        "featuredUntil": m.featured_until.isoformat() if m.featured_until else None,
        "pageCount": m.page_count,
        "pdfUrl": m.pdf_url,
        "coverImageUrl": m.cover_image_url,
        "coverPages": m.cover_pages or [],
        "bodyPages": m.body_pages or [],
        "galleryImages": m.gallery_images or [],
        "failureReason": m.failure_reason,
        "issueDate": (m.event_date or m.issue_date or m.created_at).isoformat(),
        "processedAt": m.processed_at.isoformat() if m.processed_at else None,
        "publishedAt": m.published_at.isoformat() if m.published_at else None,
        "createdAt": m.created_at.isoformat(),
    }


# ─── PUBLIC ENDPOINTS ─────────────────────────────────────────────────────────

async def _pub_query(
    db: AsyncSession, request: Request,
    page: int, limit: int,
    featured_only: bool = False,
    archive_only: bool = False,
    magazine_type: str | None = None,
    year: int | None = None,
    q: str | None = None,
):
    page = normalize_page(page)
    limit = normalize_limit(limit)

    base = (
        select(Magazine)
        .options(
            selectinload(Magazine.pages),
            selectinload(Magazine.toc_entries),
            selectinload(Magazine.achievements),
            selectinload(Magazine.project_links),
        )
        .where(Magazine.status == "published")
    )
    count_base = select(func.count()).select_from(Magazine).where(Magazine.status == "published")

    if featured_only:
        base = base.where(Magazine.is_featured == True)
        count_base = count_base.where(Magazine.is_featured == True)
    elif archive_only:
        # Archive: is_featured=False, within last 12 months
        cutoff_12m = datetime.now(timezone.utc) - timedelta(days=365)
        base = base.where(Magazine.is_featured == False).where(Magazine.published_at >= cutoff_12m)
        count_base = count_base.where(Magazine.is_featured == False).where(Magazine.published_at >= cutoff_12m)

    if magazine_type:
        try:
            mt = MagazineType(magazine_type.strip().lower())
            base = base.where(Magazine.magazine_type == mt)
            count_base = count_base.where(Magazine.magazine_type == mt)
        except ValueError:
            return paginated_payload([], page, limit, 0)

    if year:
        base = base.where(Magazine.publication_year == year)
        count_base = count_base.where(Magazine.publication_year == year)

    if q:
        pred = search_filter(Magazine, q)
        base = base.where(pred)
        count_base = count_base.where(pred)

    total = await db.scalar(count_base) or 0
    result = await db.execute(
        base.order_by(Magazine.is_featured.desc(), Magazine.published_at.desc().nullslast(), Magazine.id.desc())
        .offset((page - 1) * limit).limit(limit)
    )
    rows = list(result.scalars().all())
    media = await get_media_map(db)
    uid = _current_user_id(request)
    items = [await serialize_magazine(db, row, media=media, current_user_id=uid) for row in rows]
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
    return await _pub_query(db, request, page, limit, magazine_type=type, year=year, q=q)


@router.get("/featured")
async def list_featured_magazines(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Magazines published within last 90 days — shown in priority section."""
    return await _pub_query(db, request, page, limit, featured_only=True)


@router.get("/archive")
async def list_archive_magazines(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    year: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Magazine archive — is_featured=False, always retains last 12 months."""
    return await _pub_query(db, request, page, limit, archive_only=True, year=year)


@router.get("/type/{type}")
async def magazine_by_type(
    type: str, request: Request,
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await _pub_query(db, request, page, limit, magazine_type=type)


@router.get("/year/{year}")
async def magazine_by_year(
    year: int, request: Request,
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await _pub_query(db, request, page, limit, year=year)


@router.get("/{slug_or_id}")
async def get_magazine_by_slug_or_id(slug_or_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    query = select(Magazine).options(
        selectinload(Magazine.pages), selectinload(Magazine.toc_entries),
        selectinload(Magazine.achievements), selectinload(Magazine.project_links),
    )
    query = query.where(Magazine.id == int(slug_or_id)) if slug_or_id.isdigit() else query.where(Magazine.slug == slug_or_id)
    row = (await db.execute(query)).scalars().first()
    if not row:
        raise NotFoundException("Magazine item not found.")
    return await serialize_magazine(db, row, current_user_id=_current_user_id(request))


# Engagement endpoints
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


# ─── ADMIN ENDPOINTS ──────────────────────────────────────────────────────────

@admin_router.get("")
async def admin_list_magazines(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    query = select(Magazine).options(
        selectinload(Magazine.pages), selectinload(Magazine.toc_entries),
    ).order_by(Magazine.id.desc())
    rows = list((await db.execute(query)).scalars().all())
    return [_magazine_row(m) for m in rows]


@admin_router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_event_magazine(
    event_name: str = Form(...),
    title: str = Form(...),
    description: str = Form(None),
    event_date: str = Form(None),          # ISO date string e.g. 2026-08-14
    magazine_type: str = Form("special"),
    publication_year: int = Form(datetime.now().year),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Step 1: Create a new event magazine entry. No file required yet."""
    slug = await _unique_slug(db, slugify(title))
    try:
        mt = MagazineType(magazine_type.lower())
    except ValueError:
        mt = MagazineType.SPECIAL

    parsed_event_date = None
    if event_date:
        try:
            parsed_event_date = datetime.fromisoformat(event_date).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    mag = Magazine(
        title=title.strip(),
        slug=slug,
        description=description.strip() if description else None,
        event_name=event_name.strip(),
        event_date=parsed_event_date,
        magazine_type=mt,
        publication_year=publication_year,
        issue_date=parsed_event_date or datetime.now(timezone.utc),
        status="draft",
        is_featured=True,
        featured_until=datetime.now(timezone.utc) + timedelta(days=MAGAZINE_FEATURED_DAYS),
        cover_pages=[],
        body_pages=[],
        gallery_images=[],
    )
    db.add(mag)
    await db.commit()
    await db.refresh(mag)
    return {"message": "Event magazine created.", "id": str(mag.id), "slug": mag.slug, "status": mag.status}


@admin_router.post("/{magazine_id}/cover")
async def upload_cover_pages(
    magazine_id: int,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Upload up to 2 intro/cover page images. Replaces any existing cover pages."""
    mag = await db.get(Magazine, magazine_id)
    if not mag:
        raise NotFoundException("Magazine not found.")
    if len(files) > 2:
        raise HTTPException(status_code=400, detail="Cover pages are limited to 2 images.")

    saved = []
    for f in files:
        raw = await f.read()
        if len(raw) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Each image must be under 10MB.")
        ext = os.path.splitext(f.filename or "cover.jpg")[1].lower() or ".jpg"
        url = _save_upload(raw, ext, prefix=f"cover_{magazine_id}")
        saved.append({"url": url, "caption": f.filename})

    mag.cover_pages = saved
    if saved:
        mag.cover_image_url = saved[0]["url"]
    await db.commit()
    return {"message": f"Saved {len(saved)} cover page(s).", "coverPages": saved}


@admin_router.post("/{magazine_id}/body")
async def upload_body_pages(
    magazine_id: int,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Upload body content pages (images). Appends to existing body pages."""
    mag = await db.get(Magazine, magazine_id)
    if not mag:
        raise NotFoundException("Magazine not found.")

    existing = list(mag.body_pages or [])
    for f in files:
        raw = await f.read()
        if len(raw) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Each image must be under 10MB.")
        ext = os.path.splitext(f.filename or "page.jpg")[1].lower() or ".jpg"
        url = _save_upload(raw, ext, prefix=f"body_{magazine_id}")
        existing.append({"url": url, "caption": f.filename})

    mag.body_pages = existing
    mag.page_count = len(mag.cover_pages or []) + len(existing) + len(mag.gallery_images or [])
    await db.commit()
    return {"message": f"Added {len(files)} body page(s). Total body pages: {len(existing)}.", "bodyPages": existing}


@admin_router.post("/{magazine_id}/gallery")
async def upload_gallery_images(
    magazine_id: int,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Batch upload event photos. Auto-appended as the final gallery section."""
    mag = await db.get(Magazine, magazine_id)
    if not mag:
        raise NotFoundException("Magazine not found.")

    existing = list(mag.gallery_images or [])
    for f in files:
        raw = await f.read()
        if len(raw) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Each image must be under 10MB.")
        ext = os.path.splitext(f.filename or "photo.jpg")[1].lower() or ".jpg"
        url = _save_upload(raw, ext, prefix=f"gallery_{magazine_id}")
        existing.append({"url": url, "caption": f.filename})

    mag.gallery_images = existing
    mag.page_count = len(mag.cover_pages or []) + len(mag.body_pages or []) + len(existing)
    await db.commit()
    return {"message": f"Added {len(files)} gallery image(s). Total gallery: {len(existing)}.", "galleryImages": existing}


@admin_router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_magazine_issue(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    description: str = Form(None),
    publication_year: int = Form(datetime.now().year),
    magazine_type: str = Form("special"),
    event_name: str = Form(None),
    event_date: str = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_super_admin),
):
    """Upload a full PDF directly — existing flow extended with event fields."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a PDF document.")

    file_bytes = await file.read()
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF exceeds maximum 50MB.")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    pdf_filename = f"issue_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6]}.pdf"
    pdf_save_path = os.path.join(UPLOAD_DIR, pdf_filename)
    with open(pdf_save_path, "wb") as f:
        f.write(file_bytes)

    slug = await _unique_slug(db, slugify(title))
    try:
        mt = MagazineType(magazine_type.lower())
    except ValueError:
        mt = MagazineType.SPECIAL

    parsed_event_date = None
    if event_date:
        try:
            parsed_event_date = datetime.fromisoformat(event_date).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    mag = Magazine(
        title=title.strip(),
        slug=slug,
        description=description.strip() if description else None,
        event_name=event_name.strip() if event_name else None,
        event_date=parsed_event_date,
        publication_year=publication_year,
        magazine_type=mt,
        pdf_url=f"/{UPLOAD_DIR}/{pdf_filename}",
        issue_date=parsed_event_date or datetime.now(timezone.utc),
        status="processing",
        is_featured=True,
        featured_until=datetime.now(timezone.utc) + timedelta(days=MAGAZINE_FEATURED_DAYS),
        cover_pages=[],
        body_pages=[],
        gallery_images=[],
    )
    db.add(mag)
    await db.commit()
    await db.refresh(mag)

    background_tasks.add_task(process_magazine_pdf, mag.id, pdf_save_path)
    return {
        "message": "Magazine uploaded. Background PDF processing started.",
        "id": str(mag.id), "slug": mag.slug, "status": mag.status,
    }


@admin_router.post("/{magazine_id}/publish")
async def publish_magazine(
    magazine_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Publish a draft magazine. Sets status=published and stamps published_at."""
    mag = await db.get(Magazine, magazine_id)
    if not mag:
        raise NotFoundException("Magazine not found.")

    now = datetime.now(timezone.utc)
    mag.status = "published"
    mag.published_at = now
    mag.is_featured = True
    mag.featured_until = now + timedelta(days=MAGAZINE_FEATURED_DAYS)
    await db.commit()
    return {"message": "Magazine published.", "id": str(mag.id), "isFeatured": mag.is_featured}


@admin_router.post("/{magazine_id}/unpublish")
async def unpublish_magazine(
    magazine_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Unpublish a magazine back to draft."""
    mag = await db.get(Magazine, magazine_id)
    if not mag:
        raise NotFoundException("Magazine not found.")
    mag.status = "draft"
    mag.is_featured = False
    await db.commit()
    return {"message": "Magazine unpublished.", "id": str(mag.id)}


@admin_router.post("/{magazine_id}/replace-pdf")
async def replace_magazine_pdf(
    magazine_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_super_admin),
):
    mag = await db.get(Magazine, magazine_id)
    if not mag:
        raise NotFoundException("Magazine issue not found.")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a PDF document.")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    pdf_filename = f"issue_{magazine_id}_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6]}.pdf"
    pdf_save_path = os.path.join(UPLOAD_DIR, pdf_filename)
    file_bytes = await file.read()
    with open(pdf_save_path, "wb") as f:
        f.write(file_bytes)

    mag.pdf_url = f"/{UPLOAD_DIR}/{pdf_filename}"
    mag.status = "processing"
    mag.failure_reason = None
    await db.commit()
    background_tasks.add_task(process_magazine_pdf, mag.id, pdf_save_path)
    return {"message": f"PDF replaced for magazine #{magazine_id}. Background processing re-started.", "id": str(mag.id)}


@admin_router.delete("/{magazine_id}")
async def delete_magazine_issue(
    magazine_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_super_admin),
):
    mag = await db.get(Magazine, magazine_id)
    if not mag:
        raise NotFoundException("Magazine issue not found.")
    await db.delete(mag)
    await db.commit()
    return {"message": "Magazine issue deleted successfully."}


# ─── AI ASSISTANT ENDPOINTS ───────────────────────────────────────────────────

class AIFullAutoGenerateRequest(BaseModel):
    event_name: str
    event_date: str = ""
    raw_notes: str
    photo_count: int = 0


class AIOverviewRequest(BaseModel):
    raw_notes: str
    event_name: str = ""
    event_date: str = ""


class AIArticleRequest(BaseModel):
    raw_notes: str
    event_name: str = ""


class PhotoNote(BaseModel):
    id: str
    notes: str = ""


class AICaptionsRequest(BaseModel):
    event_name: str = ""
    event_description: str = ""
    photos: list[PhotoNote] = []


class AITocRequest(BaseModel):
    title: str
    description: str = ""


@admin_router.post("/ai/auto-generate")
async def api_auto_generate_full(
    payload: AIFullAutoGenerateRequest,
    current_user=Depends(require_admin),
):
    """
    ONE-CLICK AI AUTO-FILL:
    Generates magazine_issue_title, description, writeup, captions, and toc_summary in 1 call.
    """
    res = await generate_full_magazine_content(
        event_name=payload.event_name,
        event_date=payload.event_date,
        raw_notes=payload.raw_notes,
        photo_count=payload.photo_count,
    )
    return success(res)


@admin_router.post("/ai/generate-overview")
async def api_generate_overview(
    payload: AIOverviewRequest,
    current_user=Depends(require_admin),
):
    overview = await generate_event_overview(
        raw_notes=payload.raw_notes,
        event_name=payload.event_name,
        event_date=payload.event_date,
    )
    return success({"overview": overview})


@admin_router.post("/ai/generate-article")
async def api_generate_article(
    payload: AIArticleRequest,
    current_user=Depends(require_admin),
):
    res = await generate_writeup_article(
        raw_notes=payload.raw_notes,
        event_name=payload.event_name,
    )
    return success(res)


@admin_router.post("/ai/generate-captions")
async def api_generate_captions(
    payload: AICaptionsRequest,
    current_user=Depends(require_admin),
):
    photos_input = [{"id": p.id, "notes": p.notes} for p in payload.photos]
    captions = await generate_gallery_captions(
        event_name=payload.event_name,
        event_description=payload.event_description,
        photos=photos_input,
    )
    return success({"captions": captions})


@admin_router.post("/ai/generate-toc")
async def api_generate_toc(
    payload: AITocRequest,
    current_user=Depends(require_admin),
):
    toc_summary = await generate_toc_entry(
        title=payload.title,
        description=payload.description,
    )
    return success({"toc_summary": toc_summary})


