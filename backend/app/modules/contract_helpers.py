from __future__ import annotations

from collections.abc import Sequence
from math import ceil
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.articles.models import Article
from app.modules.auth.models import User
from app.modules.domains.models import Domain
from app.modules.engagement.models import Bookmark, Like
from app.modules.magazine.models import Magazine
from app.modules.media.models import Media
from app.modules.news.models import News
from sqlalchemy.orm import attributes
from app.modules.tags.models import Tag
from app.shared.types.content import ContentKind


def _is_loaded(instance: Any, prop: str) -> bool:
    try:
        return prop in attributes.instance_state(instance).dict
    except Exception:
        return False


async def get_domain_map(db: AsyncSession) -> dict[int, Domain]:
    result = await db.execute(select(Domain))
    return {domain.id: domain for domain in result.scalars().all()}


async def get_user_map(db: AsyncSession) -> dict[int, User]:
    result = await db.execute(select(User))
    return {user.id: user for user in result.scalars().all()}


async def get_media_map(db: AsyncSession) -> dict[int, Media]:
    result = await db.execute(select(Media))
    return {media.id: media for media in result.scalars().all()}


async def like_count(db: AsyncSession, content_id: int, kind: ContentKind) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Like)
        .where(Like.content_id == content_id, Like.content_kind == kind)
    )
    return result.scalar() or 0


async def is_bookmarked(
    db: AsyncSession,
    content_id: int,
    kind: ContentKind,
    user_id: int | None,
) -> bool:
    if not user_id:
        return False
    result = await db.execute(
        select(Bookmark.id).where(
            Bookmark.user_id == user_id,
            Bookmark.content_id == content_id,
            Bookmark.content_kind == kind,
        )
    )
    return result.scalar() is not None


async def is_liked(
    db: AsyncSession,
    content_id: int,
    kind: ContentKind,
    user_id: int | None,
) -> bool:
    if not user_id:
        return False
    result = await db.execute(
        select(Like.id).where(
            Like.user_id == user_id,
            Like.content_id == content_id,
            Like.content_kind == kind,
        )
    )
    return result.scalar() is not None


async def get_like_counts_map(db: AsyncSession, kind: ContentKind, content_ids: list[int]) -> dict[int, int]:
    if not content_ids:
        return {}
    result = await db.execute(
        select(Like.content_id, func.count())
        .where(Like.content_kind == kind, Like.content_id.in_(content_ids))
        .group_by(Like.content_id)
    )
    return {row[0]: row[1] for row in result.all()}


async def get_user_likes_set(db: AsyncSession, user_id: int | None, kind: ContentKind, content_ids: list[int]) -> set[int]:
    if not user_id or not content_ids:
        return set()
    result = await db.execute(
        select(Like.content_id)
        .where(Like.user_id == user_id, Like.content_kind == kind, Like.content_id.in_(content_ids))
    )
    return set(result.scalars().all())


async def get_user_bookmarks_set(db: AsyncSession, user_id: int | None, kind: ContentKind, content_ids: list[int]) -> set[int]:
    if not user_id or not content_ids:
        return set()
    result = await db.execute(
        select(Bookmark.content_id)
        .where(Bookmark.user_id == user_id, Bookmark.content_kind == kind, Bookmark.content_id.in_(content_ids))
    )
    return set(result.scalars().all())


async def get_coverage_map(db: AsyncSession, news_ids: list[int]) -> dict[int, list[Any]]:
    if not news_ids:
        return {}
    from app.modules.news.models import StoryCoverage
    result = await db.execute(
        select(StoryCoverage).where(StoryCoverage.news_id.in_(news_ids)).order_by(StoryCoverage.is_primary.desc())
    )
    cov_map: dict[int, list[Any]] = {}
    for cov in result.scalars().all():
        cov_map.setdefault(cov.news_id, []).append(cov)
    return cov_map


def domain_payload(domain: Domain | None) -> dict[str, Any]:
    if not domain:
        return {"slug": "general", "name": "General", "count": 0}
    return {"slug": domain.slug, "name": domain.name, "count": 0}


def user_payload(user: User | None) -> dict[str, Any]:
    if not user:
        return {"id": "0", "name": "SIET Editorial Desk", "role": "user"}
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role,
    }


def paginated_payload(items: Sequence[Any], page: int, limit: int, total: int) -> dict[str, Any]:
    pages = max(1, ceil(total / limit)) if limit else 1
    return {"items": list(items), "page": page, "pageSize": limit, "pages": pages, "total": total}


