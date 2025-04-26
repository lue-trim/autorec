import os, time, requests, re, json, traceback, datetime
import asyncio
# import http.cookiejar, requests.utils
import urllib3

from aiohttp import ClientSession, ClientError
from typing import Any, TypeVar, Coroutine, Union
from asyncio.futures import Future as AsyncioFuture
from concurrent.futures import Future as ConcurrentFuture
T = TypeVar("T")

from urllib.parse import unquote, quote
from static import config, session, logger
import static

class AutoBackuper():
    '自动备份工具'
    running: bool = True
    task_list: list = []

    def init(self) -> None:
        self.task_list = []
        self.running = True

    def add_task(self, t, local_dir, settings_alist):
        '添加任务'
        task_dict = {
            'time': t,
            'local_dir': local_dir,
            'settings_alist': settings_alist,
            'status': 'waiting',
        }

        # 查重
        if task_dict not in self.task_list:
            print(f"Auto backuping task created on {t}, {local_dir} -> {settings_alist['remote_dir']}")
            self.task_list.append(task_dict)

    def del_task(self, id:int, del_all=False):
        '删除任务'
        if del_all:
            self.task_list = []
        elif 0 <= id < len(self.task_list):
            del self.task_list[id]
        return self.show_status()

    def change_status(self, id:int, status:str):
        '改变任务状态'
        self.task_list[id]['status'] = status
        return self.show_status()

    async def __upload_action(self, task_dict):
        '执行上传'
        # 分离参数
        local_dir = task_dict['local_dir']
        settings_temp = task_dict['settings_alist']
        dest_dir = utils.get_dest_dir(local_dir, settings_temp['remote_dir'])
        
        # 获取文件名，去除文件夹
        filenames = os.listdir(local_dir)
        for idx, filename in enumerate(filenames):
            if os.path.isdir(os.path.join(local_dir, filename)):
                del filenames[idx]
        
        # 获取token
        token = await session.get_alist_token(settings_temp)

        # 上传文件
        loop = asyncio.get_event_loop()
        tasks = []
        for filename in filenames:
            local_filename = os.path.join(local_dir, filename)
            dest_filename = os.path.join(dest_dir, filename)
            tasks.append(session.upload_alist(settings_temp, token, local_filename, dest_filename))
        wait_coro = asyncio.wait(tasks)
        loop.run_until_complete(wait_coro)
        loop.close()
    
    def __check_time(self, interval):
        '循环检查时间'
        while self.running:
            for task_id, task_dict in enumerate(self.task_list):
                if datetime.datetime.now() >= task_dict['time'] and task_dict['status'] == 'waiting':
                    # 发现到点了并且待上传
                    logger.debug(f"Auto backuping...\n{task_dict}")
                    self.change_status(task_id, 'uploading')
                    # 上传
                    try:
                        utils.run_async(self.__upload_action(task_dict))
                    except Exception as e:
                        logger.error(traceback.format_exc())
                        self.change_status(task_id, 'failed')
                    else:
                        # 标记为已完成
                        self.change_status(task_id, 'completed')
                    break
            # 接着睡
            time.sleep(interval)
    
    def start_check(self, settings_autobackup:dict):
        '启动循环检查'
        import threading
        interval = settings_autobackup['timer_interval']
        t = threading.Thread(target=self.__check_time, args=[interval])
        t.start()
        return t
    
    def show_status(self):
        '获取备份情况'
        res_str = ''
        for idx, i in enumerate(self.task_list):
            config_temp = i['settings_alist']
            res_str += "ID: {} \tStatus: {} \tScheduled Time: {} \tLocal dir:{} \tRemote dir:{} \n".format(
                idx,
                i['status'],
                i['time'].strftime(r"%y/%m/%dT%H:%M:%S"),
                i['local_dir'],
                f"{config_temp['url_alist']}{config_temp['remote_dir']}"
            )
        return res_str

