from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.contract_helpers import (
    get_domain_map,
    get_media_map,
    normalize_limit,
    normalize_page,
    paginated_payload,
    search_filter,
    serialize_news,
)
from app.modules.domains.models import Domain
from app.modules.engagement.router import (
    bookmark_contract,
    bookmark_status_contract,
    like_contract,
    like_status_contract,
    unbookmark_contract,
    unlike_contract,
)
from app.modules.news.models import News, Source, SyncLog
from app.modules.news.pipeline import run_sync_pipeline
from app.shared.exceptions.custom import NotFoundException
from app.shared.types.content import ContentKind, ContentStatus

router = APIRouter(prefix="/news", tags=["News"])


def _current_user_id(request: Request) -> int | None:
    return int(request.state.user) if getattr(request.state, "user", None) else None


class SourceCreateSchema(BaseModel):
    name: str
    department: str = "ai-ml"
    feed_type: str = "rss"
    feed_url: str
    is_active: bool = True


async def _news_page(
    db: AsyncSession,
    request: Request,
    page: int,
    limit: int,
    department: str | None = None,
    subcategory: str | None = None,
    domain: str | None = None,
    q: str | None = None,
    tab: str | None = None,
    date_filter: str | None = None,
    include_archived: bool = False,
    archived_only: bool = False,
):
    page = normalize_page(page)
    limit = normalize_limit(limit)
    query = select(News).where(News.status == ContentStatus.PUBLISHED)
    count_query = select(func.count()).select_from(News).where(News.status == ContentStatus.PUBLISHED)

    if archived_only:
        query = query.where(News.is_archived == True)
        count_query = count_query.where(News.is_archived == True)
    elif not include_archived:
        query = query.where(News.is_archived == False)
        count_query = count_query.where(News.is_archived == False)

    if date_filter == "today":
        import zoneinfo
        from datetime import datetime
        kolkata_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        today_kolkata = datetime.now(kolkata_tz).date()
        today_pred = func.date(func.coalesce(News.published_at, News.created_at).op("AT TIME ZONE")("Asia/Kolkata")) == today_kolkata
        query = query.where(today_pred)
        count_query = count_query.where(today_pred)

    if department:
        query = query.where(News.department == department)
        count_query = count_query.where(News.department == department)

    if subcategory:
        query = query.where(News.subcategory == subcategory)
        count_query = count_query.where(News.subcategory == subcategory)

    if domain:
        domain_obj = (await db.execute(select(Domain).where(Domain.slug == domain))).scalars().first()
        if not domain_obj:
            return paginated_payload([], page, limit, 0)
        query = query.where(News.domain_id == domain_obj.id)
        count_query = count_query.where(News.domain_id == domain_obj.id)

    if q:
        predicate = search_filter(News, q)
        query = query.where(predicate)
        count_query = count_query.where(predicate)

    if tab == "trending":
        query = query.order_by(News.likes.desc().nullslast(), News.published_at.desc().nullslast(), News.id.desc())
    elif tab == "latest":
        query = query.order_by(News.published_at.desc().nullslast(), News.id.desc())
    else:
        query = query.order_by(News.published_at.desc().nullslast(), News.id.desc())

    total = await db.scalar(count_query) or 0
    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    rows = list(result.scalars().all())
    domains = await get_domain_map(db)
    media = await get_media_map(db)
    items = [await serialize_news(db, row, domains=domains, media=media, current_user_id=_current_user_id(request)) for row in rows]
    return paginated_payload(items, page, limit, total)


