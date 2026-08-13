from datetime import datetime, timedelta, timezone
from sqlalchemy import select

import app.modules.media.models  # Ensure foreign key resolution
import app.modules.auth.models
import app.modules.domains.models

from app.core.database import async_session_maker
from app.core.logging import logger
from app.core.config import settings
from app.modules.news.models import News, SyncLog
from app.shared.types.content import ContentStatus


async def archive_old_news(days: int | None = None) -> int:
    """
    Finds all published news articles where published_at is older than `days` (default: 30)
    and marks them `is_archived = True` with `archived_at = now()`.
    
    CRITICAL: NO ROWS ARE DELETED FROM THE DATABASE.
    Returns the count of newly archived articles.
    """
    days = days if days is not None else settings.NEWS_ARCHIVE_AFTER_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with async_session_maker() as session:
        stmt = (
            select(News)
            .where(News.status == ContentStatus.PUBLISHED)
            .where(News.is_archived == False)
            .where(News.published_at < cutoff)
        )
        result = await session.execute(stmt)
        articles_to_archive = result.scalars().all()

        count = len(articles_to_archive)
        now_ts = datetime.now(timezone.utc)

        if count > 0:
            for article in articles_to_archive:
                article.is_archived = True
                article.archived_at = now_ts

            log_entry = SyncLog(
                run_at=now_ts,
                duration_seconds=0.1,
                sources_checked=1,
                articles_discovered=count,
                articles_new=0,
                articles_duplicate=0,
                articles_failed=0,
                status="success",
                log_details={
                    "action": "daily_archiving",
                    "archived_count": count,
                    "cutoff_days": days,
                    "cutoff_timestamp": cutoff.isoformat(),
                },
            )
            session.add(log_entry)
            await session.commit()
            logger.info(f"[ARCHIVER] Successfully archived {count} news articles older than {days} days (cutoff: {cutoff.isoformat()}). NO ROWS DELETED.")
        else:
            logger.info(f"[ARCHIVER] Checked old articles — zero articles required archiving (older than {days} days).")

        return count
