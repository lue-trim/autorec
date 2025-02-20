import requests.adapters
import os, time, requests, re, json, toml, multiprocessing, traceback, datetime, threading
import http.cookiejar, requests.utils
import urllib3

from urllib.parse import unquote, quote
from http.server import HTTPServer, BaseHTTPRequestHandler

class Settings():
    '设置类'
    DEFAULT_SETTINGS = r"""[blrec]
host_blrec = 'localhost'
port_blrec = 2233

[alist]
enabled = true # optional, true for default
port_alist = 5244
host_alist = 'localhost'
username = 'wase'
password = 'AFFA9DBA2C1A74EB34F1585110B0A414F9693AF93BC52C218BE2EEBE7309C43B'
# secured password format: sha256(<your password>-https://github.com/alist-org/alist)
remote_dir = '/quark/2024_下/{time/%y%m%d}_{room_info/title}'
# usage: {time/<time formatting expressions>} or {<keys of recording properties>/<attribute>}
# (Refer to README.md)
remove_after_upload = false # optional, whether delete local file after upload, false by default
retry_times = 6 # Not implemented, but maybe useful in the future 

[autobackup]
# Settings for auto backup
timer_interval = 60 # optional, seconds of upload timer interval
[[autobackup.servers]]
# Support multiple remote configs, the same format as 'alist' part above
# For example, when remote_dir is set to /xxx, then it seems like:
# local(automatically get from blrec): /aaa/bbb/ccc/d.flv(xml,jsonl...) -> remote: /xxx/ccc/d.flv(xml,jsonl...)
enabled = true
time = "07:00:00"
port_alist = 5244
host_alist = '192.168.1.1'
username = 'username'
password = 'SHA-256'
remote_dir = '/remote/records/'
remove_after_upload = false

[server]
host_server = 'localhost'
port_server = 23560
"""

    @classmethod
    def load_settings(self):
        '加载设置'
        if not os.path.exists("settings.toml"):
            with open("settings.toml", 'w', encoding='utf-8') as f:
                print("正在导出默认配置")
                f.write(self.DEFAULT_SETTINGS)
                quit()
        else:
            with open("settings.toml", 'r', encoding='utf-8') as f:
                self.settings = toml.load(f)
        
            ## blrec
            self.settings_blrec = self.settings['blrec']
            self.host_blrec = self.settings_blrec['host_blrec']
            self.port_blrec = self.settings_blrec['port_blrec']

            ## alist
            self.settings_alist:dict = self.settings['alist']
            self.settings_alist.setdefault('remove_after_upload', False)
            self.settings_alist.setdefault('enabled', True)

            ## autobackup
            self.settings_autobackup:dict = self.settings['autobackup']
            self.settings_autobackup.setdefault('timer_interval', 60)
            # self.settings_autobackup.setdefault('retry_times', 6)
            self.settings_autobackup.setdefault('servers', [])
            for i in self.settings_autobackup['servers']:
                i.setdefault('remove_after_upload', False)
                i.setdefault('enabled', True)

            ## server
            self.settings_server = self.settings['server']
            self.host_server = self.settings_server['host_server']
            self.port_server = self.settings_server['port_server']

class AutoBackuper():
    '自动备份工具'
    def __init__(self) -> None:
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

    def __upload_action(self, task_dict):
        '执行上传'
        # session
        session = AutoRecSession()
        session.mount('http://', requests.adapters.HTTPAdapter(max_retries=3))
        token = session.get_alist_token(Settings.settings_alist)
        
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
        session = AutoRecSession()
        session.mount('http://', requests.adapters.HTTPAdapter(max_retries=3))
        token = session.get_alist_token(settings_temp)

        # 上传文件
        pool = multiprocessing.Pool()
        for filename in filenames:
            local_filename = os.path.join(local_dir, filename)
            dest_filename = os.path.join(dest_dir, filename)
            pool.apply_async(session.upload_alist_action, args=[settings_temp, token, local_filename, dest_filename])
        pool.close()
        pool.join()
    
    def __check_time(self, interval):
        '循环检查时间'
        while self.running:
            for task_id, task_dict in enumerate(self.task_list):
                if datetime.datetime.now() >= task_dict['time'] and task_dict['status'] == 'waiting':
                    # 发现到点了并且待上传
                    print(f"Auto backuping...\n{task_dict}")
                    self.change_status(task_id, 'uploading')
                    # 上传
                    try:
                        self.__upload_action(task_dict)
                    except:
                        traceback.print_exc()
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
                f"{config_temp['host_alist']}:{config_temp['port_alist']}{config_temp['remote_dir']}"
            )
        return res_str

