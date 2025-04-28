import autorec
import os, sys, getopt, time, re, requests, json

import bilibili_api as bili
#import bilibili_api.login
from bilibili_api import login_v2, request_settings
from bilibili_api.login_v2 import QrCodeLoginEvents
from static import logger, config

def usage():
    '--help'
    print("""
检查并更新cookies
-l / --login \t扫码登录
    -t / --tv \t使用TV端扫码登录(不指定的话默认使用Web端)
-c / --cookies \t检查cookies, 并决定是否刷新
    -f / --forced \t不管cookies有没有过期都强制刷新(optional)
-s / --sync \t将cookies同步到blrec
""")
    quit()

def cookie_dict2str(data:dict):
    'cookie_dict转换为字符串'
    s = ''
    for i in data.keys():
        s += "{}={};".format(i, data[i])
    return s

def load_credential():
    '从json导入credential'
    with open("credential.json", 'r') as f:
        credential_dict =json.load(f)
    credential = bili.Credential.from_cookies(credential_dict)
    return credential

def dump_credential(credential:bili.Credential):
    '导出credential到json'
    credential_dict = credential.get_cookies()
    with open("credential.json", 'w') as f:
        json.dump(credential_dict, f)

def login(is_tv=False):
    '登录账号'
    if is_tv:
        qr = login_v2.QrCodeLogin(platform=login_v2.QrCodeLoginChannel.TV)
    else:
        qr = login_v2.QrCodeLogin(platform=login_v2.QrCodeLoginChannel.WEB) # 生成二维码登录实例，平台选择网页端
    bili.sync(qr.generate_qrcode())                                          # 生成二维码
    while not qr.has_done():
        print(qr.get_qrcode_terminal())                                     # 生成终端二维码文本，打印
        while bili.sync(qr.check_state()) != QrCodeLoginEvents.TIMEOUT:                                            # 在完成扫描前轮询
            # print(bili.sync(qr.check_state()))                                   # 检查状态
            time.sleep(2)                                                   # 轮询间隔建议 >=1s
    credential = qr.get_credential()
    #credential = bili.login.login_with_qrcode_term()
    if not bili.sync(credential.check_valid()):
        ans = input("\nWarning: this account maybe invalid, continue?(y/N)")
        if ans.lower() != 'y':
            return
    print("Login complete, syncing to blrec...")

    # 保存并同步
    sync_cookies(credential=credential)

async def refresh_cookies(is_forced=False):
    '刷新cookies'
    # 加载cookies
    credential = load_credential()
    
    # 检查是否需要更新
    if not is_forced:
        logger.info("Checking cookies...")
        if await credential.check_refresh():
            print("Cookies expired, refreshing...")
        else:
            ans = input("Cookies not expired, proceed refreshing?(y/N): ")
            if ans.lower() != 'y':
                return
    
    # 刷新
    await credential.refresh()

    # 保存并同步
    sync_cookies(credential=credential)

def sync_cookies(credential=None):
    '保存cookies并同步到blrec'
    if not credential:
        credential = load_credential()
    else:
        dump_credential(credential)
    new_cookies = cookie_dict2str(credential.get_cookies())[:-1] # 去除最后的分号

    # 更新blrec的cookies
    new_data = {"header": {"cookie": new_cookies}}
    session = autorec.AutoRecSession(config.app['max_retries'])
    bili.sync(session.set_blrec(new_data))

    print(new_cookies)
    print("Cookies sync complete.")

def main():
    # 初始化
    #request_settings.set_enable_bili_ticket(True)
    request_settings.set_enable_auto_buvid(True)
    is_forced = False
    is_refresh_cookies = False
    is_login = False
    is_sync = False
    is_tv = False

    # 解析参数
    options, args = getopt.getopt(sys.argv[1:], "hfclst", ["help", "force", "cookies", "login", "sync", "tv"])
    for name, value in options:
        if name in ("-f","--forced"):
            is_forced = True
        if name in ("-h","--help"):
            usage()
        if name in ("-l","--login"):
            is_login = True # 必须检查完参数再进
        if name in ("-c","--cookies"):
            is_refresh_cookies = True
        if name in ("-s","--sync"):
            is_sync = True
        if name in ("-t","--tv"):
            is_tv = True

    if is_login:
        login(is_tv)
    if is_refresh_cookies:
        bili.sync(refresh_cookies(is_forced))
    if is_sync:
        sync_cookies()

if __name__ == "__main__":
    main()
