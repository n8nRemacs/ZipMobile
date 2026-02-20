"""
APScheduler — daily proxy pool refresh.
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# Will be set from main.py after pool is created
_pool = None


def init_scheduler(pool):
    global _pool
    _pool = pool

    scheduler.add_job(
        daily_refresh,
        CronTrigger(hour=settings.daily_refresh_hour, minute=settings.daily_refresh_minute),
        id="daily_refresh",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"Scheduler started: daily refresh at "
        f"{settings.daily_refresh_hour:02d}:{settings.daily_refresh_minute:02d}"
    )


async def daily_refresh():
    if _pool is None:
        logger.error("Pool not initialized, skipping refresh")
        return
    logger.info("Scheduled daily refresh starting...")
    try:
        result = await _pool.refresh()
        logger.info(f"Daily refresh result: {result}")
    except Exception as e:
        logger.error(f"Daily refresh failed: {e}")


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
