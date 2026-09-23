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
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel
from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form,
    HTTPException, Query, Request, UploadFile, status,
)
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.logging import logger
from app.shared.responses.helpers import success
from app.modules.contract_helpers import (
    get_media_map, get_top_ai_news, normalize_limit, normalize_page,
    paginated_payload, search_filter, serialize_magazine,
)
from app.modules.engagement.router import (
    bookmark_contract, bookmark_status_contract,
    like_contract, like_status_contract,
    unbookmark_contract, unlike_contract,
)
from app.modules.magazine.models import (
    Magazine, MagazinePage, MagazineTOCEntry,
    MagazineTemplate, TemplateVersion, TemplatePage, TemplateRegion,
    DEFAULT_SECTION_SCHEMA, DEFAULT_STYLE_RULES,
)
from app.modules.magazine.visual_analyzer import analyze_template_pdf_visual_blueprint
from app.modules.magazine.renderer import render_magazine_pdf_from_blueprint
from app.modules.magazine.generation_pipeline import MagazineGenerationPipeline
from app.modules.magazine.event_segmenter import segment_document_events
from app.modules.magazine.photo_associator import PhotoAssociator
from app.modules.magazine.templates.siet_default_v1 import get_siet_default_v1_template
from app.modules.magazine.pipeline import compile_magazine_pdf, process_magazine_pdf
from app.modules.magazine.ai_service import (
    generate_full_magazine_content,
    generate_grounded_magazine_content,
    generate_event_overview,
    generate_writeup_article,
    generate_gallery_captions,
    generate_toc_entry,
)
from app.modules.magazine.file_parser import parse_event_file, parse_template_file
from app.modules.magazine.template_selection import select_template
from app.modules.magazine.photo_ranker import rank_photos_for_article
from app.modules.magazine.layout_planner import plan_page_layout
from app.modules.magazine.multi_page_planner import plan_multi_page_magazine
from app.modules.magazine.validator import (
    validate_page_visual_quality,
    render_and_validate_page_with_recovery,
)
from app.modules.magazine.schemas import (
    TemplateSelectionRequest, MagazineTemplateCreate,
    PhotoSelectionRequest, PhotoSelectionResponse,
    LayoutPlanRequest, LayoutPlanResponse,
    MultiPagePlanRequest, MultiPagePlanResponse,
    PageQCRequest, VisualQualityReport, PageRecoveryResult,
    EndToEndMagazineRequest, EndToEndMagazineResponse, PipelineProgressStage,
)
from app.modules.magazine.end_to_end_pipeline import run_end_to_end_magazine_pipeline
from app.modules.magazine.access import (
    check_magazine_access,
    check_template_access,
    resolve_creation_lab,
)
from app.shared.auth.dependencies import (
    check_object_lab_access,
    get_user_permitted_lab_ids,
    require_admin,
    require_lab_admin,
    require_super_admin,
    verify_user_lab_access,
)
from app.shared.exceptions.custom import ForbiddenException, NotFoundException
from app.shared.types.content import ContentKind, MagazineType

UPLOAD_DIR = "uploads/magazines"
MAGAZINE_FEATURED_DAYS = 90
DEFAULT_GENERATION_TEMPLATE_ID = "SIET_DEFAULT_V1"

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


def _resolve_generation_template(template_id: str):
    """Return the renderer-backed template selected by the administrator."""
    normalized_id = (template_id or DEFAULT_GENERATION_TEMPLATE_ID).strip()
    if normalized_id != DEFAULT_GENERATION_TEMPLATE_ID:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported generation template: {normalized_id}",
        )
    return get_siet_default_v1_template()


def _ensure_managed_source_path(source_file_path: str) -> str:
    """Only permit the source documents saved by the analysis endpoint."""
    source_root = os.path.abspath(os.path.join(UPLOAD_DIR, "source"))
    resolved_path = os.path.abspath(source_file_path)
    try:
        is_managed = os.path.commonpath([source_root, resolved_path]) == source_root
    except ValueError:
        is_managed = False
    if not is_managed or not os.path.isfile(resolved_path):
        raise HTTPException(status_code=404, detail="Analyzed source document not found.")
    return resolved_path


def _magazine_row(m: Magazine) -> dict:
    return {
        "id": str(m.id),
        "title": m.title,
        "slug": m.slug,
        "description": m.description,
        "eventName": m.event_name,
        "eventDate": m.event_date.isoformat() if m.event_date else None,
        "departmentId": m.department_id,
        "departmentName": m.department_name,
        "targetPageBudget": m.target_page_budget,
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


@router.get("/{slug}/download")
async def download_magazine_issue(slug: str, db: AsyncSession = Depends(get_db)):
    query = (
        select(Magazine)
        .options(
            selectinload(Magazine.pages),
            selectinload(Magazine.toc_entries),
        )
        .where(Magazine.slug == slug, Magazine.status == "published")
    )
    mag = (await db.execute(query)).scalars().first()
    if not mag:
        raise NotFoundException("Magazine issue not found.")

    top_ai_news = await get_top_ai_news(db, limit=5)
    pdf_path = compile_magazine_pdf(mag, mag.pages, top_ai_news)

    filename = f"{mag.slug}.pdf"
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{slug_or_id}")
async def get_magazine_by_slug_or_id(slug_or_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    query = select(Magazine).options(
        selectinload(Magazine.pages), selectinload(Magazine.toc_entries),
        selectinload(Magazine.achievements), selectinload(Magazine.project_links),
    )
    query = query.where(Magazine.status == "published")
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
    lab_id: Optional[int] = Query(None, description="Filter by lab ID"),
    my_work: bool = Query(False, description="Filter to items created by current user"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_lab_admin),
):
    """Admin magazine listing with server-side lab isolation:
    - Super Admin: sees all magazines or filtered by lab_id.
    - Lab Admin: sees only magazines belonging to their permitted labs.
    - my_work=True: filters to items created by current_user.
    """
    query = select(Magazine).options(
        selectinload(Magazine.pages), selectinload(Magazine.toc_entries),
    ).order_by(Magazine.id.desc())

    if current_user.is_super_admin:
        if lab_id is not None:
            query = query.where(Magazine.lab_id == lab_id)
    else:
        permitted_ids = await get_user_permitted_lab_ids(current_user, db)
        if not permitted_ids:
            return success([])
        if lab_id is not None:
            if lab_id not in permitted_ids:
                raise ForbiddenException("Access denied: You do not have permission for this lab.")
            query = query.where(Magazine.lab_id == lab_id)
        else:
            query = query.where(Magazine.lab_id.in_(permitted_ids))

    if my_work:
        query = query.where(Magazine.created_by_id == current_user.id)

    rows = list((await db.execute(query)).scalars().all())
    return success([_magazine_row(m) for m in rows])


@admin_router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_event_magazine(
    event_name: str = Form(...),
    title: str = Form(...),
    description: str = Form(None),
    event_date: str = Form(None),          # ISO date string e.g. 2026-08-14
    magazine_type: str = Form("special"),
    publication_year: int = Form(datetime.now().year),
    department_id: int | None = Form(None),
    department_name: str | None = Form(None),
    lab_id: int | None = Form(None),
    template_id: int | None = Form(None),
    target_page_budget: int = Form(4),
    gallery_images_json: str = Form(None),
    writeup_headline: str | None = Form(None),
    writeup_text: str | None = Form(None),
    writeup_html: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_lab_admin),
):
    """Step 1: Create a new event magazine entry with validated lab and creator ownership."""
    target_lab_id = await resolve_creation_lab(current_user, lab_id, db)

    # If template_id provided, verify access
    target_template_version_id = None
    if template_id is not None:
        tmpl = await db.get(MagazineTemplate, template_id)
        if not tmpl:
            raise NotFoundException(f"Template #{template_id} not found.")
        await check_template_access(current_user, tmpl, db, require_write=False)
        # Fetch active version
        v_stmt = select(TemplateVersion.id).where(
            TemplateVersion.template_id == template_id,
            TemplateVersion.is_active == True
        )
        target_template_version_id = (await db.execute(v_stmt)).scalar()

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

    initial_gallery = []
    if gallery_images_json:
        try:
            initial_gallery = json.loads(gallery_images_json)
        except Exception:
            pass

    initial_body = []
    if writeup_text or writeup_html or writeup_headline:
        initial_body.append({
            "headline": writeup_headline or title,
            "text": writeup_text or "",
            "html": writeup_html or "",
            "caption": writeup_headline or "Featured Article",
        })

    mag = Magazine(
        title=title.strip(),
        slug=slug,
        description=description.strip() if description else None,
        event_name=event_name.strip(),
        event_date=parsed_event_date,
        department_id=department_id,
        department_name=department_name.strip() if department_name else None,
        lab_id=target_lab_id,
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
        template_id=template_id,
        template_version_id=target_template_version_id,
        target_page_budget=target_page_budget,
        magazine_type=mt,
        publication_year=publication_year,
        issue_date=parsed_event_date or datetime.now(timezone.utc),
        status="draft",
        is_featured=True,
        featured_until=datetime.now(timezone.utc) + timedelta(days=MAGAZINE_FEATURED_DAYS),
        cover_pages=[],
        body_pages=initial_body,
        gallery_images=initial_gallery,
        page_count=len(initial_gallery) + (1 if initial_body else 0),
    )
    db.add(mag)
    await db.commit()
    await db.refresh(mag)
    return {
        "message": "Event magazine created.",
        "id": str(mag.id),
        "slug": mag.slug,
        "status": mag.status,
        "lab_id": mag.lab_id,
        "created_by_id": mag.created_by_id,
    }


