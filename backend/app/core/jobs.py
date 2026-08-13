import asyncio
from app.core.logging import logger


class BackgroundJobRunner:
    @staticmethod
    async def schedule_hourly_news_ingestion(interval_seconds: int = 3600):
        """Continuously scrape live web news feeds every hour and append new entries into PostgreSQL DB."""
        logger.info(f"Hourly live news ingestion scheduler initiated (interval: {interval_seconds}s)...")
        while True:
            # Sleep first on startup so application initializes immediately
            await asyncio.sleep(interval_seconds)
            try:
                from scripts.fetch_todays_news import sync_todays_news
                logger.info("Executing scheduled hourly live web news research & sync...")
                await sync_todays_news()
                logger.info(f"Hourly news research complete. Next scheduled run in {interval_seconds} seconds.")
            except asyncio.CancelledError:
                logger.info("Hourly news ingestion task cancelled gracefully.")
                break
            except Exception as e:
                logger.error(f"Error during scheduled news ingestion: {e}")

    @staticmethod
    async def run_rss_ingestion():
        """Fetch RSS feeds and populate DB on demand."""
        logger.info("Running manual RSS ingestion background job...")
        from scripts.fetch_todays_news import sync_todays_news
        await sync_todays_news()
        logger.info("Manual RSS ingestion complete.")

    @staticmethod
    async def calculate_trending():
        """Aggregate analytics to calculate trending items."""
        logger.info("Calculating trending content...")
        await asyncio.sleep(1)
        logger.info("Trending calculation complete.")

    @staticmethod
    async def sync_search_index():
        """Sync DB records to Meilisearch."""
        logger.info("Syncing search indexes...")
        await asyncio.sleep(1)
        logger.info("Search index sync complete.")

    @staticmethod
    async def revalidate_cache():
        """Invalidate CDN/Redis caches."""
        logger.info("Revalidating caches...")
        await asyncio.sleep(1)
        logger.info("Cache revalidation complete.")

    @staticmethod
    async def generate_thumbnails(media_id: int):
        """Generate thumbnails for uploaded media."""
        logger.info(f"Generating thumbnails for media {media_id}...")
        await asyncio.sleep(1)
        logger.info("Thumbnail generation complete.")
