import os, sys, getopt, asyncio

from cookies_checker.utils import login, refresh_cookies, sync_cookies
#import bilibili_api.login

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


def main():
    # 初始化
    #request_settings.set_enable_bili_ticket(True)
    # request_settings.set_enable_auto_buvid(True)
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
        asyncio.run(login(is_tv))
    if is_refresh_cookies:
        asyncio.run(refresh_cookies(is_forced))
    if is_sync:
        asyncio.run(sync_cookies())

if __name__ == "__main__":
    main()