def normalize_page(page: int) -> int:
    return page if page > 0 else 1


def normalize_limit(limit: int) -> int:
    return min(max(limit, 1), 100)


def search_filter(model: Any, q: str | None):
    if not q:
        return None
    pattern = f"%{q}%"
    fields = [model.title]
    if hasattr(model, "content"):
        fields.append(model.content)
    if hasattr(model, "excerpt"):
        fields.append(model.excerpt)
    if hasattr(model, "description"):
        fields.append(model.description)
    return or_(*[field.ilike(pattern) for field in fields])


async def serialize_news(
    db: AsyncSession,
    item: News,
    domains: dict[int, Domain] | None = None,
    media: dict[int, Media] | None = None,
    current_user_id: int | None = None,
    coverage_map: dict[int, list[Any]] | None = None,
    likes_map: dict[int, int] | None = None,
    user_likes: set[int] | None = None,
    user_bookmarks: set[int] | None = None,
) -> dict[str, Any]:
    domains = domains or await get_domain_map(db)
    media = media or await get_media_map(db)
    kind = ContentKind.NEWS
    image = (
        item.image_url
        or (media[item.featured_image_id].public_url if item.featured_image_id is not None and item.featured_image_id in media else None)
        or "https://images.unsplash.com/photo-1677442136019-21780efad99a?auto=format&fit=crop&w=1200&q=80"
    )

    if coverage_map is not None:
        coverage_records = coverage_map.get(item.id, [])
    else:
        from app.modules.news.models import StoryCoverage
        coverage_q = await db.execute(
            select(StoryCoverage).where(StoryCoverage.news_id == item.id).order_by(StoryCoverage.is_primary.desc())
        )
        coverage_records = list(coverage_q.scalars().all())

    coverage_count = max(item.coverage_count or 1, len(coverage_records))
    verification_status = item.verification_status or ("confirmed" if coverage_count >= 2 else "single_source")

    coverage_payload = [
        {
            "id": str(c.id),
            "source_name": c.source_name,
            "title": c.title,
            "url": c.source_url,
            "published_at": c.published_at.isoformat() if c.published_at else item.published_at.isoformat(),
            "is_primary": c.is_primary,
        }
        for c in coverage_records
    ]

    likes_cnt = likes_map[item.id] if likes_map is not None and item.id in likes_map else (await like_count(db, item.id, kind) if likes_map is None else 0)
    liked_val = item.id in user_likes if user_likes is not None else await is_liked(db, item.id, kind, current_user_id)
    bookmarked_val = item.id in user_bookmarks if user_bookmarks is not None else await is_bookmarked(db, item.id, kind, current_user_id)

    return {
        "id": str(item.id),
        "slug": item.slug,
        "title": item.title,
        "content": item.content,
        "simple_explanation": item.simple_explanation or item.content_summary or item.excerpt or item.content[:220],
        "detailed_sections": item.detailed_sections or [
            {
                "heading": "Event Overview",
                "paragraphs": [item.detailed_summary or item.content]
            }
        ],
        "content_depth": item.content_depth or "summary_only",
        "contentSummary": item.content_summary or item.simple_explanation,
        "detailedSummary": item.detailed_summary,
        "keyPoints": item.key_points or [],
        "technicalDetails": item.technical_details,
        "whyItMatters": item.why_it_matters,
        "studentRelevance": item.student_relevance,
        "department": item.department or "ai-ml",
        "subcategory": item.subcategory or "General",
        "tags": item.tags_list or [item.department or "AI-ML"],
        "verification_status": verification_status,
        "coverage_count": coverage_count,
        "coverage": coverage_payload,
        "sourceUrl": getattr(item, "source_url", None) or "",
        "canonicalUrl": getattr(item, "canonical_url", None) or getattr(item, "source_url", None) or "",
        "sourceName": getattr(item, "source_name", None) or "SIET Tech News",
        "author": getattr(item, "author", None) or "SIET Tech News Desk",
        "domain": domain_payload(domains.get(item.domain_id) if item.domain_id is not None else None),
        "image": image,
        "imageUrl": image,
        "publishedAt": (item.published_at or item.created_at).isoformat(),
        "fetchedAt": item.fetched_at.isoformat() if item.fetched_at else None,
        "is_archived": getattr(item, "is_archived", False),
        "archived_at": item.archived_at.isoformat() if getattr(item, "archived_at", None) else None,
        "processing_status": getattr(item, "processing_status", "processed"),
        "processedAt": item.processed_at.isoformat() if item.processed_at else None,
        "trending": False,
        "likes": likes_cnt,
        "liked": liked_val,
        "bookmarked": bookmarked_val,
    }


