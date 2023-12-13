import os, time, requests, re, json, toml, multiprocessing
import http.cookiejar, requests.utils

from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
import binascii

from urllib.parse import unquote, quote
from http.server import HTTPServer, BaseHTTPRequestHandler

# classes
class RequestHandler(BaseHTTPRequestHandler):
    '网络请求服务器'
    def _writeheaders(self):
        print(self.path)
        print(self.headers)

    def do_Head(self):
        self._writeheaders()

    def do_GET(self):
        self._writeheaders()
        self.wfile.write(str(self.headers))

        # 回复
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(str(self.headers))

    def do_POST(self):
        # 读取参数
        data = self.rfile.read(int(self.headers['content-length']))
        data = unquote(str(data, encoding='utf-8'))
        json_obj = json.loads(data)
        event_type = json_obj['type']

        # 根据接收到的blrec参数执行相应操作
        try:
            if event_type == 'RecordingFinishedEvent':
                # 录制完成，更新cookies
                refresh_cookies()
            elif event_type == 'VideoPostprocessingCompletedEvent':
                # 视频后处理完成，上传到alist
                filename = json_obj['data']['path']
                upload_video(filename=filename)
        except Exception as e:
            print(e)
        
        # 回复
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(str(self.headers))

class AutoRecSession(requests.Session):
    '本地http通信专用类'
    def get_alist_token(self):
        '获取alist管理token'
        url = "http://localhost:{}{}".format(port_alist, '/api/auth/login/hash')
        params = {
            "username": username,
            "password": password
        }
        headers = {
            'Content-Type': 'application/json'
        }

        # 请求API
        data = dict2str(params)
        response = self.post(url, data=data, headers=headers)
        data = response.json()['data']
        
        return data['token']
    
    def upload_alist(self, token:str, filename: str):
        '上传文件'
        # 文件名处理
        filename_split = os.path.split(filename)
        target_filename = filename_split[1] # 目标文件名
        target_dir = os.path.split(filename_split[0])[1] # 目标文件夹
        filepath = "/quark/{}/{}".format(target_dir, target_filename)
        filepath = quote(filepath) # URL编码

        # 请求参数
        url = "http://localhost:{}{}".format(port_alist, '/api/fs/put')
        headers = {
            "Authorization": token,
            "File-Path": filepath,
            "As-Task": "True",
            "Content-Type": "application/octet-stream",
            "Content-Length": ""
        }
        data = {
            "body": "file:/{}".format(filename)
        }

        # 请求API
        response = self.put(url=url, data=dict2str(data), headers=headers)
        data = response.json()

        # 上传完成后删除文件
        if data['code'] == 200:
            print("Upload success.")
            os.remove(filename)
        else:
            print("Upload failed,", data['message'])
    
    def set_blrec(self, data: dict):
        '更改blrec设置'
        url = "http://localhost:{}{}".format(port_blrec, '/api/v1/settings')
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

def upload_video(filename: str):
    '上传视频'
    # session
    session = AutoRecSession()

    # 获取token
    token = session.get_alist_token()

    # 上传文件
    pool = multiprocessing.Pool()
    pool.apply_async(session.upload_alist, args=[token, filename])
    pool.close()

# 加载toml
with open("settings.toml", 'r', encoding='utf-8') as f:
    settings = toml.load(f)

# const
## blrec
settings_blrec = settings['blrec']
port_blrec = settings_blrec['port_blrec']
settings_dir = settings_blrec['settings_dir']

## alist
settings_alist = settings['alist']
port_alist = settings_alist['port_alist']
username = settings_alist['username']
password = settings_alist['password']

# main
if __name__ == "__main__":
    # const
    # 监听
    addr = ('', 23560)
    server = HTTPServer(addr, RequestHandler)
    server.serve_forever()