# classes
class RequestHandler(BaseHTTPRequestHandler):
    '网络请求服务器'
    def do_PUT(self):
        # 读取参数
        data = self.rfile.read(int(self.headers['content-length']))
        data = unquote(str(data, encoding='utf-8'))
        path = self.path.replace("/",'')
        if path == 'autobackup':
            Settings.load_settings()
            # 回复
            self.reply(message='Settings reloaded.')
        else:
            self.reply(code=404)

    def do_GET(self):
        # 读取参数
        data = self.rfile.read(int(self.headers['content-length'])) # content-length不能去掉
        data = unquote(str(data, encoding='utf-8'))
        path = self.path.replace("/",'')
        if path == 'autobackup':
            # 回复
            self.reply(message='Backup task sent.', data=autobackuper.show_status())
        else:
            self.reply(code=404)

    def do_DELETE(self):
        '接收DELETE信息'
        # 读取参数
        data = self.rfile.read(int(self.headers['content-length']))
        data = unquote(str(data, encoding='utf-8'))
        path = self.path.replace("/",'')
        if path == 'autobackup':
            # 删除备份任务
            json_obj = json.loads(data)
            id = json_obj['id']
            is_del_all = json_obj.get('all', False)
            status = autobackuper.del_task(int(id), is_del_all)
            # 回复
            self.reply(message='Backup task complete.', data=status)
        else:
            self.reply(code=404)

    def do_PATCH(self):
        '接收PATCH信息'
        # 读取参数
        data = self.rfile.read(int(self.headers['content-length']))
        data = unquote(str(data, encoding='utf-8'))
        path = self.path.replace("/",'')
        if path == 'autobackup':
            # 重试备份任务
            json_obj = json.loads(data)
            id = json_obj.get('id', -1)
            if json_obj.get('all', False):
                for idx, task in enumerate(autobackuper.task_list):
                    if task['status'] == "failed":
                        autobackuper.change_status(idx, "waiting")
                status = autobackuper.show_status()
            else:
                if type(id) is not int:
                    self.reply(code=500, message='非法id数据类型')
                status = autobackuper.change_status(id, "waiting")
            # 回复
            self.reply(message='Readded backup task.', data=status)
        else:
            self.reply(code=404)

    def do_POST(self):
        '接收到POST信息时'
        # 读取参数
        data = self.rfile.read(int(self.headers['content-length']))
        data = unquote(str(data, encoding='utf-8'))
        path = self.path.replace("/",'')

        if path == "blrec":
            # 处理blrec请求
            json_obj = json.loads(data)
            event_type = json_obj['type']
            session = AutoRecSession()
            session.mount('http://', requests.adapters.HTTPAdapter(max_retries=3))
            # 根据接收到的blrec webhook参数执行相应操作
            # 更新：不用套try语句，要是出错http模块会自己处理
            if event_type == 'RecordingFinishedEvent':
                # 录制完成，如果没有其他在录制的任务的话就更新一下cookies
                if not session.get_blrec_data(select='recording'):
                    refresh_cookies()
            elif event_type == 'VideoPostprocessingCompletedEvent':
                # 视频后处理完成，上传+自动备份
                # 获取直播间信息
                room_id = json_obj['data']['room_id']
                room_info = session.get_blrec_data(room_id)
                # 上传
                filename = json_obj['data']['path']
                try:
                    upload_video(filename, rec_info=room_info, settings_alist=Settings.settings_alist)
                except:
                    traceback.print_exc()
                # 自动备份
                local_dir = os.path.split(filename)[0]
                add_autobackup(autobackuper=autobackuper, settings_autobackup=Settings.settings_autobackup, local_dir=local_dir)
            else:
                print("Got new Event: ", event_type)
            # 回复
            self.reply()
        
        elif path == "autobackup":
            # 添加备份任务
            json_obj = json.loads(data)
            # 获取数据
            local_dir = json_obj['local_dir']
            config_toml = json_obj['config_toml']
            with open(config_toml, 'r', encoding='utf-8') as f:
                settings_temp = toml.load(f)
            # 添加
            add_autobackup(autobackuper=autobackuper, settings_autobackup=settings_temp['autobackup'], local_dir=local_dir)
            # 回复
            self.reply(message='Backup task added.', data=autobackuper.show_status())

    def reply(self, code=200, message='Mua!\n', data=''):
        # 回复
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        data = {
            "code": code,
            "message": message,
            "data": data,
        }
        self.wfile.write(json.dumps(data).encode())

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

        # 计算上传时间
        new_time = datetime.datetime.now()
        delta_time = new_time - self.last_time
        secs = delta_time.total_seconds()
        if secs <= 0:
            secs = 1.0
        self.last_time = new_time

        # 输出进度并返回
        print("Read: {:.2f}%".format(
            self.current_size / self.total_size * 100,
            #self.current_size / secs / 1024
        ),
        end='          \r')
        return self.fp.read(size)

    def __len__(self):
        '获取文件大小，给http模块调用'
        return self.get_size()

