import os, time, requests, re, json, toml
import http.cookiejar, requests.utils

from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
import binascii

from urllib.parse import unquote
from http.server import HTTPServer, BaseHTTPRequestHandler

# classes
## 网络请求处理
class RequestHandler(BaseHTTPRequestHandler):
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
        event_type = json_obj[type]

        # 根据接收到的blrec参数执行相应操作
        try:
            if event_type == 'RecordingFinishedEvent':
                # 录制完成，更新cookies
                refresh_cookies()
            elif event_type == 'VideoPostprocessingCompletedEvent':
                # 视频后处理完成，上传到alist
        except Exception as e:
            print(e)
        
        # 回复
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(str(self.headers))

# functions

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

def dict2str(data:dict):
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
    session = requests.session()
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
    new_cookies = dict2str(cookies_dict)

    # 读取blrec设置
    settings_path = os.path.join(settings_dir, "settings.toml")
    with open(settings_path, 'r', encoding='utf-8') as f:
        settings_toml = toml.load(f)

    # 更新blrec设置
    settings_toml['header']['cookie'] = new_cookies[:-1]
    with open(settings_path, 'w', encoding='utf-8') as f:
        toml.dump(settings_toml, f)

## 上传视频

def get_token()

# const
## blrec
port_blrec = 2356
settings_dir = '/root/.blrec'

## alist
port_alist = 5244
username = 'admin'
password = ''

# main
if __name__ == "__main__":
    # const
    # 监听
    addr = ('', 23560)
    server = HTTPServer(addr, RequestHandler)
    server.serve_forever()
