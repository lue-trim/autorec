import traceback, datetime, asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from static import config, backup_job_list

from .utils import change_status, upload, add_task


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

def add_autobackup(task_list:list, settings_autobackup:dict, local_dir:str, now=False):
    '自动备份功能'
    for settings_alist in settings_autobackup['servers']:
        # 判断一下开没开
        if not settings_alist['enabled']:
            continue

        try:
            # 读取时间
            scheduled_time = settings_alist['time']
            datetime_now = datetime.datetime.now()
            time_today = datetime_now.strftime(r'%H:%M:%S')

            # 如果立即上传的话
            if now:
                scheduled_time = time_today

            # 决定启动时间
            if time_today <= scheduled_time:
                # 如果时间没过预定的点，那就放今天
                scheduled_date = datetime_now.strftime(r'%y/%m/%d')
            else:
                # 如果时间已经过了，挪到第二天
                scheduled_date = (datetime_now + datetime.timedelta(days=1)).strftime(r'%y/%m/%d')
            formatted_time = f"{scheduled_date}T{scheduled_time}"
            t = datetime.datetime.strptime(formatted_time, r"%y/%m/%dT%H:%M:%S")

            # 添加任务
            add_task(
                task_list = task_list,
                t = t, 
                local_dir = local_dir, 
                settings_alist = settings_alist
                )
        except Exception as e:
            logger.error(e)