async def serialize_article(
    db: AsyncSession,
    item: Article,
    domains: dict[int, Domain] | None = None,
    users: dict[int, User] | None = None,
    media: dict[int, Media] | None = None,
    current_user_id: int | None = None,
) -> dict[str, Any]:
    domains = domains or await get_domain_map(db)
    users = users or await get_user_map(db)
    media = media or await get_media_map(db)
    kind = ContentKind.ARTICLE
    cover = media[item.featured_image_id].public_url if item.featured_image_id is not None and item.featured_image_id in media else None
    return {
        "id": str(item.id),
        "slug": item.slug,
        "title": item.title,
        "excerpt": item.excerpt or item.content[:220],
        "body": item.content,
        "author": user_payload(users.get(item.author_id) if item.author_id is not None else None),
        "domain": domain_payload(domains.get(item.domain_id) if item.domain_id is not None else None),
        "tags": [],
        "cover": cover,
        "publishedAt": (item.published_at or item.created_at).isoformat(),
        "readingMinutes": item.reading_time_minutes,
        "likes": await like_count(db, item.id, kind),
        "liked": await is_liked(db, item.id, kind, current_user_id),
        "bookmarked": await is_bookmarked(db, item.id, kind, current_user_id),
    }


async def serialize_magazine(
    db: AsyncSession,
    item: Magazine,
    domains: dict[int, Domain] | None = None,
    media: dict[int, Media] | None = None,
    current_user_id: int | None = None,
) -> dict[str, Any]:
    media = media or await get_media_map(db)
    kind = ContentKind.MAGAZINE
    gallery = []
    if item.cover_image_id in media:
        gallery.append(media[item.cover_image_id].public_url)
    if item.cover_image_url and item.cover_image_url not in gallery:
        gallery.append(item.cover_image_url)

    pdf_url = item.pdf_url
    if not pdf_url and item.pdf_file_id is not None and item.pdf_file_id in media:
        pdf_url = media[item.pdf_file_id].public_url

    cover_url = item.cover_image_url or (gallery[0] if gallery else None)

    pages = []
    if _is_loaded(item, "pages") and item.pages:
        pages = [
            {
                "id": str(p.id),
                "pageNumber": p.page_number,
                "imageUrl": p.image_url,
                "extractedText": p.extracted_text or "",
            }
            for p in item.pages
        ]

    toc_entries = []
    if _is_loaded(item, "toc_entries") and item.toc_entries:
        toc_entries = [
            {
                "id": str(t.id),
                "pageNumber": t.page_number,
                "heading": t.heading,
            }
            for t in item.toc_entries
        ]

    return {
        "id": str(item.id),
        "slug": item.slug,
        "title": item.title,
        "description": item.description or "",
        "year": item.publication_year,
        "type": item.magazine_type.value if hasattr(item.magazine_type, "value") else str(item.magazine_type),
        "status": getattr(item, "status", "published"),
        "failureReason": getattr(item, "failure_reason", None),
        "pageCount": getattr(item, "page_count", 0),
        "pdfUrl": pdf_url,
        "certificateUrl": pdf_url,
        "coverImageUrl": cover_url,
        "gallery": gallery,
        "pages": pages,
        "tocEntries": toc_entries,
        "issueDate": item.issue_date.isoformat() if getattr(item, "issue_date", None) else item.created_at.isoformat(),
        "projectLinks": [
            {"label": link.title, "url": link.url}
            for link in getattr(item, "project_links", [])
        ],
        "likes": await like_count(db, item.id, kind),
        "liked": await is_liked(db, item.id, kind, current_user_id),
        "bookmarked": await is_bookmarked(db, item.id, kind, current_user_id),
    }


def serialize_domain(item: Domain, count: int = 0) -> dict[str, Any]:
    return {"slug": item.slug, "name": item.name, "count": count}


def serialize_tag(item: Tag) -> dict[str, Any]:
    return {"slug": item.slug, "name": item.name}


def serialize_media(item: Media) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "url": item.public_url,
        "filename": item.filename,
        "uploadedAt": item.created_at.isoformat(),
        "mimeType": item.mime_type,
        "sizeBytes": item.size_bytes,
        "mediaType": item.media_type.value,
    }


def serialize_user(item: User) -> dict[str, Any]:
    return {"id": str(item.id), "name": item.name, "email": item.email, "role": item.role}
