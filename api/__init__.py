import asyncio, traceback, datetime, os

from loguru import logger

from static import config, session

from .utils import parse_macro
from autobackup.utils import add_task


async def upload_video(video_filename: str, settings_alist=None, rec_info=None):
    '上传视频'
    # 判断一下有没有开启自动上传功能
    if not settings_alist['enabled']:
        return

    # 文件名处理
    appendices = ['flv', 'jsonl', 'xml', 'jpg', 'mp4'] # 可能存在的后缀名
    filenames = []
    for appendix in appendices:
        # 本地文件名
        local_filename = "{}.{}".format(os.path.splitext(video_filename)[0], appendix)
        if not os.path.exists(local_filename):
            continue

        # 远程文件名
        if rec_info:
            dist_dir = parse_macro(settings_alist['remote_dir'], rec_info)
            dest_filename = os.path.join(dist_dir, os.path.split(local_filename)[1])
        else:
            dest_filename = settings_alist['remote_dir']

        # [本地文件名, 远程文件名]
        filenames.append([local_filename, dest_filename])
    
    # 获取token
    token = await session.get_alist_token(settings_alist)

    # 上传文件
    loop = asyncio.get_event_loop()
    tasks = []
    for i in filenames:
        local_filename = i[0]
        dest_filename = i[1]
        tasks.append(session.upload_alist(settings_alist, token, local_filename, dest_filename))
    wait_coro = asyncio.wait(tasks)
    loop.run_until_complete(wait_coro)
    loop.close()


def add_autobackup(settings_autobackup:dict, local_dir:str, now=False):
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
                t = t, 
                local_dir = local_dir, 
                settings_alist = settings_alist
                )
        except Exception as e:
            logger.log(e)