@router.get("")
async def list_news(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    department: str | None = Query(None),
    subcategory: str | None = Query(None),
    domain: str | None = Query(None),
    q: str | None = Query(None),
    tab: str | None = Query(None),
    date_filter: str | None = Query("today"),
    include_archived: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    return await _news_page(
        db,
        request,
        page,
        limit,
        department=department,
        subcategory=subcategory,
        domain=domain,
        q=q,
        tab=tab,
        date_filter=date_filter,
        include_archived=include_archived,
    )


@router.get("/archived")
async def list_archived_news(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    department: str | None = Query(None),
    q: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await _news_page(db, request, page, limit, department=department, q=q, archived_only=True)


@router.get("/latest")
async def latest_news(
    request: Request,
    limit: int = Query(6, ge=1, le=50),
    department: str | None = Query(None),
    domain: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    payload = await _news_page(db, request, 1, limit, department=department, domain=domain, tab="latest", date_filter="today")
    return payload["items"]


@router.get("/trending")
async def trending_news(
    request: Request,
    limit: int = Query(6, ge=1, le=50),
    department: str | None = Query(None),
    domain: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    payload = await _news_page(db, request, 1, limit, department=department, domain=domain, tab="trending", date_filter="today")
    return payload["items"]


@router.get("/taxonomy")
async def get_taxonomy(
    date_filter: str | None = Query("today"),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns counts by department and subcategory for active non-archived articles.
    """
    dept_stmt = (
        select(News.department, func.count(News.id))
        .where(News.status == ContentStatus.PUBLISHED, News.is_archived == False)
    )
    sub_stmt = (
        select(News.department, News.subcategory, func.count(News.id))
        .where(News.status == ContentStatus.PUBLISHED, News.is_archived == False)
    )

    if date_filter == "today":
        import zoneinfo
        from datetime import datetime
        kolkata_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        today_kolkata = datetime.now(kolkata_tz).date()
        today_pred = func.date(func.coalesce(News.published_at, News.created_at).op("AT TIME ZONE")("Asia/Kolkata")) == today_kolkata
        dept_stmt = dept_stmt.where(today_pred)
        sub_stmt = sub_stmt.where(today_pred)

    dept_stmt = dept_stmt.group_by(News.department)
    sub_stmt = sub_stmt.group_by(News.department, News.subcategory)

    dept_rows = (await db.execute(dept_stmt)).all()
    departments = {dept: count for dept, count in dept_rows}

    sub_rows = (await db.execute(sub_stmt)).all()
    subcategories: Dict[str, Any] = {}
    for dept, sub, count in sub_rows:
        if dept not in subcategories:
            subcategories[dept] = []
        if sub:
            subcategories[dept].append({"name": sub, "count": count})

    return {
        "departments": departments,
        "subcategories": subcategories,
    }


@router.post("/sync")
async def trigger_news_sync(background_tasks: BackgroundTasks):
    """
    Triggers news aggregation pipeline execution in background
    """
    background_tasks.add_task(run_sync_pipeline, is_full_sync=True)
    return {"message": "News aggregation sync triggered in background.", "status": "processing"}


@router.get("/sources")
async def list_sources(db: AsyncSession = Depends(get_db)):
    stmt = select(Source).order_by(Source.name.asc())
    result = await db.execute(stmt)
    sources = result.scalars().all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "department": s.department,
            "feed_type": s.feed_type,
            "feed_url": s.feed_url,
            "is_active": s.is_active,
            "last_success_at": s.last_success_at.isoformat() if s.last_success_at else None,
            "error_count": s.error_count,
        }
        for s in sources
    ]


@router.post("/sources")
async def create_source(payload: SourceCreateSchema, db: AsyncSession = Depends(get_db)):
    source = Source(
        name=payload.name,
        department=payload.department,
        feed_type=payload.feed_type,
        feed_url=payload.feed_url,
        is_active=payload.is_active,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return {"id": source.id, "name": source.name, "feed_url": source.feed_url, "is_active": source.is_active}


@router.delete("/sources/{source_id}")
async def delete_source(source_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Source).where(Source.id == source_id)
    source = (await db.execute(stmt)).scalars().first()
    if not source:
        raise NotFoundException("Source not found")
    await db.delete(source)
    await db.commit()
    return {"message": "Source deleted successfully"}


@router.get("/logs")
async def get_sync_logs(limit: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    stmt = select(SyncLog).order_by(SyncLog.run_at.desc()).limit(limit)
    result = await db.execute(stmt)
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "run_at": l.run_at.isoformat(),
            "duration_seconds": l.duration_seconds,
            "sources_checked": l.sources_checked,
            "articles_discovered": l.articles_discovered,
            "articles_new": l.articles_new,
            "articles_duplicate": l.articles_duplicate,
            "articles_failed": l.articles_failed,
            "status": l.status,
            "log_details": l.log_details,
        }
        for l in logs
    ]


@router.get("/domain/{domain}")
async def news_by_domain(
    domain: str,
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    tab: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await _news_page(db, request, page, limit, domain=domain, tab=tab)


@router.get("/search")
async def search_news(
    q: str,
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await _news_page(db, request, page, limit, q=q)


@router.get("/{slug}")
async def get_news_by_slug(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(select(News).where(News.slug == slug))).scalars().first()
    if not row:
        raise NotFoundException("News item not found.")
    return await serialize_news(db, row, current_user_id=_current_user_id(request))


@router.get("/{slug}/like/status")
async def news_like_status(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await like_status_contract(db, request, News, slug, ContentKind.NEWS)


@router.post("/{slug}/like")
async def news_like(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await like_contract(db, request, News, slug, ContentKind.NEWS)


@router.delete("/{slug}/like")
async def news_unlike(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await unlike_contract(db, request, News, slug, ContentKind.NEWS)


@router.get("/{slug}/bookmark/status")
async def news_bookmark_status(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await bookmark_status_contract(db, request, News, slug, ContentKind.NEWS)


@router.post("/{slug}/bookmark")
async def news_bookmark(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await bookmark_contract(db, request, News, slug, ContentKind.NEWS)


@router.delete("/{slug}/bookmark")
async def news_unbookmark(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await unbookmark_contract(db, request, News, slug, ContentKind.NEWS)
