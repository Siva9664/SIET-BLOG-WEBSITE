import zoneinfo
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.models import PageView
from app.modules.articles.models import Article
from app.modules.auth.models import User
from app.modules.engagement.models import Like
from app.modules.magazine.models import Magazine
from app.modules.news.models import News
from app.shared.types.content import ContentStatus


class AdminRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dashboard_totals(self) -> dict[str, int]:
        users_count = await self.db.scalar(select(func.count()).select_from(User))
        news_count = await self.db.scalar(select(func.count()).select_from(News))
        articles_count = await self.db.scalar(select(func.count()).select_from(Article))
        magazines_count = await self.db.scalar(select(func.count()).select_from(Magazine))
        
        return {
            "users": users_count or 0,
            "news": news_count or 0,
            "articles": articles_count or 0,
            "magazines": magazines_count or 0,
        }

    async def get_today_accuracy(self) -> dict[str, Any]:
        kolkata_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        today_kolkata = datetime.now(kolkata_tz).date()

        stmt_today = select(News).where(
            func.date(News.created_at.op("AT TIME ZONE")("Asia/Kolkata")) == today_kolkata
        )
        res_today = list((await self.db.execute(stmt_today)).scalars().all())

        total = len(res_today)
        verified = sum(
            1 for n in res_today
            if getattr(n, "processing_status", "processed") in ("processed", None) and n.status == ContentStatus.PUBLISHED
        )
        flagged = sum(
            1 for n in res_today
            if getattr(n, "processing_status", None) == "flagged_for_review"
        )
        failed = sum(
            1 for n in res_today
            if getattr(n, "processing_status", None) == "failed"
        )

        return {
            "date": today_kolkata.isoformat(),
            "verified": verified,
            "flagged": flagged,
            "failed": failed,
            "total": total,
        }

    async def get_recent_activity(self) -> list:
        news_rows = await self.db.scalars(select(News).order_by(News.created_at.desc()).limit(5))
        article_rows = await self.db.scalars(select(Article).order_by(Article.created_at.desc()).limit(5))
        
        activities: list[dict[str, Any]] = []
        for n in news_rows:
            activities.append({
                "id": n.id,
                "type": "news",
                "title": n.title,
                "created_at": n.created_at
            })
        for a in article_rows:
            activities.append({
                "id": a.id,
                "type": "article",
                "title": a.title,
                "created_at": a.created_at
            })
        
        activities.sort(key=lambda x: x["created_at"], reverse=True)
        return activities[:10]

    async def get_analytics(self) -> dict[str, Any]:
        views_count = await self.db.scalar(select(func.count()).select_from(PageView))
        likes_count = await self.db.scalar(select(func.count()).select_from(Like))
        
        return {
            "views": [{"date": "total", "count": views_count or 0}],
            "topContent": [],
            "likesOverTime": [{"date": "total", "count": likes_count or 0}]
        }
