"""
Magazine 90-Day Featured Priority Rotation

Mirrors the news archiver exactly:
  - Articles > 90 days old: is_archived = True
  - Magazines > 90 days old: is_featured = False

ZERO rows are ever deleted. The magazine only moves from the
priority/featured section to the Magazine Archive listing.
The archive always retains a minimum of 12 months of content.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.logging import logger
from app.modules.magazine.models import Magazine


MAGAZINE_FEATURED_DAYS = 90      # after this many days, magazine rolls off featured
MAGAZINE_ARCHIVE_MIN_MONTHS = 12  # archive must always show at least 12 months


async def rotate_magazine_featured(days: int = MAGAZINE_FEATURED_DAYS) -> int:
    """
    Finds all published magazines where published_at is older than `days`
    and is_featured is still True, then sets is_featured = False.

    CRITICAL: NO ROWS ARE DELETED FROM THE DATABASE.
    Returns count of magazines that were de-featured.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with async_session_maker() as session:
        stmt = (
            select(Magazine)
            .where(Magazine.status == "published")
            .where(Magazine.is_featured == True)
            .where(Magazine.published_at < cutoff)
        )
        result = await session.execute(stmt)
        magazines_to_rotate = result.scalars().all()

        count = len(magazines_to_rotate)
        now_ts = datetime.now(timezone.utc)

        if count > 0:
            for mag in magazines_to_rotate:
                mag.is_featured = False

            await session.commit()
            logger.info(
                f"[MAGAZINE ARCHIVER] Rotated {count} magazines out of featured section "
                f"(older than {days} days, cutoff: {cutoff.isoformat()}). NO ROWS DELETED."
            )
        else:
            logger.info(
                f"[MAGAZINE ARCHIVER] Checked featured magazines — zero required rotation "
                f"(older than {days} days)."
            )

        return count
