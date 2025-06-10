from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from static import config

from .utils import refresh_cookies, get_blrec_data

# from .utils import add_subtitles_all

async def init():
    '初始化'
    interval = config.cookies['check_interval']
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_refresh, trigger="interval", seconds=interval)
    scheduler.start()
    logger.debug(f"Cookies scheduler started (Interval: {interval}s)")
    return scheduler

async def scheduled_refresh():
    '定时操作'
    if await get_blrec_data(room_id=-1, select="recording"):
        logger.info("Trying to check cookies but still recording, skipping...")
    else:
        logger.debug("Start checking cookies...")
        await refresh_cookies(silent=True)