class TemplateUpdateSchema(BaseModel):
    name: str | None = None
    section_schema: list[dict]
    style_rules: dict
    example_outputs: dict | None = None


@admin_router.get("/template")
async def api_get_magazine_template(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    stmt = select(MagazineTemplate).where(MagazineTemplate.is_active == True)
    tmpl = (await db.execute(stmt)).scalars().first()
    if not tmpl:
        tmpl = MagazineTemplate(
            name="SIET Standard Issue Template",
            is_active=True,
            section_schema=DEFAULT_SECTION_SCHEMA,
            style_rules=DEFAULT_STYLE_RULES,
            example_outputs={},
        )
        db.add(tmpl)
        await db.commit()
        await db.refresh(tmpl)

    return success({
        "id": tmpl.id,
        "name": tmpl.name,
        "is_active": tmpl.is_active,
        "section_schema": tmpl.section_schema,
        "style_rules": tmpl.style_rules,
        "example_outputs": tmpl.example_outputs or {},
        "updated_at": tmpl.updated_at.isoformat() if tmpl.updated_at else None,
    })


@admin_router.put("/template")
async def api_update_magazine_template(
    payload: TemplateUpdateSchema,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_super_admin),
):
    """Update global standard magazine template (SUPER_ADMIN only).
    Lab Admins must use lab-specific templates or cloning to avoid corrupting shared templates.
    """
    stmt = select(MagazineTemplate).where(MagazineTemplate.is_active == True)
    tmpl = (await db.execute(stmt)).scalars().first()
    if not tmpl:
        tmpl = MagazineTemplate(
            name=payload.name or "SIET Standard Issue Template",
            is_active=True,
            is_global=True,
            section_schema=payload.section_schema,
            style_rules=payload.style_rules,
            example_outputs=payload.example_outputs or {},
            created_by_id=current_user.id,
            updated_by_id=current_user.id,
        )
        db.add(tmpl)
    else:
        if payload.name:
            tmpl.name = payload.name
        tmpl.section_schema = payload.section_schema
        tmpl.style_rules = payload.style_rules
        if payload.example_outputs is not None:
            tmpl.example_outputs = payload.example_outputs
        tmpl.updated_by_id = current_user.id
        tmpl.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(tmpl)

    return success({
        "id": tmpl.id,
        "name": tmpl.name,
        "is_global": tmpl.is_global,
        "is_active": tmpl.is_active,
        "section_schema": tmpl.section_schema,
        "style_rules": tmpl.style_rules,
        "example_outputs": tmpl.example_outputs or {},
        "updated_at": tmpl.updated_at.isoformat() if tmpl.updated_at else None,
    })



@admin_router.post("/template/upload")
async def api_upload_magazine_template(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_super_admin),
):
    """Upload template file and extract blueprint (SUPER_ADMIN only for global standard template)."""
    contents = await file.read()
    parsed = parse_template_file(contents, file.filename)

    stmt = select(MagazineTemplate).where(MagazineTemplate.is_active == True)
    tmpl = (await db.execute(stmt)).scalars().first()
    if not tmpl:
        tmpl = MagazineTemplate(
            name=parsed["name"],
            is_active=True,
            is_global=True,
            section_schema=parsed["section_schema"],
            style_rules=parsed["style_rules"],
            created_by_id=current_user.id,
            updated_by_id=current_user.id,
        )
        db.add(tmpl)
    else:
        tmpl.name = parsed["name"]
        tmpl.section_schema = parsed["section_schema"]
        tmpl.style_rules = parsed["style_rules"]
        tmpl.updated_by_id = current_user.id
        tmpl.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(tmpl)

    # Visual Blueprint Analysis for PDF templates
    ext = os.path.splitext(file.filename)[1].lower()
    version_id = None
    if ext == ".pdf":
        try:
            blueprint = analyze_template_pdf_visual_blueprint(contents, file.filename)

            # Create new TemplateVersion with snapshots for immutability
            version_stmt = select(func.coalesce(func.max(TemplateVersion.version_number), 0)).where(TemplateVersion.template_id == tmpl.id)
            max_ver = (await db.execute(version_stmt)).scalar() or 0

            # Deactivate previous versions
            old_vers = list((await db.execute(select(TemplateVersion).where(TemplateVersion.template_id == tmpl.id))).scalars().all())
            for ov in old_vers:
                ov.is_active = False

            ver_record = TemplateVersion(
                template_id=tmpl.id,
                version_number=max_ver + 1,
                is_active=True,
                section_schema_snapshot=tmpl.section_schema,
                style_rules_snapshot=tmpl.style_rules,
                created_by_id=current_user.id,
            )
            db.add(ver_record)
            await db.commit()
            await db.refresh(ver_record)
            version_id = ver_record.id

            for p_data in blueprint["pages"]:
                page_record = TemplatePage(
                    version_id=ver_record.id,
                    page_number=p_data["page_number"],
                    width_pt=p_data["width_pt"],
                    height_pt=p_data["height_pt"],
                    margin_top=p_data["margin_top"],
                    margin_bottom=p_data["margin_bottom"],
                    margin_left=p_data["margin_left"],
                    margin_right=p_data["margin_right"],
                )
                db.add(page_record)
                await db.commit()
                await db.refresh(page_record)

                for r_data in p_data["regions"]:
                    reg_record = TemplateRegion(
                        page_id=page_record.id,
                        region_key=r_data["region_key"],
                        x_pt=r_data["x_pt"],
                        y_pt=r_data["y_pt"],
                        width_pt=r_data["width_pt"],
                        height_pt=r_data["height_pt"],
                        role=r_data["role"],
                        typography=r_data.get("typography"),
                        color_palette=r_data.get("color_palette"),
                    )
                    db.add(reg_record)
                await db.commit()
        except Exception as e:
            logger.warning(f"Visual template blueprint extraction warning: {e}")

    return success({
        "id": tmpl.id,
        "name": tmpl.name,
        "is_active": tmpl.is_active,
        "section_schema": tmpl.section_schema,
        "style_rules": tmpl.style_rules,
        "active_version_id": version_id,
        "updated_at": tmpl.updated_at.isoformat() if tmpl.updated_at else None,
    })