# classes
class File:
    '表单上传用文件类'
    # 注：with open()语句一定要写在class外面，否则对文件操作符开关过于频繁容易导致报错
    def __init__(self, fp, filename):
        self.filename = filename
        self.fp = fp
        self.total_size = os.path.getsize(self.filename)
        self.current_size = 0
        self.last_time = datetime.datetime.now()

    def get_size(self):
        '获取文件大小'
        return self.total_size

    def read(self, size=-1):
        'read方法，给http模块调用，让其对文件自动分片'
        #with open(self.filename, 'rb') as file:
        #chunk_size = 10000
        #if self.get_size() <= chunk_size:
            # 小文件直接上传
            #return self.fp.read(self.get_size())
        #else:
            # 大文件分片上传

        # 识别chunk size
        if size == -1:
            self.current_size = self.total_size
        elif size >= self.total_size:
            self.current_size += self.total_size - self.current_size
        else:
            self.current_size += size

        # # 计算上传时间
        # new_time = datetime.datetime.now()
        # delta_time = new_time - self.last_time
        # secs = delta_time.total_seconds()
        # if secs <= 0:
        #     secs = 1.0
        # self.last_time = new_time

        # # 输出进度并返回
        # print("Read: {:.2f}%".format(
        #     self.current_size / self.total_size * 100,
        #     #self.current_size / secs / 1024
        # ),
        # end='          \r')
        return self.fp.read(size)

    def __len__(self):
        '获取文件大小，给http模块调用'
        return self.get_size()

class AutoRecSession():
    '本地http通信专用类'
    max_retries = 6

    def __init__(self, max_retries:int=6):
        self.max_retries = max_retries

    @classmethod
    async def request(self, req_type, **kwargs):
        '请求'
        success = False
        for i in range(self.max_retries):
            try:
                logger.debug(f"Trying request {kwargs['url']} ({i+1}/{self.max_retries})")
                async with ClientSession() as session:
                    if req_type == "post":
                        async with session.post(**kwargs) as res:
                            return await res.json()
                    elif req_type == "put":
                        async with session.put(**kwargs) as res:
                            return await res.json()
                    elif req_type == "patch":
                        async with session.patch(**kwargs) as res:
                            return await res.json()
                    else:
                        async with session.get(**kwargs) as res:
                            return await res.json()
            except ClientError as e:
                logger.error(f"Request Error: {e}")
                await asyncio.sleep(2**i)
            except Exception:
                logger.error(f"Unknown Error: {traceback.format_exc()}")
            else:
                success = True
            if success:
                break

    @classmethod
    async def get(self, **kwargs):
        'GET'
        await self.request(req_type="get", **kwargs)

    @classmethod
    async def post(self, **kwargs):
        'POST'
        await self.request(req_type="post", **kwargs)

    @classmethod
    async def put(self, **kwargs):
        'PUT'
        await self.request(req_type="put", **kwargs)

    @classmethod
    async def patch(self, **kwargs):
        'PATCH'
        await self.request(req_type="patch", **kwargs)

    async def get_alist_token(self, settings_alist:dict):
        '获取alist管理token'
        url = f"{settings_alist['url']}/api/auth/login/hash"
        params = {
            "username": settings_alist['username'],
            "password": settings_alist['password'].lower()
        }
        headers = {
            'Content-Type': 'application/json'
        }

        # 请求API
        response_json = await self.get(url=url, data=json.dumps(params), headers=headers)
        # 获取结果
        if response_json['code'] == 200:
            return response_json['data']['token']
        else:
            return ""
    
    async def copy_alist(self, settings_alist:dict, token:str, source_dir:str, filenames:list, dist_dir:str):
        '复制文件'
        # 请求参数
        url = f"{settings_alist['url']}/api/fs/copy"
        headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }
        data = {
            "src_dir": source_dir,
            "dst_dir": dist_dir,
            "names": filenames
        }

        # 请求API
        response = await self.post(url=url, data=utils.dict2str(data), headers=headers)
        data = response.json()

        # 获取结果
        if data['code'] == 200:
            logger.info("Copy success.")
        else:
            logger.error("Copy failed,", data['message'])
        
        return data['code']
    
    async def rm_alist(self, settings_alist:dict, token:str, dirname:str, filenames:list):
        '删除文件'
        # 请求参数
        url = f"{settings_alist['url']}/api/fs/remove"
        headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }
        data = {
            "dir": dirname,
            "names": filenames
        }

        # 请求API
        response = await self.post(url=url, data=utils.dict2str(data), headers=headers)
        data = response.json()

        # 获取结果
        if data['code'] == 200:
            logger.info("Remove success:", dirname, filenames)
        else:
            logger.error("Remove failed:", dirname, filenames, data['message'])
        
        return data['code']

    async def upload_alist_action(self, settings_alist:dict, token:str, local_filename:str, dest_filename:str):
        '供multiprocessing使用的流式上传文件'
        for i in range(6):
            try:
                await self.upload_alist(settings_alist, token, local_filename, dest_filename)
            except Exception:
                logger.error(traceback.format_exc())
                time.sleep(4**i)
        else:
            from requests.exceptions import RequestException
            raise RequestException()

    async def upload_alist(self, settings_alist:dict, token:str, filename:str, dest_filename:str):
        '流式上传文件'
        dest_filename = quote(dest_filename) # URL编码

        # 请求参数
        url = f"{settings_alist['url']}/api/fs/put"
        headers = {
            "Authorization": token,
            "File-Path": dest_filename,
            "As-Task": "True",
            "Content-Type": "application/octet-stream",
        }

        # 打开文件
        with open(filename, 'rb') as f:
            data = File(f, filename)
            # 请求API
            response_json = await self.put(url=url, data=data, headers=headers)
        
        if response_json['code'] == 200:
            logger.info(f"Upload success: {filename}")
            # 是否在上传后删除文件
            if settings_alist['remove_after_upload']:
                os.remove(filename)
        else:
            logger.error("{} Upload failed: {}".format(filename, response_json))

    async def set_blrec(self, data: dict):
        '更改blrec设置'
        url = f"{config.blrec['url_blrec']}/api/v1/settings"
        body = utils.dict2str(data)

        # 请求API
        await self.patch(url=url, data=body, timeout=20)
    
    async def get_blrec_data(self, room_id=-1, page=1, size=100, select="all"):
        '获取blrec信息'
        params = {
            "select": select,
            "size": size,
            "page": page,
            }
        if room_id != -1:
            url = f"{config.blrec['url']}/api/v1/tasks/{room_id}/data"
        else:
            url = f"{config.blrec['url']}/api/v1/tasks/data"
        response_json = await self.get(url=url, params=params)

        return response_json

