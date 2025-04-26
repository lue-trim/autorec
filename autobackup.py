# import autorec
# import aiohttp
# from autorec import AutoRecSession, utils
from static import logger, Config

def reload_settings(url):
    '重载autorec配置文件'
    import requests, json
    # 请求参数
    url = f"{url}/settings/reload"
    headers = {
        "Content-Type": "application/json",
    }

    # 请求API
    response = requests.post(url=url, headers=headers)
    # data = response.json()
    print("重载设置成功", sep='\n')

def add_task(url, local_dir, config_file, now=False):
    '添加任务'
    import requests, json
    # 请求参数
    url = f"{url}/autobackup"
    headers = {
        "Content-Type": "application/json",
    }
    data = {
        "local_dir": local_dir,
        "config_toml": config_file,
        "now": now,
    }

    # 请求API
    # utils.run_async(AutoRecSession.post(url=url, params=data, headers=headers))
    response = requests.post(url=url, params=data, headers=headers)
    data = response.json()
    logger.info("Autobackup task created.")
    # logger.info(data)
    print(data['data'])

def del_retry_task(url, index=-1, retry=False, is_clear_all=False):
    '删除或重试任务'
    import requests, json
    # 请求参数
    headers = {
        "Content-Type": "application/json",
    }
    data = {
        "id": index,
        "all": is_clear_all,
    }

    # 请求API
    if retry:
        response = requests.post(url=f"{url}/autobackup/retry", params=data, headers=headers)
    else:
        response = requests.delete(url=f"{url}/autobackup", params=data, headers=headers)
    data = response.json()
    logger.log("Autobackup task modified.")
    print(data['data'])

def show_task(url):
    '列出任务'
    import requests, json
    # 请求参数
    url = f"{url}/autobackup"
    headers = {
        "Content-Type": "application/json",
    }
    data = {
        "id": 0,
    }

    # 请求API
    response = requests.get(url=url, params=data, headers=headers)
    data = response.json()
    print(data['data'], sep='\n')

def usage():
    '--help'
    print("""定时备份任务管理
--reload \t重载全局autorec配置
-u/--upload <pathname> \t立即手动上传任务
-s/--show \t查看任务列表
-a/--add <pathname> \t新增任务, 并在<pathname>处指定目录位置
-t/--retry <task-id/all> \t手动重试备份失败的任务, 输入值可以是任务id, 也可以是"all"
-d/--delete <task-id/all> \t删除任务
-c/--config <config_file> \t指定临时载入使用的服务器配置, 默认值settings.toml

e.g.:
指定配置文件并添加定时上传任务: python autobackup.py --add /home/123 -c settings2.toml
使用默认配置, 立即上传: \tpython autobackup.py --upload /home/123
让服务端重新载入配置文件: \tpython autobackup.py --reload -c settings.toml
删除ID=2的定时任务: \tpython autobackup.py --delete 2
重试所有失败的任务(已经完成的不会计入): \tpython autobackup.py --retry all
""")
    quit()

def main():
    import getopt, os, sys, toml
    # 初始化
    config_file = "settings.toml"
    add_dir = ""
    upload_dir = ""
    del_id = -1
    retry_id = -1
    is_show = False
    is_add = False
    is_delete = False
    is_reload = False
    is_retry = False

    # 解析参数
    options, args = getopt.getopt(
        sys.argv[1:], 
        "hc:sa:d:r:u:", 
        ["help", "config=", "show", "add=", "delete=", "reload", "retry=", "upload="]
        )
    for name, value in options:
        if name in ("-h","--help"):
            usage()
        elif name in ("-c","--config"):
            config_file = value
        elif name in ("-a","--add"):
            add_dir = value
        elif name in ("-s","--show"):
            is_show = True
        elif name in ("-d","--delete"):
            is_delete = True
            if value.lower() == "all":
                del_id = -1
            else:
                del_id = int(value)
        elif name == "--reload":
            is_reload = True
        elif name in ("-t","--retry"):
            is_retry = True
            if value.lower() == "all":
                retry_id = -1
            else:
                retry_id = int(value)
        elif name in ("--upload", '-u'):
            upload_dir = value

    # 检查相容性
    # 请求地址
    config = Config(config_file)
    url = f"http://{config.app['host_server']}:{config.app['port_server']}"

    # 切换模式
    if is_reload:
        reload_settings(url)
    if is_show:
        show_task(url)
    if add_dir:
        add_task(url, config_file=config_file, local_dir=add_dir)
    if is_delete:
        del_retry_task(
            url, 
            del_id, 
            is_clear_all=del_id == -1, 
            retry=False
        )
    if is_retry:
        del_retry_task(
            url, 
            retry_id, 
            is_clear_all=retry_id == -1, 
            retry=True
        )
    if upload_dir:
        add_task(url, config_file=config_file, local_dir=upload_dir, now=True)

if __name__ == "__main__":
    main()