@admin_router.get("/templates/{template_id}/blueprint")
async def get_template_blueprint(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_lab_admin),
):
    """
    Phase 4 Visual Template Blueprint Inspection Endpoint:
    Returns stored visual blueprint hierarchy with object-level lab authorization.
    """
    tmpl = await db.get(MagazineTemplate, template_id)
    if not tmpl:
        raise NotFoundException(f"Magazine template #{template_id} not found.")

    await check_template_access(current_user, tmpl, db, require_write=False)

    version_stmt = (
        select(TemplateVersion)
        .where(TemplateVersion.template_id == template_id, TemplateVersion.is_active == True)
        .options(selectinload(TemplateVersion.pages).selectinload(TemplatePage.regions))
    )
    active_ver = (await db.execute(version_stmt)).scalars().first()
    if not active_ver:
        return success({
            "template_id": tmpl.id,
            "name": tmpl.name,
            "has_visual_blueprint": False,
            "pages": [],
        })

    pages_out = []
    for page in active_ver.pages:
        regions_out = [
            {
                "id": r.id,
                "region_key": r.region_key,
                "x_pt": r.x_pt,
                "y_pt": r.y_pt,
                "width_pt": r.width_pt,
                "height_pt": r.height_pt,
                "role": r.role,
                "typography": r.typography,
                "color_palette": r.color_palette,
            }
            for r in page.regions
        ]
        pages_out.append({
            "id": page.id,
            "page_number": page.page_number,
            "width_pt": page.width_pt,
            "height_pt": page.height_pt,
            "margins": {
                "top": page.margin_top,
                "bottom": page.margin_bottom,
                "left": page.margin_left,
                "right": page.margin_right,
            },
            "regions": regions_out,
        })

    return success({
        "template_id": tmpl.id,
        "name": tmpl.name,
        "version_number": active_ver.version_number,
        "has_visual_blueprint": True,
        "pages": pages_out,
    })


@admin_router.post("/templates/select")
@router.post("/templates/select")
async def api_select_magazine_template(
    payload: TemplateSelectionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Intelligent template selection endpoint.
    Dynamically recommends and validates a template candidate against declared metadata.
    Output conforms to:
    {
      "template_id": "...",
      "page_type": "...",
      "confidence": 0.95,
      "reason": "..."
    }
    """
    try:
        res = await select_template(
            content=payload.content,
            department=payload.department,
            lab=payload.lab,
            department_or_lab=payload.department_or_lab,
            section=payload.section,
            page_type=payload.page_type,
            available_images=payload.available_images,
            candidate_templates=payload.candidate_templates,
            db=db,
            use_llm=payload.use_llm,
        )
        return success(res)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@admin_router.post("/photos/rank")
@router.post("/photos/rank")
async def api_rank_magazine_photos(
    payload: PhotoSelectionRequest,
):
    """
    Intelligent real-photo selection and ranking endpoint.
    Scores photographs by multimodal SigLIP relevance and photographic quality
    (resolution, sharpness, exposure, orientation, duplicate detection).
    Strictly prefers real photographs; never generates synthetic AI photos.
    """
    res = await rank_photos_for_article(
        article_content=payload.article_content,
        photos=payload.photos,
        top_k=payload.top_k,
        filter_duplicates=payload.filter_duplicates,
        min_quality_threshold=payload.min_quality_threshold,
    )
    return success(res)


@admin_router.post("/layout/plan")
@router.post("/layout/plan")
async def api_plan_magazine_layout(
    payload: LayoutPlanRequest,
):
    """
    Magazine layout planning endpoint.
    Converts article content and candidate photographs into a deterministic PagePlan
    and rigorously validates region existence, text length, image count, and aspect ratios.
    """
    plan, validation = await plan_page_layout(
        content=payload.content,
        department_or_lab=payload.department_or_lab,
        selected_template=payload.selected_template,
        available_images=payload.available_images,
        template_regions=payload.template_regions,
        text_limits=payload.text_limits,
        image_constraints=payload.image_constraints,
        use_llm=payload.use_llm,
    )
    return success({
        "plan": plan.model_dump(),
        "validation": validation.model_dump(),
    })


@admin_router.post("/pages/plan")
@router.post("/pages/plan")
async def api_plan_multi_page_magazine(
    payload: MultiPagePlanRequest,
):
    """
    Automatic multi-page magazine planning endpoint.
    Determines how many pages are required, packs content by template capacity,
    maintains section ordering, and avoids repeating identical layouts.
    """
    response = plan_multi_page_magazine(
        structured_content=payload.structured_content,
        department_or_lab=payload.department_or_lab,
        available_images=payload.available_images,
        available_templates=payload.available_templates,
        template_constraints=payload.template_constraints,
        magazine_section_order=payload.magazine_section_order,
        max_pages=payload.max_pages,
        start_page_number=payload.start_page_number,
    )
    return success(response.model_dump())


@admin_router.post("/qc/page")
@router.post("/qc/page")
async def api_validate_page_visual_quality(
    payload: PageQCRequest,
):
    """
    Automatic visual quality control endpoint for rendered magazine pages.
    Checks text overflow, image overflow, missing assets, image distortion,
    low-resolution images, overlapping regions, boundaries, excessive empty space,
    small text, and margins. Returns quality scores (0-100) and issues list.
    Optionally executes closed-loop recovery with regeneration limits.
    """
    import fitz
    from app.modules.magazine.renderer import render_page_from_plan

    doc = fitz.open()
    if payload.with_recovery:
        result = render_and_validate_page_with_recovery(
            doc=doc,
            page_plan=payload.plan,
            template_metadata=payload.template_metadata,
            page_num=payload.page_num,
            max_attempts=payload.max_attempts,
            thresholds=payload.thresholds,
        )
        return success(result.model_dump())
    else:
        page = render_page_from_plan(
            doc,
            payload.plan,
            payload.template_metadata,
            payload.page_num,
        )
        report = validate_page_visual_quality(
            page=page,
            page_plan=payload.plan,
            template_metadata=payload.template_metadata,
            thresholds=payload.thresholds,
            page_num=payload.page_num,
        )
        return success(report.model_dump())


@admin_router.get("/templates")
async def api_list_magazine_templates(
    department_id: int | None = Query(None),
    department_slug: str | None = Query(None),
    lab_id: int | None = Query(None),
    is_active: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_lab_admin),
):
    """List magazine templates available to the current user with strict 3-tier rules:
    - Super Admin: can view all templates (or filtered by lab_id).
    - Lab Admin: can view:
        1. Templates explicitly assigned to their lab (via template_lab_assignments).
        2. Templates created specifically for their lab (lab_id in permitted).
        3. Global templates (is_global=True).
    """
    stmt = select(MagazineTemplate)
    if is_active is not None:
        stmt = stmt.where(MagazineTemplate.is_active == is_active)
    if department_id is not None:
        stmt = stmt.where(MagazineTemplate.department_id == department_id)
    if department_slug:
        stmt = stmt.where(MagazineTemplate.department_slug == department_slug)

    if not current_user.is_super_admin:
        permitted_labs = await get_user_permitted_lab_ids(current_user, db)
        if not permitted_labs:
            # Only global templates accessible
            stmt = stmt.where(MagazineTemplate.is_global == True)
        else:
            # Rule 1, 2, 3 combined
            from sqlalchemy import or_
            from app.modules.labs.models import TemplateLabAssignment
            assigned_template_ids_stmt = select(TemplateLabAssignment.template_id).where(
                TemplateLabAssignment.lab_id.in_(permitted_labs),
                TemplateLabAssignment.is_active == True
            )
            stmt = stmt.where(
                or_(
                    MagazineTemplate.is_global == True,
                    MagazineTemplate.lab_id.in_(permitted_labs),
                    MagazineTemplate.id.in_(assigned_template_ids_stmt)
                )
            )
            if lab_id is not None:
                if lab_id not in permitted_labs:
                    raise ForbiddenException("Access denied: You do not have permission for this lab.")
                stmt = stmt.where(or_(MagazineTemplate.lab_id == lab_id, MagazineTemplate.is_global == True))
    else:
        if lab_id is not None:
            stmt = stmt.where(MagazineTemplate.lab_id == lab_id)

    templates = list((await db.execute(stmt)).scalars().all())
    out = []
    for tmpl in templates:
        out.append({
            "id": tmpl.id,
            "name": tmpl.name,
            "is_global": tmpl.is_global,
            "lab_id": tmpl.lab_id,
            "department_id": tmpl.department_id,
            "department_slug": tmpl.department_slug,
            "template_family": tmpl.template_family,
            "page_budget": tmpl.page_budget,
            "description": tmpl.description,
            "is_active": tmpl.is_active,
            "section_schema": tmpl.section_schema,
            "style_rules": tmpl.style_rules,
            "template_metadata": tmpl.effective_metadata,
            "example_outputs": tmpl.example_outputs or {},
            "created_by_id": tmpl.created_by_id,
            "updated_at": tmpl.updated_at.isoformat() if tmpl.updated_at else None,
        })
    return success(out)


@router.get("/templates")
async def api_public_list_magazine_templates(
    department_id: int | None = Query(None),
    department_slug: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Public template list: strictly global active templates only."""
    stmt = select(MagazineTemplate).where(
        MagazineTemplate.is_active == True,
        MagazineTemplate.is_global == True
    )
    if department_id is not None:
        stmt = stmt.where(MagazineTemplate.department_id == department_id)
    if department_slug:
        stmt = stmt.where(MagazineTemplate.department_slug == department_slug)

    templates = list((await db.execute(stmt)).scalars().all())
    out = []
    for tmpl in templates:
        out.append({
            "id": tmpl.id,
            "name": tmpl.name,
            "template_family": tmpl.template_family,
            "page_budget": tmpl.page_budget,
            "description": tmpl.description,
            "is_active": tmpl.is_active,
            "section_schema": tmpl.section_schema,
            "style_rules": tmpl.style_rules,
            "template_metadata": tmpl.effective_metadata,
            "example_outputs": tmpl.example_outputs or {},
            "updated_at": tmpl.updated_at.isoformat() if tmpl.updated_at else None,
        })
    return success(out)


@admin_router.post("/templates")
async def api_create_magazine_template(
    payload: MagazineTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_lab_admin),
):
    """Create a new magazine template.
    - Super Admin: can create global or lab-specific templates.
    - Lab Admin: can ONLY create templates for their permitted lab (cannot create global templates).
    """
    target_is_global = False
    target_lab_id = None

    if current_user.is_super_admin:
        target_is_global = payload.is_global
        target_lab_id = payload.lab_id if not target_is_global else None
    else:
        # Lab admin cannot create global templates
        target_is_global = False
        target_lab_id = await resolve_creation_lab(current_user, payload.lab_id, db)

    tmpl = MagazineTemplate(
        name=payload.name,
        is_global=target_is_global,
        lab_id=target_lab_id,
        department_id=payload.department_id,
        department_slug=payload.department_slug,
        template_family=payload.template_family,
        page_budget=payload.page_budget,
        description=payload.description,
        is_active=True,
        section_schema=payload.section_schema,
        style_rules=payload.style_rules,
        template_metadata=payload.template_metadata,
        example_outputs=payload.example_outputs or {},
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )
    db.add(tmpl)
    await db.commit()
    await db.refresh(tmpl)
    return success({
        "id": tmpl.id,
        "name": tmpl.name,
        "is_global": tmpl.is_global,
        "lab_id": tmpl.lab_id,
        "department_id": tmpl.department_id,
        "department_slug": tmpl.department_slug,
        "template_family": tmpl.template_family,
        "page_budget": tmpl.page_budget,
        "description": tmpl.description,
        "is_active": tmpl.is_active,
        "section_schema": tmpl.section_schema,
        "style_rules": tmpl.style_rules,
        "template_metadata": tmpl.effective_metadata,
        "example_outputs": tmpl.example_outputs or {},
        "created_by_id": tmpl.created_by_id,
        "updated_at": tmpl.updated_at.isoformat() if tmpl.updated_at else None,
    })


