import sys, toml, asyncio, traceback, json, os
# from requests.adapters import HTTPAdapter
from loguru import logger

from aiohttp import ClientSession, ClientError, ClientTimeout
from urllib.parse import quote

class AutoRecSession():
    '本地http通信专用类'
    max_retries = 6

    def __init__(self, max_retries:int=6):
        self.max_retries = max_retries

    async def __request(self, **kwargs):
        async with ClientSession(timeout=ClientTimeout(total=None)) as session:
            async with session.request(**kwargs) as res:
                response = await res.json()
                assert res.ok
                return response

    async def request(self, filename="", **kwargs):
        '发送请求'
        for i in range(self.max_retries):
            sleep_sec = min(4**(i-1), 600)
            logger.info(f"({i+1}/{self.max_retries}) Requesting after {sleep_sec} seconds: {kwargs['url']}")
            await asyncio.sleep(sleep_sec)
            try:
                if filename:
                    if os.path.getsize(filename) == 0:
                        logger.warning(f"Skipping empty file {filename}..")
                        return {'code': 200, 'data': None}
                    else:
                        logger.info(f"Loading file {filename}")
                        with open(filename, "rb") as f:
                            response = await self.__request(data=f, **kwargs)
                else:
                    response = await self.__request(**kwargs)
            except AssertionError:
                logger.warning(f"Response Error: {response}, retrying...")
            except ClientError as e:
                logger.warning(f"Request Error, retrying: {e}")
            except TimeoutError:
                logger.warning("Request time out, retrying...")
            except Exception:
                logger.warning(f"Unknown Error, retrying: {traceback.format_exc()}")
            else:
                # return json.loads(response)
                # logger.debug(response)
                if response.get("code", 200) == 200:
                    return response
                else:
                    logger.warning(f"Response Error, retrying: {response}")
        else:
            logger.error("All requests failed.")
            return {'code': 500, 'data': None}

    async def get_alist_token(self, settings_alist:dict):
        '获取alist管理token'
        url = f"{settings_alist['url_alist']}/api/auth/login/hash"
        params = {
            "username": settings_alist['username'],
            "password": settings_alist['password'].lower()
        }
        headers = {
            'Content-Type': 'application/json'
        }

        # 请求API
        response_json = await self.request(
            method="post",
            url=url, 
            data=json.dumps(params), 
            headers=headers
            )
        # 获取结果
        if response_json['code'] == 200:
            return response_json['data']['token']
        else:
            return ""
    
    async def copy_alist(self, settings_alist:dict, token:str, source_dir:str, filenames:list, dist_dir:str):
        '复制文件'
        # 请求参数
        url = f"{settings_alist['url_alist']}/api/fs/copy"
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
        data = await self.request(
            method="post",
            url=url, 
            data=json.dumps(data), 
            headers=headers
            )

        # 获取结果
        if data['code'] == 200:
            logger.info("Copy success.")
        else:
            logger.error("Copy failed,", data['message'])
        
        return data['code']
    
    async def rm_alist(self, settings_alist:dict, token:str, dirname:str, filenames:list):
        '删除文件'
        # 请求参数
        url = f"{settings_alist['url_alist']}/api/fs/remove"
        headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }
        data = {
            "dir": dirname,
            "names": filenames
        }

        # 请求API
        data = await self.request(
            method="post",
            url=url, 
            data=json.dumps(data), 
            headers=headers
            )

        # 获取结果
        if data['code'] == 200:
            logger.info("Remove success:", dirname, filenames)
        else:
            logger.error("Remove failed:", dirname, filenames, data['message'])
        
        return data['code']

    async def upload_alist(self, settings_alist:dict, token:str, filename:str, dest_filename:str):
        '流式上传文件'
        dest_filename = quote(dest_filename) # URL编码

        # 请求参数
        url = f"{settings_alist['url_alist']}/api/fs/put"
        headers = {
            "Authorization": token,
            "File-Path": dest_filename,
            "As-Task": "True",
            "Content-Type": "application/octet-stream",
        }

        # 打开文件
        response_json = await self.request(
            filename=filename, 
            method="put", 
            url=url, 
            headers=headers
            )
        # 不能在这一步加载文件，否则会出现重试时无法载入已关闭文件描述符的bug

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
        # body = utils.json.dumps(data)
        body = data

        # 请求API
        resp = await self.request(
            method="post",
            url=url, 
            json=body, 
            timeout=20
            )
        assert resp
    
    async def get_blrec_data(self, room_id=-1, page=1, size=100, select="all"):
        '获取blrec信息'
        params = {
            "select": select,
            "size": size,
            "page": page,
            }
        if room_id != -1:
            url = f"{config.blrec['url_blrec']}/api/v1/tasks/{room_id}/data"
        else:
            url = f"{config.blrec['url_blrec']}/api/v1/tasks/data"
        response_json = await self.request(
            method="get",
            url=url, 
            params=params
            )

        return response_json

