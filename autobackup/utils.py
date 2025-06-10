import os

import static
from loguru import logger

from static import backup_job_list

def add_task(task_list, t, local_dir, settings_alist):
        '添加任务'
        task_dict = {
            'time': t,
            'local_dir': local_dir,
            'settings_alist': settings_alist,
            'status': 'waiting',
        }

        # 查重
        if task_dict not in task_list:
            logger.info(f"Auto backuping task created on {t}, {local_dir} -> {settings_alist['remote_dir']}")
            task_list.append(task_dict)

async def upload(task_dict):
    '执行上传'
    # 分离参数
    local_dir = task_dict['local_dir']
    settings_temp = task_dict['settings_alist']
    dest_dir = get_dest_dir(local_dir, settings_temp['remote_dir'])
    
    # 获取文件名，去除文件夹
    filenames = os.listdir(local_dir)
    for idx, filename in enumerate(filenames):
        if os.path.isdir(os.path.join(local_dir, filename)):
            del filenames[idx]
    
    # 获取token
    token = await static.session.get_alist_token(settings_temp)

    # 上传文件
    for filename in filenames:
        local_filename = os.path.join(local_dir, filename)
        dest_filename = os.path.join(dest_dir, filename)
        await static.session.upload_alist(settings_temp, token, local_filename, dest_filename)


def del_task(id:int, del_all=False):
    '删除任务'
    if del_all:
        backup_job_list = []
    elif 0 <= id < len(backup_job_list):
        del backup_job_list[id]
    return show_status()

def change_status(id:int, status:str):
    '改变任务状态'
    backup_job_list[id]['status'] = status
    return show_status()
    
def show_status():
    '获取备份情况'
    res_str = ''
    for idx, i in enumerate(backup_job_list):
        config_temp = i['settings_alist']
        res_str += "ID: {} \tStatus: {} \tScheduled Time: {} \tLocal dir:{} \tRemote dir:{} \n".format(
            idx,
            i['status'],
            i['time'].strftime(r"%y/%m/%dT%H:%M:%S"),
            i['local_dir'],
            f"{config_temp['url_alist']}{config_temp['remote_dir']}"
        )
    return res_str

### Utils
def get_dest_dir(local_dir: str, remote_dir: str):
    '自动拼接本地文件夹和设置里的远程文件夹名，获取远程文件夹名称'
    last_dir = os.path.split(local_dir)[1]
    if not last_dir:
        # 路径以/结尾时
        last_dir = os.path.split(os.path.split(local_dir)[0])[1]
    dest_dir = os.path.join(remote_dir, last_dir)

    return dest_dir

