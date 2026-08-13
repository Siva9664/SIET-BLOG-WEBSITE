from datetime import datetime
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.news.models import News
from app.shared.repository.base import BaseRepository
from app.shared.types.content import ContentStatus


class NewsRepository(BaseRepository[News]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, News)

    async def get_by_slug(self, slug: str) -> News | None:
        result = await self.db.execute(select(News).where(News.slug == slug))
        return result.scalars().first()

    async def get_paginated(
        self, 
        limit: int = 20, 
        cursor_id: int | None = None, 
        status: ContentStatus | None = None
    ) -> list[News]:
        query = select(News)
        
        if status:
            query = query.where(News.status == status)
            
        if cursor_id is not None:
            query = query.where(News.id < cursor_id)
            
        # Default order by descending ID for cursor pagination
        query = query.order_by(desc(News.id)).limit(limit + 1)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_admin_paginated(
        self,
        limit: int = 20,
        cursor_id: int | None = None,
        archived_status: str | None = "active",  # "active" | "archived" | "all"
        department: str | None = None,
        subcategory: str | None = None,
        source_id: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        processing_status: str | None = None,
        content_status: ContentStatus | None = None,
    ) -> list[News]:
        query = select(News)

        if archived_status == "active":
            query = query.where(News.is_archived == False)
        elif archived_status == "archived":
            query = query.where(News.is_archived == True)
        # "all" does not apply an is_archived filter

        if content_status:
            query = query.where(News.status == content_status)

        if processing_status and processing_status != "all":
            query = query.where(News.processing_status == processing_status)

        if department and department != "all":
            query = query.where(News.department == department)

        if subcategory and subcategory != "all":
            query = query.where(News.subcategory == subcategory)

        if source_id:
            query = query.where(News.source_id == source_id)

        if start_date:
            try:
                dt_start = datetime.fromisoformat(start_date)
                query = query.where(News.published_at >= dt_start)
            except ValueError:
                pass

        if end_date:
            try:
                dt_end = datetime.fromisoformat(end_date)
                query = query.where(News.published_at <= dt_end)
            except ValueError:
                pass

        if cursor_id is not None:
            query = query.where(News.id < cursor_id)

        query = query.order_by(desc(News.id)).limit(limit + 1)
        result = await self.db.execute(query)
        return list(result.scalars().all())