@admin_router.get("/templates/{template_id}")
async def api_get_single_magazine_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_lab_admin),
):
    """Get single magazine template by ID with object-level lab authorization."""
    tmpl = await db.get(MagazineTemplate, template_id)
    if not tmpl:
        raise NotFoundException(f"Magazine template #{template_id} not found.")

    await check_template_access(current_user, tmpl, db, require_write=False)

    return success({
        "id": tmpl.id,
        "name": tmpl.name,
        "is_global": tmpl.is_global,
        "lab_id": tmpl.lab_id,
        "department_id": tmpl.department_id,
        "department_slug": tmpl.department_slug,
        "template_family": tmpl.template_family,
        "page_budget": tmpl.page_budget,
        "description": tmpl.description,
        "is_active": tmpl.is_active,
        "section_schema": tmpl.section_schema,
        "style_rules": tmpl.style_rules,
        "template_metadata": tmpl.effective_metadata,
        "example_outputs": tmpl.example_outputs or {},
        "updated_at": tmpl.updated_at.isoformat() if tmpl.updated_at else None,
    })




@admin_router.post("/{magazine_id}/cover")
async def upload_cover_pages(
    magazine_id: int,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_lab_admin),
):
    """Upload up to 2 intro/cover page images. Replaces any existing cover pages."""
    mag = await db.get(Magazine, magazine_id)
    if not mag:
        raise NotFoundException("Magazine not found.")
    await check_magazine_access(current_user, mag, db, require_write=True)

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
    mag.updated_by_id = current_user.id
    await db.commit()
    return {"message": f"Saved {len(saved)} cover page(s).", "coverPages": saved}


@admin_router.post("/{magazine_id}/body")
async def upload_body_pages(
    magazine_id: int,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_lab_admin),
):
    """Upload body content pages (images). Appends to existing body pages."""
    mag = await db.get(Magazine, magazine_id)
    if not mag:
        raise NotFoundException("Magazine not found.")
    await check_magazine_access(current_user, mag, db, require_write=True)

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
    mag.updated_by_id = current_user.id
    await db.commit()
    return {"message": f"Added {len(files)} body page(s). Total body pages: {len(existing)}.", "bodyPages": existing}


@admin_router.post("/{magazine_id}/gallery")
async def upload_gallery_images(
    magazine_id: int,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_lab_admin),
):
    """Batch upload event photos. Auto-appended as the final gallery section."""
    mag = await db.get(Magazine, magazine_id)
    if not mag:
        raise NotFoundException("Magazine not found.")
    await check_magazine_access(current_user, mag, db, require_write=True)

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
    mag.updated_by_id = current_user.id
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
    lab_id: int | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_super_admin),
):
    """Upload a full PDF directly (Super Admin only flow)."""
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
        lab_id=lab_id,
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
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
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_super_admin),
):
    """Publish an approval-cleared magazine and stamp its publication time. Super Admin action."""
    mag = await db.get(Magazine, magazine_id)
    if not mag:
        raise NotFoundException("Magazine not found.")

    if mag.status != "approved":
        raise HTTPException(
            status_code=400,
            detail="Magazine must be approved after review before it can be published.",
        )
    if mag.orchestrator_score is not None and mag.orchestrator_score < 0.70:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot publish magazine: validation score ({mag.orchestrator_score}) is below the required 0.70 threshold."
        )

    now = datetime.now(timezone.utc)
    mag.status = "published"
    mag.published_at = now
    mag.is_featured = True
    mag.featured_until = now + timedelta(days=MAGAZINE_FEATURED_DAYS)
    mag.updated_by_id = current_user.id
    await db.commit()

    if not mag.pdf_url or mag.page_count == 0:
        from app.modules.magazine.pipeline import compile_and_process_event_magazine
        background_tasks.add_task(compile_and_process_event_magazine, magazine_id)

    return {"message": "Magazine published.", "id": str(mag.id), "isFeatured": mag.is_featured}


