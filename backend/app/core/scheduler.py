import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.logging import logger
from app.modules.news.pipeline import run_sync_pipeline
from app.modules.news.archiver import archive_old_news
from app.modules.magazine.archiver import rotate_magazine_featured

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


async def daily_morning_sync_and_archive():
    """
    Scheduled job running every morning at 6:00 AM IST.
    1. Executes full news ingestion catch-up.
    2. Runs 90-day archiving job to mark old news articles as is_archived = True.
    3. Runs 90-day magazine rotation to set is_featured = False on old magazines.
    """
    logger.info("[SCHEDULER] Triggering Daily Morning 6:00 AM IST Full Refresh & Archiving...")
    try:
        await run_sync_pipeline(is_full_sync=True)
        archived_count = await archive_old_news()
        rotated_count = await rotate_magazine_featured()
        logger.info(
            f"[SCHEDULER] Daily Morning 6:00 AM IST Job complete. "
            f"Archived {archived_count} news articles. "
            f"Rotated {rotated_count} magazines out of featured."
        )
    except Exception as e:
        logger.error(f"[SCHEDULER] Error during Daily Morning Refresh: {e}")


async def periodic_30min_incremental_sync():
    """
    Scheduled job running every 30 minutes in Asia/Kolkata timezone.
    Performs quick incremental RSS feed ingestion.
    """
    logger.info("[SCHEDULER] Triggering 30-minute incremental news ingestion...")
    try:
        await run_sync_pipeline(is_full_sync=False)
    except Exception as e:
        logger.error(f"[SCHEDULER] Error during 30-minute incremental sync: {e}")


def start_scheduler():
    """
    Registers and starts all scheduled background jobs on application startup.
    Uses explicit 'Asia/Kolkata' timezone for all triggers.
    """
    if scheduler.running:
        logger.info("[SCHEDULER] Scheduler is already running.")
        return

    # Job 1: Daily Morning Full Refresh, News Archiving & Magazine Rotation at 6:00 AM IST
    scheduler.add_job(
        daily_morning_sync_and_archive,
        trigger=CronTrigger(hour=6, minute=0, timezone="Asia/Kolkata"),
        id="daily_morning_6am_refresh",
        name="6:00 AM IST Full Sync, Archiving & Magazine Rotation",
        replace_existing=True,
    )

    # Job 2: 30-Minute Incremental Feed Ingestion
    scheduler.add_job(
        periodic_30min_incremental_sync,
        trigger=IntervalTrigger(minutes=30, timezone="Asia/Kolkata"),
        id="incremental_30min_refresh",
        name="30-Minute Incremental News Sync",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("[SCHEDULER] APScheduler started successfully in Asia/Kolkata timezone.")
    logger.info("[SCHEDULER] Job Registered: '6:00 AM IST Full Sync, Archiving & Magazine Rotation' (Cron: 06:00 IST)")
    logger.info("[SCHEDULER] Job Registered: '30-Minute Incremental News Sync' (Interval: 30 min)")


def shutdown_scheduler():
    """
    Gracefully shuts down the background scheduler during app shutdown.
    """
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[SCHEDULER] APScheduler shut down gracefully.")

