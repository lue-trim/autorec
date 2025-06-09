import json, os, uvicorn

from loguru import logger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from uuid import UUID

from contextlib import asynccontextmanager

from autorec import add_autobackup, upload_video, refresh_cookies
# autorec模块的导入必须放前面
import static
from static import config, autobackuper, session, Config

import cookies_checker

class BlrecWebhookData(BaseModel):
    'BLREC Webhook的数据格式'
    id: UUID
    date: str
    type: str
    data: dict


@asynccontextmanager
async def lifespan(_app):
    '生命周期管理'
    config.load()
    cookies_scheduler = await cookies_checker.init()

    yield

    cookies_scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


### 设置
@app.post('/settings/reload')
async def reload_settings(filename:str="settings.toml"):
    '重新加载设置'
    config.load(config_path=filename)


### 自动备份
@app.get('/autobackup')
async def get_backup_status():
    '获取自动备份工作状态'
    data = autobackuper.show_status()
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
    add_autobackup(
        autobackuper=autobackuper, 
        settings_autobackup=settings_temp.autobackup, 
        local_dir=local_dir,
        now=now
        )
    # 回复
    data = autobackuper.show_status()
    return  {
        "code": 200,
        "data": data
        }

@app.delete('/autobackup')
async def del_backup_task(id:int, all:bool=False):
    '删除备份任务'
    data = autobackuper.del_task(int(id), all)
    return  {
        "code": 200,
        "data": data
        }

@app.post('/autobackup/retry')
async def retry_backup_task(id:int=-1, all:bool=False):
    '重试备份任务'
    if all:
        for idx, task in enumerate(autobackuper.task_list):
            if task['status'] == "failed":
                autobackuper.change_status(idx, "waiting")
        status = autobackuper.show_status()
    else:
        status = autobackuper.change_status(id, "waiting")
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
    else:
        json_obj = data.dict()
    event_type = json_obj['type']
    # 根据接收到的blrec webhook参数执行相应操作
    # 更新：不用套try语句，要是出错http模块会自己处理
    if event_type == 'RecordingFinishedEvent':
        # 录制完成，如果没有其他在录制的任务的话就更新一下cookies
        if not session.get_blrec_data(select='recording'):
            await refresh_cookies()
    elif event_type == 'VideoPostprocessingCompletedEvent':
        # 视频后处理完成，上传+自动备份
        # 获取直播间信息
        room_id = json_obj['data']['room_id']
        room_info = session.get_blrec_data(room_id)
        # 上传
        filename = json_obj['data']['path']
        try:
            await upload_video(filename, rec_info=room_info, settings_alist=config.alist)
        except Exception as e:
            logger.error(e)
        # 自动备份
        local_dir = os.path.split(filename)[0]
        add_autobackup(autobackuper=autobackuper, settings_autobackup=config.autobackup, local_dir=local_dir)
    else:
        logger.info("Got unknown Event: ", event_type)
    # 回复
    return  {
        "code": 200,
        "message": "Mua!"
        }


if __name__ == "__main__":
    # static.init()
    autobackuper.start_check(config.autobackup)
    logger.info("Autorec service started.")
    uvicorn.run(
        app=app, 
        host=config.app['host_server'], 
        port=config.app['port_server']
        )
    autobackuper.running = False
