import json, os, uvicorn, traceback

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from uuid import UUID

from contextlib import asynccontextmanager

import alist
import blrec
import db

from static import config, logger, Config, App

import cookies_checker
from cookies_checker.utils import refresh_cookies

import autobackup
from autobackup.utils import show_status, change_status, del_task, dump_task, load_task, retry_task


class BlrecWebhookData(BaseModel):
    'BLREC Webhook的数据格式'
    id: UUID
    date: str
    type: str
    data: dict


@asynccontextmanager
async def lifespan(_app):
    '生命周期管理'
    # config.load()
    await db.init_db()
    cookies_scheduler = await cookies_checker.init()
    autobackup_scheduler = await autobackup.init()

    yield

    cookies_scheduler.shutdown()
    autobackup_scheduler.shutdown()
    await db.close()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


### 设置
@app.get('/version')
async def get_version(package:str=""):
    '获取任务包版本'
    try:
        ver_dict = App.get_version(package)
        return {
            "code": 200,
            "data": ver_dict
        }
    except Exception:
        return {
            'code': 422,
            'data': traceback.format_exc()
        }

@app.post('/settings/reload')
async def reload_settings(filename:str="settings.toml"):
    '重新加载设置'
    config.load(config_path=filename)
    return  {
        "code": 200,
        "data": None
        }


### 自动备份
@app.get('/autobackup')
async def get_backup_status():
    '获取自动备份工作状态'
    data = await show_status()
    return  {
        "code": 200,
        "data": data
        }

@app.post('/autobackup')
async def add_backup_task(local_dir:str, config_toml:str, now:bool=False):
    '添加备份任务'
    # 获取数据
    settings_temp = Config(config_path=config_toml)
    # 添加
    await autobackup.add_autobackup(
        # task_list=backup_job_list,
        settings_autobackup=settings_temp.autobackup, 
        local_dir=local_dir,
        now=now
        )
    # 回复
    data = await show_status()
    return  {
        "code": 200,
        "data": data
        }

@app.post('/autobackup/dump')
async def dump_backup_task(filename:str="task_backup.json"):
    '导出备份任务到文件'
    await dump_task(filename)
    # 回复
    data = await show_status()
    return  {
        "code": 200,
        "data": data
        }

@app.post('/autobackup/load')
async def load_backup_task(filename:str="task_backup.json"):
    '从文件中加载任务信息'
    await load_task(filename)
    # 回复
    data = await show_status()
    return  {
        "code": 200,
        "data": data
        }

@app.delete('/autobackup')
async def del_backup_task(id:int, all:bool=False):
    '删除备份任务'
    data = await del_task(int(id), all)
    return  {
        "code": 200,
        "data": data
        }

@app.post('/autobackup/retry')
async def retry_backup_task(id:int=-1, all:bool=False):
    '重试备份任务'
    status = await retry_task(id=id, retry_all=all)
    return  {
        "code": 200,
        "data": status
        }


### 手动上传接口
# @app.post('/upload')
# async def manual_upload(path: str):
#     '手动上传到指定位置'


### BLREC Webhook
@app.post('/blrec')
async def blrec_webhook(data: BlrecWebhookData|str):
    '接收webhook信息'
    if type(data) is str:
        json_obj = json.loads(data)
    elif type(data) is BlrecWebhookData:
        json_obj = data.dict()
    else:
        raise
    event_type = json_obj['type']
    # 根据接收到的blrec webhook参数执行相应操作
    # 更新：不用套try语句，要是出错http模块会自己处理
    if event_type == 'RecordingFinishedEvent':
        # 录制完成，如果没有其他在录制的任务的话就更新一下cookies
        if not await blrec.get_blrec_data(select='recording'):
            await refresh_cookies(silent=True)
    elif event_type == 'VideoPostprocessingCompletedEvent':
        # 视频后处理完成，上传+自动备份
        # 获取直播间信息
        room_id = json_obj['data']['room_id']
        room_info = await blrec.get_blrec_data(room_id)
        # 上传
        filename = json_obj['data']['path']
        try:
            await alist.upload_video(filename, rec_info=room_info, settings_alist=config.alist)
        except Exception as e:
            logger.error(e)
        # 自动备份
        local_dir = os.path.split(filename)[0]
        await autobackup.add_autobackup(
            # task_list = backup_job_list,
            settings_autobackup = config.autobackup, 
            local_dir = local_dir)
    else:
        logger.info("Got unknown Event: ", event_type)
    # 回复
    return  {
        "code": 200,
        "message": "Mua!"
        }


if __name__ == "__main__":
    # static.init()
    logger.info("Autorec service started.")
    uvicorn.run(
        app=app, 
        host=config.app['host_server'], 
        port=config.app['port_server']
        )
