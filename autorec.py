import os, time, requests, re, json, toml, multiprocessing
import http.cookiejar, requests.utils
import urllib3

from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
import binascii

from urllib.parse import unquote, quote
from http.server import HTTPServer, BaseHTTPRequestHandler

# classes
class RequestHandler(BaseHTTPRequestHandler):
    '网络请求服务器'
    def do_POST(self):
        '接收到POST信息时'
        # 读取参数
        data = self.rfile.read(int(self.headers['content-length']))
        data = unquote(str(data, encoding='utf-8'))
        json_obj = json.loads(data)
        event_type = json_obj['type']

        # 根据接收到的blrec webhook参数执行相应操作
        try:
            if event_type == 'RecordingFinishedEvent':
                # 录制完成，更新cookies
                refresh_cookies()
            elif event_type == 'VideoPostprocessingCompletedEvent':
                # 视频后处理完成，上传到alist
                filename = json_obj['data']['path']
                upload_video(filename)
            else:
                print("Got new Event: ", event_type)
        except Exception as e:
            print(e)
        
        # 回复
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        data = {
            "code": 200,
            "message": "Mua!"
        }
        self.wfile.write(data)

class File:
    '表单上传用文件类'
    def __init__(self, fp, filename):
        self.filename = filename
        self.fp = fp

    def read(self, size=-1):
        'read方法，给requests调用'
        #with open(self.filename, 'rb') as file:
        return self.fp.read(10000)

    def __len__(self):
        return os.path.getsize(self.filename)

class AutoRecSession(requests.Session):
    '本地http通信专用类'
    def get_alist_token(self):
        '获取alist管理token'
        url = "http://{}:{}{}".format(host_alist, port_alist, '/api/auth/login/hash')
        params = {
            "username": username,
            "password": password.lower()
        }
        headers = {
            'Content-Type': 'application/json'
        }

        # 请求API
        data = dict2str(params)
        response = self.post(url, data=data, headers=headers)
        response_json = response.json()
        # 获取结果
        if response_json['code'] == 200:
            print("Get token success.")
            return response_json['data']['token']
        else:
            print("Get token failed,", response_json['message'])
            return ""
    
    def copy_alist(self, token:str, source_dir:str, filenames:list, dist_dir:str):
        '复制文件'
        # 请求参数
        url = "http://{}:{}{}".format(host_alist, port_alist, '/api/fs/copy')
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
        response = self.post(url=url, data=dict2str(data), headers=headers)
        data = response.json()

        # 获取结果
        if data['code'] == 200:
            print("Copy success.")
        else:
            print("Copy failed,", data['message'])
        
        return data['code']
    
    def rm_alist(self, token:str, dirname:str, filenames:list):
        '删除文件'
        # 请求参数
        url = "http://{}:{}{}".format(host_alist, port_alist, '/api/fs/remove')
        headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }
        data = {
            "dir": dirname,
            "names": filenames
        }

        # 请求API
        response = self.post(url=url, data=dict2str(data), headers=headers)
        data = response.json()

        # 获取结果
        if data['code'] == 200:
            print("Remove success.")
        else:
            print("Remove failed,", data['message'])
        
        return data['code']
        
    def upload_alist(self, token:str, filename:str, dist_filename:str, remove_after_upload=False):
        '流式上传文件'
        dist_filename = quote(dist_filename) # URL编码

        # 请求参数
        url = "http://{}:{}{}".format(host_alist, port_alist, '/api/fs/put')
        headers = {
            "Authorization": token,
            "File-Path": dist_filename,
            "As-Task": "True",
            "Content-Type": "application/octet-stream",
            "Content-Length": ""
        }

        # 打开文件
        with open(filename, 'rb') as f:
            data = File(f, filename)
            # 请求API
            response = requests.put(url=url, data=data, headers=headers)
        response_json = response.json()
        
        if response_json['code'] == 200:
            print("Upload success.")
            # 是否在上传后删除文件
            if remove_after_upload:
                os.remove(filename)
        else:
            print("Upload failed,", response['message'])

    def upload_alist_form(self, token:str, filename: str):
        '表单上传文件（已废弃）'
        # 文件名处理
        filename_split = os.path.split(filename)
        target_filename = filename_split[1] # 目标文件名
        target_dir = os.path.split(filename_split[0])[1] # 目标文件夹
        filepath = "/quark/{}/{}".format(target_dir, target_filename)
        filepath = quote(filepath) # URL编码

        # 请求参数
        #token = self.get_alist_token()
        url = "http://{}:{}{}".format(host_alist, port_alist, '/api/fs/form')
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
        url = "http://{}:{}{}".format(host_blrec, port_blrec, '/api/v1/settings')
        body = dict2str(data)

        # 请求API
        self.patch(url, data=body)

# functions
## 奇奇怪怪的功能
def dict2str(data: dict):
    '将dict转换为符合http要求的字符串'
    s = str(data)
    return s.replace('\'', '\"')

