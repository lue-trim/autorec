import sys, toml, asyncio, traceback, json, os
# from requests.adapters import HTTPAdapter
from loguru import logger

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

# 初始化日志
log_file = config.log['file']
level = config.log['level']
logger.remove()
if log_file:
    logger.add(log_file, enqueue=True, level=level)
    logger.add(sys.stdout, enqueue=True, level="INFO")
else:
    logger.add(sys.stdout, enqueue=True, level=level)