class Config:
    __app:dict
    __log:dict
    __alist:dict
    __blrec:dict
    __autobackup:dict
    __cookies:dict

    def __init__(self, config_path="settings.toml"):
        self.load(config_path)

    @property
    def app(self):
        'api设置'
        return self.__app

    @property
    def cookies(self):
        'cookies设置'
        return self.__cookies

    @property
    def autobackup(self):
        '自动备份设置'
        return self.__autobackup

    @property
    def blrec(self):
        'blrec设置'
        return self.__blrec

    @property
    def alist(self):
        'alist设置'
        return self.__alist

    @property
    def log(self):
        '日志记录器'
        return self.__log

    def write_default(self):
        '写入默认配置'
        self.DEFAULT_SETTINGS = r"""[blrec]
url_blrec = 'http://localhost:2233'

[alist]
enabled = true # optional, true for default
url_alist = 'http://localhost:5244'
username = 'wase'
password = 'AFFA9DBA2C1A74EB34F1585110B0A414F9693AF93BC52C218BE2EEBE7309C43B'
# secured password format: sha256(<your password>-https://github.com/alist-org/alist)
remote_dir = '/quark/2024_下/{time/%y%m%d}_{room_info/title}'
# usage: {time/<time formatting expressions>} or {<keys of recording properties>/<attribute>}
# (Refer to README.md)
remove_after_upload = false # optional, whether delete local file after upload, false by default

[cookies]
check_interval = 43200 # optional, in seconds

[autobackup]
# Settings for auto backup
check_interval = 60 # optional, in seconds
[[autobackup.servers]]
# Support multiple remote configs, the same format as 'alist' part above
# For example, when remote_dir is set to /xxx, then it seems like:
# local(automatically get from blrec): /aaa/bbb/ccc/d.flv(xml,jsonl...) -> remote: /xxx/ccc/d.flv(xml,jsonl...)
enabled = true
time = "07:00:00"
url_alist = 'http://192.168.1.1:5244'
username = 'username'
password = 'SHA-256'
remote_dir = '/remote/records/'
remove_after_upload = false

[server]
host_server = 'localhost'
port_server = 23560
max_retries = 6

[log]
file = "logs.log" # Leave empty to disable logging to file
level = "INFO"
"""
        with open("settings.toml", 'w', encoding='utf-8') as f:
            logger.info("Writing default settings...")
            f.write(self.DEFAULT_SETTINGS)
            quit()

    def load(self, config_path="settings.toml"):
        '加载配置'
        logger.info(f"Loading config {config_path}...")
        with open(config_path, 'r', encoding='utf-8') as f:
            config_file = toml.load(f)
            self.__app = config_file.get('server', {})
            self.__autobackup = config_file.get('autobackup', {})
            self.__cookies = config_file.get('cookies', {})
            self.__blrec = config_file.get('blrec', {})
            self.__alist = config_file.get('alist', {})
            self.__log = config_file.get('log', {})

        # 设置默认值
        self.__app.setdefault('max_retries', 6)

        self.__log.setdefault('file', '')

        self.__alist.setdefault('remove_after_upload', False)
        self.__alist.setdefault('enabled', True)

        self.__autobackup.setdefault('interval', 60)
        # self.settings_autobackup.setdefault('retry_times', 6)
        self.__autobackup.setdefault('servers', [])
        for i in self.__autobackup['servers']:
            i.setdefault('remove_after_upload', False)
            i.setdefault('enabled', True)
        
        self.__cookies.setdefault('check_interval', 43200)


# 初始化配置
config = Config()
config.load()

# 初始化自动备份服务器
backup_job_list = []

# 初始化alist连接会话
# session = None
session = AutoRecSession(max_retries=config.app['max_retries'])

# 初始化日志
log_file = config.log['file']
level = config.log['level']
logger.remove()
if log_file:
    logger.add(log_file, enqueue=True, level=level)
    logger.add(sys.stdout, enqueue=True, level="INFO")
else:
    logger.add(sys.stdout, enqueue=True, level=level)
