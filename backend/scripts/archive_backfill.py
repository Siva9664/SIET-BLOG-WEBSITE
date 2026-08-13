import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.modules.news.archiver import archive_old_news
from app.core.config import settings


async def main():
    print(f"Running One-Off Archive Backfill (NEWS_ARCHIVE_AFTER_DAYS = {settings.NEWS_ARCHIVE_AFTER_DAYS})...")
    count = await archive_old_news(days=settings.NEWS_ARCHIVE_AFTER_DAYS)
    print(f"Archive Backfill Complete. Total articles marked is_archived = True: {count}")
    print("NO ROWS WERE DELETED FROM POSTGRESQL.")


if __name__ == "__main__":
    asyncio.run(main())