@admin_router.post("/{magazine_id}/approve")
async def approve_magazine(
    magazine_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Persist the administrative approval required before publication."""
    mag = await db.get(Magazine, magazine_id)
    if not mag:
        raise NotFoundException("Magazine not found.")
    if mag.status == "failed":
        raise HTTPException(status_code=400, detail="A failed generation cannot be approved.")
    if mag.status not in {"draft", "review", "approved"}:
        raise HTTPException(
            status_code=400,
            detail=f"Magazine in '{mag.status}' status is not ready for approval.",
        )
    if mag.orchestrator_score is not None and mag.orchestrator_score < 0.70:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve magazine: validation score ({mag.orchestrator_score}) is below the required 0.70 threshold.",
        )
    mag.status = "approved"
    await db.commit()
    return {"message": "Magazine approved for publication.", "id": str(mag.id), "status": mag.status}


@admin_router.post("/{magazine_id}/submit-review")
async def submit_magazine_for_review(
    magazine_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_lab_admin),
):
    """Lab Admin submits their magazine draft for Super Admin review & publishing."""
    mag = await db.get(Magazine, magazine_id)
    if not mag:
        raise NotFoundException("Magazine not found.")
    await check_magazine_access(current_user, mag, db, require_write=True)

    mag.status = "submitted"
    mag.updated_by_id = current_user.id
    await db.commit()
    return {"message": "Magazine submitted for Super Admin review.", "id": str(mag.id), "status": mag.status}


@admin_router.post("/{magazine_id}/reject")
async def reject_magazine(
    magazine_id: int,
    notes: str = Form("Needs revisions"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_super_admin),
):
    """Super Admin rejects a submitted magazine with review notes."""
    mag = await db.get(Magazine, magazine_id)
    if not mag:
        raise NotFoundException("Magazine not found.")

    mag.status = "rejected"
    mag.review_notes = notes
    mag.updated_by_id = current_user.id
    await db.commit()
    return {"message": "Magazine rejected with review feedback.", "id": str(mag.id), "status": mag.status, "notes": notes}


@admin_router.post("/{magazine_id}/compile")
async def api_compile_magazine(
    magazine_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_lab_admin),
):
    """Compiles and renders a full multi-page event magazine publication immediately."""
    mag = await db.get(Magazine, magazine_id)
    if not mag:
        raise NotFoundException("Magazine not found.")
    await check_magazine_access(current_user, mag, db, require_write=True)

    from app.modules.magazine.pipeline import compile_and_process_event_magazine
    res = await compile_and_process_event_magazine(magazine_id)
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message", "Compilation failed"))
    return success(res)


@admin_router.post("/{magazine_id}/unpublish")
async def unpublish_magazine(
    magazine_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_super_admin),
):
    """Unpublish a magazine while retaining its completed approval (Super Admin only)."""
    mag = await db.get(Magazine, magazine_id)
    if not mag:
        raise NotFoundException("Magazine not found.")
    mag.status = "approved"
    mag.is_featured = False
    mag.updated_by_id = current_user.id
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
    mag.updated_by_id = current_user.id
    await db.commit()
    background_tasks.add_task(process_magazine_pdf, mag.id, pdf_save_path)
    return {"message": f"PDF replaced for magazine #{magazine_id}. Background processing re-started.", "id": str(mag.id)}


@admin_router.delete("/{magazine_id}")
async def delete_magazine_issue(
    magazine_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_lab_admin),
):
    """Delete magazine: Super Admin can delete any; Lab Admin can only delete within assigned lab."""
    mag = await db.get(Magazine, magazine_id)
    if not mag:
        raise NotFoundException("Magazine issue not found.")
    await check_magazine_access(current_user, mag, db, require_write=True)

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


@admin_router.get("/ai/health")
async def api_ai_health(
    current_user=Depends(require_admin),
):
    """
    Checks operational status and diagnostic connectivity of primary (Ollama/Qwen)
    and fallback AI providers.
    """
    from app.infrastructure.ai import get_ai_service
    health_data = await get_ai_service().health()
    return success(health_data)


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


class ApprovedGenerationPayload(BaseModel):
    source_file_path: str
    lab_department: str = "Artificial Intelligence and Data Science"
    title: str = ""
    issue_date: str = ""
    template_id: str = "SIET_DEFAULT_V1"
    approved_associations: Dict[str, List[Any]] = {}
    all_photos: List[Dict[str, Any]] = []


async def _execute_and_persist_magazine(
    source_path: str,
    department: str,
    issue_title: str,
    final_event_date: str,
    event_photos_map: Optional[Dict[str, List[Any]]],
    uploaded_photos: Optional[List[Dict[str, Any]]],
    original_filename: str,
    file_size_bytes: int,
    template_id: str,
    db: AsyncSession,
    current_user: Any,
) -> Dict[str, Any]:
    final_event_name = issue_title.strip() if issue_title.strip() else (department.strip() if department.strip() else "Artificial Intelligence Research Lab")
    final_date_str = final_event_date.strip() if final_event_date.strip() else "August 2026"

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    pdf_filename = f"rendered_issue_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6]}.pdf"
    output_pdf_path = os.path.join(UPLOAD_DIR, pdf_filename)

    template = _resolve_generation_template(template_id)
    pipeline = MagazineGenerationPipeline(template_spec=template)

    try:
        planned_pages, validation_report, output_pdf_path = await pipeline.generate_magazine(
            source_text_or_path=source_path,
            department=department,
            issue_title=final_event_name,
            event_photos_map=event_photos_map,
            uploaded_photos=uploaded_photos,
            output_pdf_path=output_pdf_path,
        )
    except ValueError as e:
        logger.warning(f"Magazine generation input rejected: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Magazine generation pipeline error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Magazine generation pipeline failed: {str(e)}"
        )

    page_previews = pipeline.renderer.generated_previews
    total_pages = len(planned_pages)

    cover_preview = page_previews[0] if page_previews else None
    if cover_preview and not cover_preview.startswith("/"):
        cover_preview = "/" + cover_preview

    extracted_images = []
    seen_photos = set()
    for img in getattr(pipeline, "extracted_images", []):
        url = img.get("url") if isinstance(img, dict) else str(img)
        if url and url not in seen_photos:
            seen_photos.add(url)
            extracted_images.append({
                "url": url if url.startswith("/") else f"/{url}",
                "file_name": os.path.basename(url),
                "is_masthead": img.get("is_masthead", False) if isinstance(img, dict) else False,
            })

    for p in planned_pages:
        for ph in p.get("attached_photos", []):
            url = ph.get("url") if isinstance(ph, dict) else str(ph)
            img_url = url if url.startswith("/") else f"/{url}"
            if img_url not in seen_photos:
                seen_photos.add(img_url)
                extracted_images.append({
                    "url": img_url,
                    "file_name": os.path.basename(img_url),
                    "is_masthead": False,
                })

    lead_story = planned_pages[2] if len(planned_pages) > 2 else planned_pages[0]
    writeup_headline = lead_story.get("headline", final_event_name)
    writeup_text = lead_story.get("body", "")
    toc_summary = planned_pages[1].get("body", "") if len(planned_pages) > 1 else ""

    captions = []
    for p in planned_pages:
        captions.extend(p.get("captions", []))

    render_result = {
        "pdf_path": output_pdf_path,
        "total_pages": total_pages,
        "page_previews": page_previews,
    }

    blueprint = {
        "template_id": template.template_id,
        "name": template.name,
        "page_count": total_pages,
        "pages": [
            {
                "page_number": p["page_number"],
                "page_type": p["page_type"],
                "headline": p.get("headline", ""),
                "attached_photos_count": len(p.get("attached_photos", [])),
            }
            for p in planned_pages
        ],
    }

    base_slug = slugify(final_event_name or "siet-magazine")
    mag_slug = await _unique_slug(db, base_slug)

    parsed_date = None
    if final_date_str:
        try:
            from dateutil import parser as dt_parser
            parsed_date = dt_parser.parse(final_date_str)
        except Exception:
            parsed_date = None

    mag = Magazine(
        title=final_event_name,
        slug=mag_slug,
        description=lead_story.get("subheadline", "") or "Official SIET College Magazine Digest",
        event_name=final_event_name,
        event_date=parsed_date,
        publication_year=datetime.now(timezone.utc).year,
        issue_date=parsed_date,
        status="review" if validation_report.is_valid else "failed",
        is_featured=False,
        pdf_url=f"/uploads/magazines/{pdf_filename}",
        cover_image_url=cover_preview,
        page_count=total_pages,
        gallery_images=extracted_images,
        editorial_plan={
            "issue_title": final_event_name,
            "department": department,
            "template_id": template.template_id,
            "template_name": template.name,
            "template_version": template.version,
            "generation_timestamp": datetime.now(timezone.utc).isoformat(),
            "created_by_user_id": getattr(current_user, "id", None),
            "created_by_email": getattr(current_user, "email", None),
            "source_provenance": {
                "original_filename": original_filename,
                "saved_path": source_path,
                "file_size_bytes": file_size_bytes,
            },
            "total_pages": total_pages,
            "stories_count": max(0, len(planned_pages) - 3),
            "detected_event_name": final_event_name,
            "detected_event_date": final_date_str,
            "attached_photos_summary": {
                "total_attached_photos": len(extracted_images),
                "images": extracted_images,
            },
            "approved_associations": event_photos_map or {},
            "pages_summary": [
                {
                    "page": p["page_number"],
                    "type": p["page_type"],
                    "headline": p.get("headline", ""),
                    "photo_count": len(p.get("attached_photos", [])),
                }
                for p in planned_pages
            ],
        },
        orchestrator_score=validation_report.composite_score if hasattr(validation_report, "composite_score") else 1.0,
        failure_reason=("; ".join(validation_report.all_issues) if not validation_report.is_valid else None),
    )
    db.add(mag)
    await db.flush()

    for p_idx, p_data in enumerate(planned_pages):
        prev_url = page_previews[p_idx] if p_idx < len(page_previews) else None
        if prev_url and not prev_url.startswith("/"):
            prev_url = "/" + prev_url
        mag_page = MagazinePage(
            magazine_id=mag.id,
            page_number=p_data["page_number"],
            image_url=prev_url or "",
            extracted_text=p_data.get("body", "")[:1000],
        )
        db.add(mag_page)

    for p_data in planned_pages:
        if p_data["page_type"] not in {"cover", "contents", "closing", "closing_page"} and p_data.get("headline"):
            toc = MagazineTOCEntry(
                magazine_id=mag.id,
                page_number=p_data["page_number"],
                heading=p_data["headline"][:250],
            )
            db.add(toc)

    await db.commit()
    await db.refresh(mag)

    val_report_dict = validation_report.model_dump() if hasattr(validation_report, "model_dump") else (
        validation_report.dict() if hasattr(validation_report, "dict") else {}
    )

    return {
        "magazine_id": mag.id,
        "id": mag.id,
        "title": mag.title,
        "slug": mag.slug,
        "magazine_issue_title": mag.title,
        "writeup_headline": writeup_headline,
        "writeup_text": writeup_text,
        "toc_summary": toc_summary,
        "captions": captions,
        "pdf_url": mag.pdf_url,
        "cover_image_url": mag.cover_image_url,
        "page_count": mag.page_count,
        "total_pages": mag.page_count,
        "pdf_path": render_result.get("pdf_path") or (mag.pdf_url.lstrip("/") if mag.pdf_url else ""),
        "status": mag.status,
        "blueprint": blueprint,
        "render_result": render_result,
        "validation": val_report_dict,
        "validation_report": val_report_dict,
        "validation_summary": {
            "is_valid": val_report_dict.get("is_valid", True),
            "composite_score": mag.orchestrator_score or 1.0,
            "page_count": mag.page_count,
            "errors": val_report_dict.get("errors", []),
            "warnings": val_report_dict.get("warnings", []),
        },
        "orchestrator_score": mag.orchestrator_score or 1.0,
        "detected_event_name": final_event_name,
        "detected_event_date": final_date_str,
        "extracted_images": extracted_images,
        "events_count": max(0, len(planned_pages) - 3),
        "stories_count": max(0, len(planned_pages) - 3),
        "photos_count": len([img for img in extracted_images if not img.get("is_masthead")]),
        "photo_associations": getattr(pipeline, "photo_associations", []),
    }


@admin_router.post("/ai/auto-generate-from-file")
async def api_auto_generate_from_file(
    file: UploadFile = File(...),
    photos: List[UploadFile] = File(default=[]),
    event_name: str = Form(""),
    event_date: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    FILE UPLOAD AUTO-RECOGNITION & MULTI-PAGE SIET MAGAZINE GENERATION PIPELINE:
    1. Extracts & segments events/achievements from source document.
    2. Enforces event-scoped photo association with strict photo isolation.
    3. Generates grounded Qwen3-14B editorial content.
    4. Plans multi-page magazine layout using SIET_DEFAULT_V1.
    5. Deterministically renders multi-page magazine PDF and high-res page previews.
    6. Persists Magazine record, MagazinePages, and TOC entries in database.
    7. Returns complete magazine metadata and generation outputs.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    os.makedirs("uploads/magazines/source", exist_ok=True)
    source_filename = f"source_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6]}_{file.filename or 'doc.pdf'}"
    source_path = os.path.join("uploads/magazines/source", source_filename)
    with open(source_path, "wb") as f:
        f.write(file_bytes)

    uploaded_photo_dicts: List[Dict[str, Any]] = []
    if photos:
        os.makedirs("uploads/magazines/extracted", exist_ok=True)
        for idx, photo_file in enumerate(photos):
            p_bytes = await photo_file.read()
            if not p_bytes:
                continue
            orig_fn = photo_file.filename or f"photo_{idx+1}.jpg"
            ext = os.path.splitext(orig_fn)[1].lower() or ".jpg"
            p_id = f"up_photo_{idx+1}_{uuid.uuid4().hex[:6]}"
            disk_name = f"{p_id}{ext}"
            disk_path = os.path.join("uploads/magazines/extracted", disk_name)
            with open(disk_path, "wb") as pf:
                pf.write(p_bytes)
            pub_url = f"/uploads/magazines/extracted/{disk_name}"
            uploaded_photo_dicts.append({
                "id": p_id,
                "url": pub_url,
                "file_name": orig_fn,
                "disk_path": disk_path,
                "is_masthead": False,
            })

    final_event_name = event_name.strip() if event_name.strip() else "Artificial Intelligence Research Lab"
    final_event_date = event_date.strip() if event_date.strip() else "August 2026"

    res = await _execute_and_persist_magazine(
        source_path=source_path,
        department=final_event_name,
        issue_title=final_event_name,
        final_event_date=final_event_date,
        event_photos_map=None,
        uploaded_photos=uploaded_photo_dicts,
        original_filename=file.filename or "doc.pdf",
        file_size_bytes=len(file_bytes),
        template_id=DEFAULT_GENERATION_TEMPLATE_ID,
        db=db,
        current_user=current_user,
    )
    return success(res)


@admin_router.post("/ai/analyze-and-match")
async def api_analyze_and_match(
    file: UploadFile = File(...),
    photos: List[UploadFile] = File(default=[]),
    lab_department: str = Form("Artificial Intelligence and Data Science"),
    title: str = Form(""),
    issue_date: str = Form(""),
    template_id: str = Form("SIET_DEFAULT_V1"),
    current_user=Depends(require_admin),
):
    """
    Step 1: Upload source document + photos, segment events, and run AI matching with confidence rules:
    - >= 0.90: HIGH CONFIDENCE (auto-attached)
    - 0.75 - 0.89: REVIEW RECOMMENDED (auto-attached, flagged)
    - < 0.75: UNMATCHED (placed in unmatched_photos for admin manual attachment)
    """
    _resolve_generation_template(template_id)
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    os.makedirs("uploads/magazines/source", exist_ok=True)
    source_filename = f"source_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6]}_{file.filename or 'doc.pdf'}"
    source_path = os.path.join("uploads/magazines/source", source_filename)
    with open(source_path, "wb") as f:
        f.write(file_bytes)

    uploaded_photo_dicts: List[Dict[str, Any]] = []
    if photos:
        os.makedirs("uploads/magazines/extracted", exist_ok=True)
        for idx, photo_file in enumerate(photos):
            p_bytes = await photo_file.read()
            if not p_bytes:
                continue
            orig_fn = photo_file.filename or f"photo_{idx+1}.jpg"
            ext = os.path.splitext(orig_fn)[1].lower() or ".jpg"
            p_id = f"up_photo_{idx+1}_{uuid.uuid4().hex[:6]}"
            disk_name = f"{p_id}{ext}"
            disk_path = os.path.join("uploads/magazines/extracted", disk_name)
            with open(disk_path, "wb") as pf:
                pf.write(p_bytes)
            pub_url = f"/uploads/magazines/extracted/{disk_name}"
            uploaded_photo_dicts.append({
                "id": p_id,
                "url": pub_url,
                "file_name": orig_fn,
                "disk_path": disk_path,
                "is_masthead": False,
            })

    dept = lab_department.strip() or "Artificial Intelligence and Data Science"
    mag_source = segment_document_events(
        file_bytes=file_bytes,
        filename=file.filename or "doc.pdf",
        default_department=dept,
    )

    analysis = PhotoAssociator.analyze_and_match(
        events=mag_source.events,
        uploaded_photos=uploaded_photo_dicts,
        confidence_threshold_high=0.90,
        confidence_threshold_review=0.75,
    )

    return success({
        "session_id": str(uuid.uuid4()),
        "source_file_path": source_path,
        "original_filename": file.filename,
        "file_size_bytes": len(file_bytes),
        "lab_department": dept,
        "title": title.strip() or (mag_source.events[0].title if mag_source.events else f"{dept} Magazine"),
        "issue_date": issue_date.strip() or "August 2026",
        "template_id": template_id,
        "events": analysis["events"],
        "unmatched_photos": analysis["unmatched_photos"],
        "associations": analysis["associations"],
        "all_uploaded_photos": uploaded_photo_dicts,
        "stats": analysis["stats"],
    })


@admin_router.post("/ai/generate-from-approved")
async def api_generate_from_approved(
    payload: ApprovedGenerationPayload,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    Step 2: Admin approves/corrects associations and triggers grounded magazine PDF generation.
    """
    source_path = _ensure_managed_source_path(payload.source_file_path)

    res = await _execute_and_persist_magazine(
        source_path=source_path,
        department=payload.lab_department,
        issue_title=payload.title,
        final_event_date=payload.issue_date,
        event_photos_map=payload.approved_associations,
        uploaded_photos=payload.all_photos,
        original_filename=os.path.basename(source_path),
        file_size_bytes=os.path.getsize(source_path),
        template_id=payload.template_id,
        db=db,
        current_user=current_user,
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


class AIGroundedRequest(BaseModel):
    event_name: str = ""
    event_date: str = ""
    raw_notes: str
    photo_count: int = 0
    document_ids: list[int] | None = None


@admin_router.post("/ai/generate-grounded")
async def api_generate_grounded(
    payload: AIGroundedRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    Phase 3 Grounded LLM Content Generation Endpoint:
    Pulls RAG source passages from Document Intelligence, injects them as ground truth facts,
    and returns generated magazine content annotated with real sources and confidence bands.
    """
    res = await generate_grounded_magazine_content(
        event_name=payload.event_name,
        event_date=payload.event_date,
        raw_notes=payload.raw_notes,
        photo_count=payload.photo_count,
        document_ids=payload.document_ids,
        db=db,
    )
    return success(res)


class AIReviseRequest(BaseModel):
    section_key: str
    feedback_comment: str
    current_content: str = ""
    event_name: str = ""
    raw_notes: str = ""
    document_ids: list[int] | None = None


@admin_router.post("/ai/revise")
async def api_revise_section(
    payload: AIReviseRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    Part 4 Section-Targeted Revision Endpoint:
    Re-generates strictly the targeted section based on ground truth passages and admin feedback comment.
    """
    from app.modules.magazine.ai_service import revise_section_content

    res = await revise_section_content(
        section_key=payload.section_key,
        feedback_comment=payload.feedback_comment,
        current_content=payload.current_content,
        event_name=payload.event_name,
        raw_notes=payload.raw_notes,
        document_ids=payload.document_ids,
        db=db,
    )
    return success(res)


class AIOrchestrationRequest(BaseModel):
    event_name: str
    raw_notes: str
    template_name: str = "Siet Magazine Template"
    max_rework_rounds: int = 2


@admin_router.post("/ai/orchestrated-generate")
async def api_orchestrated_magazine_generate(
    payload: AIOrchestrationRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    Orchestrator Agent Pipeline Endpoint:
    Pre-generation Planning -> Plan-Conditioned Generation -> Section Verification -> Post-generation Holistic Design Scoring -> Rework Loop (max 2 rounds).
    """
    from app.modules.magazine.orchestrator import run_orchestrated_magazine_pipeline

    res = await run_orchestrated_magazine_pipeline(
        event_name=payload.event_name,
        raw_notes=payload.raw_notes,
        template_name=payload.template_name,
        db=db,
        max_rework_rounds=payload.max_rework_rounds,
    )
    return success(res)




class RenderFromBlueprintRequest(BaseModel):
    template_id: int = 1
    event_name: str = "SIET Campus Innovation Digest"
    event_date: str = ""
    raw_notes: str
    document_ids: list[int] | None = None


@admin_router.post("/render-from-blueprint")
async def api_render_from_blueprint(
    payload: RenderFromBlueprintRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    Phase 5 & 6 End-to-End Master Endpoint:
    1. Executes Grounded LLM Content Generation with source provenance.
    2. Fetches active TemplateVersion & Visual Blueprint.
    3. Renders PDF strictly into region coordinates with font scaling.
    4. Runs Layout & Content Grounding Validation.
    """
    # 1. Grounded Generation
    grounded_content = await generate_grounded_magazine_content(
        event_name=payload.event_name,
        event_date=payload.event_date,
        raw_notes=payload.raw_notes,
        document_ids=payload.document_ids,
        db=db,
    )

    # 2. Fetch Blueprint
    bp_res = await get_template_blueprint(template_id=payload.template_id, db=db, current_user=current_user)
    blueprint = bp_res.data if hasattr(bp_res, "data") else (bp_res.get("data", {}) if isinstance(bp_res, dict) else {})

    # 3. Deterministic Coordinate PDF Rendering
    pdf_filename = f"rendered_issue_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6]}.pdf"
    output_pdf_path = os.path.join(UPLOAD_DIR, pdf_filename)

    render_result = render_magazine_pdf_from_blueprint(
        blueprint=blueprint,
        content=grounded_content,
        output_pdf_path=output_pdf_path,
    )

    # 4. Post-Render Quality Validation
    validation_report = validate_rendered_magazine(
        pdf_path=output_pdf_path,
        page_previews=render_result["page_previews"],
        content=grounded_content,
        blueprint=blueprint,
    )

    return success({
        "pdf_url": f"/uploads/magazines/{pdf_filename}",
        "render_result": render_result,
        "validation_report": validation_report,
        "grounded_content": grounded_content,
    })


class AutoGenerateRequest(BaseModel):
    document_ids: list[int]
    template_id: int | None = None
    event_name: str | None = "SIET Engineering & Innovation Issue"
    event_date: str | None = "2026 Edition"


@admin_router.post("/auto-generate")
async def api_auto_generate_magazine(
    payload: AutoGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    Single-Call Automatic Magazine Generation Pipeline:
    1. Loads source document chunks for document_ids.
    2. Runs hybrid RAG retrieval per template section role.
    3. Generates grounded short digest-style content with word budgets & LLM retry shortening.
    4. Enforces confidence bands: Flags low-confidence sections instead of silently publishing hallucinations.
    5. Composes output document via DOCX Blueprint Composer / PDF Renderer.
    6. Verifies zero template text leakage via regression test assertion.
    """
    from app.modules.documents.models import DocumentChunk, SourceDocument
    from app.modules.template_engine.analyzer import analyze_docx_template
    from app.modules.template_engine.composer import generate_docx_from_blueprint
    from app.modules.template_engine.models import DocxTemplateBlueprint
    from app.modules.template_engine.test_leakage import verify_no_template_leakage

    if not payload.document_ids:
        raise HTTPException(status_code=400, detail="At least one document_id is required.")

    # 1. Fetch Source Documents & Chunks
    stmt = select(SourceDocument).where(SourceDocument.id.in_(payload.document_ids))
    docs_res = await db.execute(stmt)
    source_docs = docs_res.scalars().all()
    if not source_docs:
        raise HTTPException(status_code=404, detail=f"No source documents found for IDs: {payload.document_ids}")

    chunk_stmt = select(DocumentChunk).where(DocumentChunk.document_id.in_(payload.document_ids))
    chunks_res = await db.execute(chunk_stmt)
    chunks = chunks_res.scalars().all()

    combined_notes = "\n".join([c.text for c in chunks[:10]]) if chunks else "SIET engineering event proceedings."

    # 2. Template Selection (Default to Active / Blueprint)
    template_bytes = b""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    static_tmpl_path = os.path.join(base_dir, "static", "templates", "SIET-Magazine-Template.docx")
    siet_tmpl_path = static_tmpl_path if os.path.exists(static_tmpl_path) else "/home/shiva/Downloads/SIET-Magazine-Template.docx"

    if payload.template_id:
        record = await db.get(DocxTemplateBlueprint, payload.template_id)
        if record:
            blueprint = record.blueprint_json
        else:
            blueprint = None
    else:
        # Fallback to latest registered blueprint or analyze SIET template directly
        stmt_bp = select(DocxTemplateBlueprint).order_by(DocxTemplateBlueprint.id.desc()).limit(1)
        res_bp = await db.execute(stmt_bp)
        record = res_bp.scalars().first()
        blueprint = record.blueprint_json if record else None

    if os.path.exists(siet_tmpl_path):
        with open(siet_tmpl_path, "rb") as f:
            template_bytes = f.read()

    if not blueprint and template_bytes:
        blueprint = analyze_docx_template(template_bytes, "SIET-Magazine-Template.docx")

    if not blueprint:
        raise HTTPException(status_code=400, detail="No active DOCX template blueprint found.")

    # 3. Grounded Short Content Generation
    grounded_content = await generate_grounded_magazine_content(
        event_name=payload.event_name or "SIET Tech Digest",
        event_date=payload.event_date or "2026 Edition",
        raw_notes=combined_notes,
        photo_count=2,
        document_ids=payload.document_ids,
        db=db,
    )

    # 4. Confidence Band Enforcement & Section Flagging
    flagged_sections = []
    confidence_band = grounded_content.get("overall_confidence_band", "low_confidence")

    if confidence_band == "do_not_auto_publish":
        flagged_sections.append("article_body (Low Confidence: Flagged for manual editorial review)")
        grounded_content["writeup_text"] = "[FLAGGED FOR REVIEW: Confidence below publication threshold]"

    # 5. Compose Output Document
    output_docx_bytes = generate_docx_from_blueprint(
        blueprint=blueprint,
        content=grounded_content,
        template_bytes=template_bytes,
    )

    docx_filename = f"auto_generated_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6]}.docx"
    output_path = os.path.join("uploads/magazines", docx_filename)
    os.makedirs("uploads/magazines", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(output_docx_bytes)

    # 6. Template Leakage Assertion
    is_clean, leaked_phrases = verify_no_template_leakage(output_docx_bytes, template_bytes)
    leakage_status = "PASSED" if is_clean else f"FAILED ({len(leaked_phrases)} phrases leaked)"

    return success({
        "generated_file_url": f"/{output_path}",
        "issue_title": grounded_content.get("magazine_issue_title"),
        "description": grounded_content.get("description"),
        "writeup_headline": grounded_content.get("writeup_headline"),
        "writeup_text": grounded_content.get("writeup_text"),
        "overall_confidence_band": confidence_band,
        "flagged_sections": flagged_sections,
        "provenance": grounded_content.get("sources", []),
        "template_leakage_check": leakage_status,
    })



@admin_router.post("/generate/end-to-end")
async def api_generate_end_to_end_magazine(
    file: Optional[UploadFile] = File(None),
    photos: Optional[List[UploadFile]] = File(None),
    templates: Optional[List[UploadFile]] = File(None),
    event_name: Optional[str] = Form(None),
    event_date: Optional[str] = Form(None),
    department_or_lab: Optional[str] = Form("AI & Data Science Lab"),
    lab_id: Optional[int] = Form(None),
    template_id: Optional[Union[int, str]] = Form(None),
    raw_notes: Optional[str] = Form(None),
    target_page_budget: int = Form(5),
    publish_immediately: bool = Form(True),
    use_llm: bool = Form(True),
    max_qc_attempts: int = Form(3),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_lab_admin),
):
    """
    Complete End-to-End AI Magazine Generation Pipeline.
    Securely checks lab access and tags the generated magazine with user's lab and creator ID.
    """
    target_lab_id = await resolve_creation_lab(current_user, lab_id, db)

    file_bytes: Optional[bytes] = None
    filename: Optional[str] = None
    if file and file.filename:
        file_bytes = await file.read()
        filename = file.filename

    saved_photos: List[Dict[str, Any]] = []
    if photos:
        os.makedirs("uploads/magazines", exist_ok=True)
        for p in photos:
            if p.filename:
                p_bytes = await p.read()
                ext = os.path.splitext(p.filename)[1].lower() or ".jpg"
                p_id = f"photo_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6]}"
                p_name = f"{p_id}{ext}"
                p_path = os.path.join("uploads/magazines", p_name)
                with open(p_path, "wb") as f_out:
                    f_out.write(p_bytes)
                saved_photos.append({
                    "id": p_id,
                    "url": f"/uploads/magazines/{p_name}",
                    "file_path": p_path,
                    "filename": p.filename,
                })

    custom_tmpl_items: List[Dict[str, Any]] = []
    if templates:
        for t in templates:
            if t.filename:
                t_bytes = await t.read()
                custom_tmpl_items.append({
                    "filename": t.filename,
                    "bytes": t_bytes,
                })

    result = await run_end_to_end_magazine_pipeline(
        file_bytes=file_bytes,
        filename=filename,
        raw_notes=raw_notes,
        real_photos=saved_photos,
        custom_templates=custom_tmpl_items,
        department_or_lab=department_or_lab or "AI & Data Science Lab",
        event_name=event_name,
        event_date=event_date,
        target_page_budget=target_page_budget,
        publish_immediately=publish_immediately,
        use_llm=use_llm,
        max_qc_attempts=max_qc_attempts,
        lab_id=target_lab_id,
        created_by_id=current_user.id,
        template_id=template_id,
        db=db,
    )
    return success(result.model_dump())


@admin_router.post("/generate/end-to-end-json")
@router.post("/generate/end-to-end-json")
async def api_generate_end_to_end_magazine_json(
    payload: EndToEndMagazineRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    JSON entrypoint for End-to-End AI Magazine Generation Pipeline.
    Accepts raw notes or base64-encoded documents, real photo paths, and parameters.
    """
    import base64
    file_bytes: Optional[bytes] = None
    if payload.source_file_base64:
        try:
            file_bytes = base64.b64decode(payload.source_file_base64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 payload: {e}")

    result = await run_end_to_end_magazine_pipeline(
        file_bytes=file_bytes,
        filename=payload.source_filename,
        raw_notes=payload.raw_notes,
        real_photos=payload.photos,
        custom_templates=payload.custom_templates,
        department_or_lab=payload.department_or_lab or "AI & Data Science Lab",
        event_name=payload.event_name,
        event_date=payload.event_date,
        target_page_budget=payload.target_page_budget,
        publish_immediately=payload.publish_immediately,
        use_llm=payload.use_llm,
        max_qc_attempts=payload.max_qc_attempts,
        template_id=payload.template_id,
        db=db,
    )
    return success(result.model_dump())
