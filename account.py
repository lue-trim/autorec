import autorec
import os, sys, getopt, time, re, requests, json

import bilibili_api as bili
#import bilibili_api.login
from static import logger, config

def usage():
    '--help'
    print("""检查并更新cookies
-l / --login \t扫码登录
-c / --cookies \t检查cookies, 并决定是否刷新
-s / --sync \t将cookies同步到blrec
-f / --forced \t不管cookies有没有过期都强制刷新(optional)""")
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

def login():
    '登录账号'
    credential = bili.login.login_with_qrcode_term()
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
    autorec.utils.run_async(coro=session.set_blrec(new_data))

    print(new_cookies)
    print("Cookies sync complete.")

def main():
    # 初始化
    is_forced = False
    is_refresh_cookies = False
    is_login = False
    is_sync = False

    # 解析参数
    options, args = getopt.getopt(sys.argv[1:], "hfcls", ["help", "force", "cookies", "login", "sync"])
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

    if is_login:
        login()
    if is_refresh_cookies:
        bili.sync(refresh_cookies(is_forced))
    if is_sync:
        sync_cookies()

if __name__ == "__main__":
    main()
