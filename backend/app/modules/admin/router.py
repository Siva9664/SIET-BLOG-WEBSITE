
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.admin.repository import AdminRepository
from app.modules.admin.schemas import (
    AdminArticleCreate,
    AdminArticleUpdate,
    AdminMagazineCreate,
    AdminMagazineUpdate,
    AdminNewsCreate,
    AdminNewsUpdate,
    AdminUserCreate,
    AdminUserUpdate,
    AnalyticsResponse,
    DashboardResponse,
)
from app.modules.admin.service import AdminService
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository
from app.modules.contract_helpers import (
    serialize_article,
    serialize_domain,
    serialize_magazine,
    serialize_news,
    serialize_tag,
    serialize_user,
)
from app.modules.news.repository import NewsRepository
from app.modules.news.schemas import NewsPublish
from app.modules.news.service import NewsService
from pydantic import BaseModel, EmailStr
from app.shared.auth.dependencies import require_admin, require_super_admin
from app.shared.types.content import ContentStatus

router = APIRouter(prefix="/admin", tags=["Admin"])

# DASHBOARD & ANALYTICS
@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = AdminService(AdminRepository(db))
    return await service.get_dashboard()

@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = AdminService(AdminRepository(db))
    return await service.get_analytics()

# NEWS CRUD
@router.get("/news")
async def admin_list_news(
    cursor: str | None = Query(None),
    status: str | None = Query("active"),
    department: str | None = Query(None),
    subcategory: str | None = Query(None),
    source_id: int | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    processing_status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = NewsService(NewsRepository(db))
    archived_status = "active"
    content_status = None

    if status in ("active", "archived", "all"):
        archived_status = status
    elif status and status.lower() != "all":
        try:
            content_status = ContentStatus(status.lower())
        except ValueError:
            pass

    items, page_info = await service.list_admin_news(
        limit=20,
        cursor=cursor,
        archived_status=archived_status,
        department=department,
        subcategory=subcategory,
        source_id=source_id,
        start_date=start_date,
        end_date=end_date,
        processing_status=processing_status,
        status=content_status,
    )
    return {"items": [await serialize_news(db, item) for item in items], "pageInfo": page_info.model_dump()}

@router.post("/news", status_code=status.HTTP_201_CREATED)
async def admin_create_news(
    payload: AdminNewsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = NewsService(NewsRepository(db))
    news = await service.create_news(payload)
    
    if payload.status == ContentStatus.PUBLISHED:
        news = await service.publish_news(news.id, NewsPublish(status=ContentStatus.PUBLISHED))

    return await serialize_news(db, news)

@router.put("/news/{news_id}")
async def admin_update_news(
    news_id: int,
    payload: AdminNewsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = NewsService(NewsRepository(db))
    news = await service.update_news(news_id, payload)

    if payload.status and payload.status != news.status:
        news = await service.publish_news(news_id, NewsPublish(status=payload.status))

    return await serialize_news(db, news)

@router.delete("/news/{news_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_news(
    news_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = NewsService(NewsRepository(db))
    await service.delete_news(news_id)
    return None

@router.post("/news/trigger-fetch")
async def admin_trigger_news_fetch(
    current_user: User = Depends(require_admin)
):
    from app.modules.news.pipeline import run_sync_pipeline
    res = await run_sync_pipeline(is_full_sync=True)
    return {"message": "Live web news research and ingestion completed successfully.", "details": res}

# USERS CRUD
@router.get("/users")
async def admin_list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    users = list((await db.execute(select(User).order_by(User.id))).scalars().all())
    return [serialize_user(u) for u in users]

@router.post("/users", status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    payload: AdminUserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    from app.core.security import hash_password
    
    repo = UserRepository(db)
    if await repo.exists(payload.email):
        raise HTTPException(status_code=409, detail="User already exists")
        
    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        email_verified=payload.email_verified
    )
    user = await repo.create(user)
    await repo.db.refresh(user)
    return serialize_user(user)

@router.put("/users/{user_id}")
async def admin_update_user(
    user_id: str,
    payload: AdminUserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    from app.core.security import hash_password

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.name is not None:
        user.name = payload.name
    if payload.email is not None:
        user.email = payload.email
    if payload.role is not None:
        user.role = payload.role
    if payload.email_verified is not None:
        user.email_verified = payload.email_verified
    if payload.password is not None and payload.password.strip():
        user.password_hash = hash_password(payload.password)
    await repo.update(user)
    return serialize_user(user)

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await repo.delete(user)
    return None

# ADMIN ACCOUNTS MANAGEMENT (SUPER_ADMIN ONLY)
class AdminAccountCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "ADMIN"


@router.get("/admins")
async def list_admin_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    stmt = (
        select(User)
        .where(User.role.in_(["ADMIN", "SUPER_ADMIN", "admin", "super_admin"]))
        .order_by(User.id.asc())
    )
    users = list((await db.execute(stmt)).scalars().all())
    return [
        {
            "id": str(u.id),
            "name": u.name,
            "email": u.email,
            "role": u.role.upper(),
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if hasattr(u, "created_at") and u.created_at else None,
        }
        for u in users
    ]


@router.post("/admins", status_code=status.HTTP_201_CREATED)
async def create_admin_account(
    payload: AdminAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    from app.core.security import hash_password

    repo = UserRepository(db)
    if await repo.exists(payload.email):
        raise HTTPException(status_code=409, detail="An account with this email address already exists.")

    target_role = payload.role.upper().strip()
    if target_role not in ("ADMIN", "SUPER_ADMIN"):
        target_role = "ADMIN"

    user = User(
        name=payload.name.strip(),
        email=payload.email.strip().lower(),
        password_hash=hash_password(payload.password),
        role=target_role,
        is_active=True,
        is_verified=True,
        email_verified=True,
    )
    user = await repo.create(user)
    await db.commit()
    await repo.db.refresh(user)
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role.upper(),
        "is_active": user.is_active,
    }


@router.delete("/admins/{admin_id}")
async def delete_admin_account(
    admin_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    from sqlalchemy import func

    if current_user.id == admin_id:
        raise HTTPException(status_code=400, detail="You cannot delete your own administrative account.")

    repo = UserRepository(db)
    target_user = await repo.get_by_id(admin_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Admin account not found.")

    if target_user.role.upper() == "SUPER_ADMIN":
        super_admin_count_stmt = (
            select(func.count())
            .select_from(User)
            .where(User.role.in_(["SUPER_ADMIN", "super_admin"]))
        )
        super_admin_count = await db.scalar(super_admin_count_stmt) or 0
        if super_admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete account: At least one Super Administrator must remain registered."
            )

    await repo.delete(target_user)
    await db.commit()
    return {"message": f"Admin account '{target_user.email}' deleted successfully."}

# ARTICLES CRUD
from app.modules.articles.repository import ArticleRepository
from app.modules.articles.schemas import ArticlePublish
from app.modules.articles.service import ArticleService


@router.get("/articles")
async def admin_list_articles(
    cursor: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = ArticleService(ArticleRepository(db))
    content_status = ContentStatus(status.lower()) if status and status.lower() != "all" else None
    items, page_info = await service.list_articles(limit=20, cursor=cursor, status=content_status)
    return {"items": [await serialize_article(db, item) for item in items], "pageInfo": page_info.model_dump()}

@router.post("/articles", status_code=status.HTTP_201_CREATED)
async def admin_create_article(
    payload: AdminArticleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = ArticleService(ArticleRepository(db))
    article = await service.create_article(payload)
    if payload.status == ContentStatus.PUBLISHED:
        article = await service.publish_article(article.id, ArticlePublish(status=ContentStatus.PUBLISHED))
    return await serialize_article(db, article)

@router.put("/articles/{article_id}")
async def admin_update_article(
    article_id: int,
    payload: AdminArticleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = ArticleService(ArticleRepository(db))
    article = await service.update_article(article_id, payload)
    if payload.status and payload.status != article.status:
        article = await service.publish_article(article_id, ArticlePublish(status=payload.status))
    return await serialize_article(db, article)

@router.delete("/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = ArticleService(ArticleRepository(db))
    await service.delete_article(article_id)
    return None

# MAGAZINE CRUD
from app.modules.magazine.repository import MagazineRepository
from app.modules.magazine.schemas import MagazinePublish
from app.modules.magazine.service import MagazineService


@router.get("/magazine")
async def admin_list_magazine(
    cursor: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = MagazineService(MagazineRepository(db))
    content_status = ContentStatus(status.lower()) if status and status.lower() != "all" else None
    items, page_info = await service.list_magazines(limit=20, cursor=cursor, status=content_status)
    return {"items": [await serialize_magazine(db, item) for item in items], "pageInfo": page_info.model_dump()}

@router.post("/magazine", status_code=status.HTTP_201_CREATED)
async def admin_create_magazine(
    payload: AdminMagazineCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = MagazineService(MagazineRepository(db))
    magazine = await service.create_magazine(payload)
    if payload.status == ContentStatus.PUBLISHED:
        magazine = await service.publish_magazine(magazine.id, MagazinePublish(status=ContentStatus.PUBLISHED))
    # Re-fetch with achievements/project_links eagerly loaded — serialize_magazine
    # accesses those relationships, and the object returned above only has them
    # loaded if get_magazine() (which eager-loads) was the last thing to touch it.
    magazine = await service.get_magazine(magazine.id)
    return await serialize_magazine(db, magazine)

@router.put("/magazine/{magazine_id}")
async def admin_update_magazine(
    magazine_id: int,
    payload: AdminMagazineUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = MagazineService(MagazineRepository(db))
    magazine = await service.update_magazine(magazine_id, payload)
    if payload.status and payload.status != magazine.status:
        magazine = await service.publish_magazine(magazine_id, MagazinePublish(status=payload.status))
    magazine = await service.get_magazine(magazine.id)
    return await serialize_magazine(db, magazine)

@router.delete("/magazine/{magazine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_magazine(
    magazine_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = MagazineService(MagazineRepository(db))
    await service.delete_magazine(magazine_id)
    return None

# DOMAINS CRUD
from app.modules.domains.repository import DomainRepository
from app.modules.domains.schemas import DomainCreate, DomainUpdate
from app.modules.domains.service import DomainService


@router.get("/domains")
async def admin_list_domains(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = DomainService(DomainRepository(db))
    return [serialize_domain(d) for d in await service.list_domains()]

@router.post("/domains", status_code=status.HTTP_201_CREATED)
async def admin_create_domain(
    payload: DomainCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = DomainService(DomainRepository(db))
    return serialize_domain(await service.create_domain(payload))

@router.put("/domains/{slug}")
async def admin_update_domain(
    slug: str,
    payload: DomainUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = DomainService(DomainRepository(db))
    return serialize_domain(await service.update_domain(slug, payload))

@router.delete("/domains/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_domain(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    import logging

    from sqlalchemy.exc import IntegrityError

    from app.shared.responses.errors import conflict_error
    logger = logging.getLogger(__name__)

    service = DomainService(DomainRepository(db))
    try:
        await service.delete_domain(slug)
    except IntegrityError as e:
        logger.error(f"IntegrityError deleting domain {slug}: {str(e)}")
        raise conflict_error(
            message="Cannot delete domain: it is still referenced by existing content."
        )
    return None

# TAGS CRUD
from app.modules.tags.repository import TagRepository
from app.modules.tags.schemas import TagCreate, TagUpdate
from app.modules.tags.service import TagService


@router.get("/tags")
async def admin_list_tags(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = TagService(TagRepository(db))
    return [serialize_tag(t) for t in await service.list_tags()]

@router.post("/tags", status_code=status.HTTP_201_CREATED)
async def admin_create_tag(
    payload: TagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = TagService(TagRepository(db))
    return serialize_tag(await service.create_tag(payload))

@router.put("/tags/{tag_id}")
async def admin_update_tag(
    tag_id: int,
    payload: TagUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = TagService(TagRepository(db))
    return serialize_tag(await service.update_tag(tag_id, payload))

@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_tag(
    tag_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = TagService(TagRepository(db))
    await service.delete_tag(tag_id)
    return None

# FEATURED (not yet implemented — no `featured` table exists)
@router.get("/featured")
async def get_featured(current_user: User = Depends(require_admin)):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Featured content is not yet implemented.")

@router.post("/featured")
async def create_featured(current_user: User = Depends(require_admin)):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Featured content is not yet implemented.")

@router.delete("/featured/{id}")
async def delete_featured(id: int, current_user: User = Depends(require_admin)):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Featured content is not yet implemented.")