## 奇奇怪怪的功能
class utils:
    def run_async(coro: Union[Coroutine[Any, Any, T], AsyncioFuture, ConcurrentFuture]):
        '同步执行异步代码'
        loop = asyncio.get_event_loop()
        task = loop.create_task(coro)
        # task.add_done_callback(lambda x: x.result())
        loop.run_until_complete(task)
        loop.close()
        return task.result()

    def get_dest_dir(local_dir: str, remote_dir: str):
        '自动拼接本地文件夹和设置里的远程文件夹名，获取远程文件夹名称'
        last_dir = os.path.split(local_dir)[1]
        if not last_dir:
            # 路径以/结尾时
            last_dir = os.path.split(os.path.split(local_dir)[0])[1]
        dest_dir = os.path.join(remote_dir, last_dir)

        return dest_dir

    def dict2str(data: dict):
        '将dict转换为符合http要求的字符串'
        #s = str(data)
        #return s.replace('\'', '\"') 
        return json.dumps(data)# 之前写的什么破玩意
    
    def parse_macro(s: str, data: dict):
        '将配置文件含宏部分解析成对应字符串'
        from functools import reduce
        parsed_s = s
        # 匹配
        re_res = re.findall(r'{[^}]*/[^}]*}', s)
        if not re_res:
            return parsed_s
        
        #print(re_res.groups())
        # 解析
        for match_res in re_res:
            split_list = match_res[1:-1].split('/')
            #print(split_list)
            
            if split_list[0] == 'time':
                # 时间解析
                time_now = datetime.datetime.now()
                replaced_s = time_now.strftime(split_list[1])
            else:
                # 字典解析
                replaced_s = str(reduce(lambda x,y:x[y], split_list, data))
            
            # 替换
            parsed_s = re.sub(match_res, replaced_s, parsed_s)
        
        return parsed_s

# functions
## 刷新cookies
async def refresh_cookies():
    '刷新cookies'
    import account
    await account.refresh_cookies(True)

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
            dist_dir = utils.parse_macro(settings_alist['remote_dir'], rec_info)
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


def add_autobackup(autobackuper:AutoBackuper, settings_autobackup:dict, local_dir:str, now=False):
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
            autobackuper.add_task(
                t = t, 
                local_dir = local_dir, 
                settings_alist = settings_alist
                )
        except Exception as e:
            logger.log(e)

# 初始化
static.autobackuper = AutoBackuper()
static.autobackuper.start_check(config.autobackup)

static.session = AutoRecSession(max_retries=config.app['max_retries'])
logger.debug("Initialized server config.")