## 刷新cookies
def getCorrespondPath(ts):
    '获取刷新地址'
    key = RSA.importKey('''\
    -----BEGIN PUBLIC KEY-----
    MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDLgd2OAkcGVtoE3ThUREbio0Eg
    Uc/prcajMKXvkCKFCWhJYJcLkcM2DKKcSeFpD/j6Boy538YXnR6VhcuUJOhH2x71
    nzPjfdTcqMz7djHum0qSZA0AyCBDABUqCrfNgCiJ00Ra7GmRj+YCK1NJEuewlb40
    JNrRuoEUXpabUzGB8QIDAQAB
    -----END PUBLIC KEY-----''')

    cipher = PKCS1_OAEP.new(key, SHA256)
    encrypted = cipher.encrypt(f'refresh_{ts}'.encode())
    return binascii.b2a_hex(encrypted).decode()

def cookie_dict2str(data:dict):
    'cookie_dict转换为字符串'
    s = ''
    for i in data.keys():
        s += "{}={};".format(i, data[i])
    return s

def refresh_cookies():
    '刷新cookies'
    # 获取刷新地址
    ts = round(time.time() * 1000)
    correspondPath = getCorrespondPath(ts)

    # header和session
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0'
        }
    session = AutoRecSession()
    session.cookies = http.cookiejar.LWPCookieJar()
    session.cookies.load(filename='cookies.txt', ignore_discard=True, ignore_expires=True)
    cookies_dict = requests.utils.dict_from_cookiejar(session.cookies)

    # 获取refresh_csrf
    response = session.get(
        url="https://www.bilibili.com/correspond/1/{}".format(correspondPath), 
        headers=headers
        )
    refresh_csrf = re.search(r'(?<=<div id="1-name">).*?(?=</div>)', response.text).group()

    # 获取refresh_token
    with open("loginData.json", 'r', encoding='utf-8') as f:
        data = json.load(f)
    refresh_token = data['refresh_token']

    # 刷新cookies
    response = session.post(
        url='https://passport.bilibili.com/x/passport-login/web/cookie/refresh', 
        headers=headers, 
        params={
            'csrf': cookies_dict['bili_jct'], 
            'refresh_csrf': refresh_csrf, 
            'source': 'main_web',
            'refresh_token': refresh_token
            }
        )
    js = response.json()
    data = js['data']

    # 提取新的登录信息
    loginData = data

    # 提取新的csrf
    cookies_dict = requests.utils.dict_from_cookiejar(session.cookies)
    csrf = cookies_dict['bili_jct']

    # 确认更新
    print("正在更新cookies")
    response = session.post(
        url='https://passport.bilibili.com/x/passport-login/web/confirm/refresh', 
        headers=headers, 
        params={
            'csrf': csrf, 
            'refresh_token': refresh_token
            }
        )
    code = response.json()['code']
    if code == 0:
        print("更新成功")
    else:
        print(response.json()['message'])
        return

    # 保存登录信息
    with open("loginData.json", 'w', encoding='utf-8') as f:
        json.dump(loginData, f)

    # 保存cookies
    session.cookies.save(filename='cookies.txt')
    new_cookies = cookie_dict2str(cookies_dict)[:-1] # 去除最后的分号

    # 更新blrec的cookies
    new_data = {"header": {"cookie": new_cookies}}
    session.set_blrec(new_data)

def upload_video(video_filename: str):
    '上传视频'
    # 文件名处理
    appendices = ['flv', 'jsonl', 'xml', 'jpg', 'mp4'] # 可能存在的后缀名
    filenames = []
    for appendix in appendices:
        # 以下两块自己处理
        filename_split = os.path.split(video_filename)
        target_filename = filename_split[1] # 目标文件名
        target_dir = os.path.split(filename_split[0])[1] # 目标文件夹(日期)

        local_filename = "{}{}".format(video_filename[:-3], appendix)
        dist_filename = "/quark/{}/{}{}".format(target_dir, target_filename[:-3], appendix) # 给文件加上不同的后缀名

        # [本地文件名, 远程文件名]
        if os.path.exists(local_filename):
            filenames.append([local_filename, dist_filename])
    
    # session
    session = AutoRecSession()

    # 获取token
    token = session.get_alist_token()

    # 上传文件
    pool = multiprocessing.Pool()
    for i in filenames:
        local_filename = i[0]
        dist_filename = i[1]
        pool.apply_async(session.upload_alist, args=[token, local_filename, dist_filename, True])
    pool.close()

# 加载toml
with open("settings.toml", 'r', encoding='utf-8') as f:
    settings = toml.load(f)

# const
## blrec
settings_blrec = settings['blrec']
host_blrec = settings_blrec['host_blrec']
port_blrec = settings_blrec['port_blrec']

## alist
settings_alist = settings['alist']
host_alist = settings_alist['host_alist']
port_alist = settings_alist['port_alist']
username = settings_alist['username']
password = settings_alist['password']

## server
settings_server = settings['server']
host_server = settings_server['host_server']
port_server = settings_server['port_server']

# main
if __name__ == "__main__":
    # const
    # 监听
    addr = (host_server, port_server)
    print("service started")
    server = HTTPServer(addr, RequestHandler)
    server.serve_forever()