class AutoRecSession(requests.Session):
    '本地http通信专用类'
    def get_alist_token(self, settings_alist:dict):
        '获取alist管理token'
        url = "http://{}:{}{}".format(settings_alist['host_alist'], settings_alist['port_alist'], '/api/auth/login/hash')
        params = {
            "username": settings_alist['username'],
            "password": settings_alist['password'].lower()
        }
        headers = {
            'Content-Type': 'application/json'
        }

        # 请求API
        data = utils.dict2str(params)
        response = self.post(url, data=data, headers=headers)
        response_json = response.json()
        # 获取结果
        if response_json['code'] == 200:
            print("Get token success.")
            return response_json['data']['token']
        else:
            print("Get token failed,", response_json['message'])
            return ""
    
    def copy_alist(self, settings_alist:dict, token:str, source_dir:str, filenames:list, dist_dir:str):
        '复制文件'
        # 请求参数
        url = "http://{}:{}{}".format(settings_alist['host_alist'], settings_alist['port_alist'], '/api/fs/copy')
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
        response = self.post(url=url, data=utils.dict2str(data), headers=headers)
        data = response.json()

        # 获取结果
        if data['code'] == 200:
            print("Copy success.")
        else:
            print("Copy failed,", data['message'])
        
        return data['code']
    
    def rm_alist(self, settings_alist:dict, token:str, dirname:str, filenames:list):
        '删除文件'
        # 请求参数
        url = "http://{}:{}{}".format(settings_alist['host_alist'], settings_alist['port_alist'], '/api/fs/remove')
        headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }
        data = {
            "dir": dirname,
            "names": filenames
        }

        # 请求API
        response = self.post(url=url, data=utils.dict2str(data), headers=headers)
        data = response.json()

        # 获取结果
        if data['code'] == 200:
            print("Remove success:", dirname, filenames)
        else:
            print("Remove failed:", dirname, filenames, data['message'])
        
        return data['code']

    def upload_alist_action(self, settings_alist:dict, token:str, local_filename:str, dest_filename:str):
        '供multiprocessing使用的流式上传文件，自动重试6次以防上传时网盘抽风'
        for i in range(6):
            try:
                self.upload_alist(settings_alist, token, local_filename, dest_filename)
            except:
                traceback.print_exc()
                time.sleep(4**i)
        else:
            from requests.exceptions import RequestException
            raise RequestException()

    def upload_alist(self, settings_alist:dict, token:str, filename:str, dest_filename:str):
        '流式上传文件'
        dest_filename = quote(dest_filename) # URL编码

        # 请求参数
        url = "http://{}:{}{}".format(settings_alist['host_alist'], settings_alist['port_alist'], '/api/fs/put')
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
            response = requests.put(url=url, data=data, headers=headers)
        response_json = response.json()
        
        if response_json['code'] == 200:
            print("\nUpload success:", filename) # 加个\n防止覆盖上传进度条
            # 是否在上传后删除文件
            if settings_alist['remove_after_upload']:
                os.remove(filename)
        else:
            raise Exception("{} Upload failed: {}".format(filename, response_json))

    def upload_alist_form(self, settings_alist:dict, token:str, filename: str):
        '表单上传文件（已废弃）'
        # 文件名处理
        filename_split = os.path.split(filename)
        target_filename = filename_split[1] # 目标文件名
        target_dir = os.path.split(filename_split[0])[1] # 目标文件夹
        filepath = "/quark/{}/{}".format(target_dir, target_filename)
        filepath = quote(filepath) # URL编码

        # 请求参数
        #token = self.get_alist_token(settings_alist)
        url = "http://{}:{}{}".format(settings_alist['host_alist'], settings_alist['port_alist'], '/api/fs/form')
        headers = {
            "Authorization": token,
            "File-Path": filepath,
            "As-Task": "True",
            "Content-Type": "multipart/form-data",
            "Content-Length": str(os.path.getsize(filename))
        }
        data = File(filename)
        data = urllib3.encode_multipart_formdata()
        # 请求API
        res2 = requests.put(url=url, data=data, headers=headers).json()
        print(res2)

    def set_blrec(self, data: dict):
        '更改blrec设置'
        host_blrec = Settings.host_blrec
        port_blrec = Settings.port_blrec
        url = "http://{}:{}{}".format(host_blrec, port_blrec, '/api/v1/settings')
        body = utils.dict2str(data)

        # 请求API
        self.patch(url, data=body, timeout=10)
    
    def get_blrec_data(self, room_id=-1, page=1, size=100, select="all"):
        '获取blrec信息'
        host_blrec = Settings.host_blrec
        port_blrec = Settings.port_blrec
        params = {
            "select": select,
            "size": size,
            "page": page,
            }
        if room_id != -1:
            url = "http://{}:{}{}".format(host_blrec, port_blrec, '/api/v1/tasks/{}/data'.format(room_id))
        else:
            url = "http://{}:{}{}".format(host_blrec, port_blrec, '/api/v1/tasks/data')
        response = self.get(url=url, params=params)
        response_json = response.json()

        return response_json

