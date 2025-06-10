import traceback, datetime, asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from static import config, backup_job_list

from .utils import change_status, upload


async def init():
    '初始化'
    interval = config.autobackup['check_interval']
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_check, trigger="interval", seconds=interval)
    scheduler.start()
    logger.debug(f"Autobackup scheduler started (Interval: {interval}s)")
    return scheduler

async def scheduled_check():
    '定时检查是不是该备份了'
    logger.debug("Start checking autobackups...")
    for task_id, task_dict in enumerate(backup_job_list):
        if datetime.datetime.now() >= task_dict['time'] and task_dict['status'] == 'waiting':
            # 发现到点了并且待上传
            logger.info(f"Auto backuping...")
            logger.debug(f"{task_dict}")
            change_status(task_id, 'uploading')
            # 上传
            try:
                await upload(task_dict)
            except Exception as e:
                logger.error(traceback.format_exc())
                change_status(task_id, 'failed')
            else:
                # 标记为已完成
                change_status(task_id, 'completed')
            # break