## 奇奇怪怪的功能
class utils:
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
def refresh_cookies():
    '刷新cookies'
    import account
    account.refresh_cookies(True)

def upload_video(video_filename: str, settings_alist=None, rec_info=None):
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
    
    # session
    session = AutoRecSession()
    session.mount('http://', requests.adapters.HTTPAdapter(max_retries=3))

    # 获取token
    token = session.get_alist_token(settings_alist)

    # 上传文件
    pool = multiprocessing.Pool()
    for i in filenames:
        local_filename = i[0]
        dest_filename = i[1]
        pool.apply_async(session.upload_alist_action, args=[settings_alist, token, local_filename, dest_filename])
    pool.close()
    pool.join()


def add_autobackup(autobackuper:AutoBackuper, settings_autobackup:dict, local_dir:str):
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

            # 决定要不要第二天再启动
            if time_today < scheduled_time:
                scheduled_date = datetime_now.strftime(r'%y/%m/%d')
            else:
                scheduled_date = (datetime_now + datetime.timedelta(days=1)).strftime(r'%y/%m/%d')
            formatted_time = f"{scheduled_date}T{scheduled_time}"
            t = datetime.datetime.strptime(formatted_time, r"%y/%m/%dT%H:%M:%S")

            # 添加任务
            autobackuper.add_task(
                t = t, 
                local_dir = local_dir, 
                settings_alist = settings_alist
                )
        except Exception:
            traceback.print_exc()

# main
if __name__ == "__main__":
    # 加载toml
    Settings.load_settings()

    # 自动备份
    autobackuper = AutoBackuper()
    autobackuper.start_check(Settings.settings_autobackup)

    # 监听
    addr = (Settings.host_server, Settings.port_server)
    server = HTTPServer(addr, RequestHandler)
    try:
        server.serve_forever()
    except Exception:
        # 好像没什么用，但总之先留着
        autobackuper.running = False
