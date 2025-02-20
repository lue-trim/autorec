import autorec

def reload_settings(url):
    '重载autorec配置文件'
    import requests, json
    # 请求参数
    headers = {
        "Content-Type": "application/json",
    }

    # 请求API
    response = requests.put(url=url, headers=headers)
    # data = response.json()
    print("重载设置成功", sep='\n')

def add_task(url, local_dir, config_file):
    '添加任务'
    import requests, json
    # 请求参数
    headers = {
        "Content-Type": "application/json",
    }
    data = {
        "local_dir": local_dir,
        "config_toml": config_file
    }

    # 请求API
    response = requests.post(url=url, data=json.dumps(data), headers=headers)
    data = response.json()
    print("添加成功", data['data'], sep='\n')

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
        response = requests.patch(url=url, data=json.dumps(data), headers=headers)
    else:
        response = requests.delete(url=url, data=json.dumps(data), headers=headers)
    data = response.json()
    print("提交成功", data['data'], sep='\n')

def show_task(url):
    '列出任务'
    import requests, json
    # 请求参数
    headers = {
        "Content-Type": "application/json",
    }
    data = {
        "id": 0,
    }

    # 请求API
    response = requests.get(url=url, data=json.dumps(data), headers=headers)
    data = response.json()
    print(data['data'], sep='\n')

def usage():
    '--help'
    print("""定时备份任务管理
-r/--reload \t重载全局autorec配置
-s/--show \t查看任务列表
-a/--add \t新增任务
-t/--retry \t手动重试备份失败的任务
-d/--delete \t删除任务
-p/--path <pathname> \t要备份的目录，新增任务必填
-c/--config <config_file> \t备份使用的服务器配置，新增任务必填，默认值settings.toml
-i/--id <id> 或 --all\t要选中的任务ID，删除/重试任务必填
e.g.:
python autobackup.py --add -c settings.toml -p /home/123
python autobackup.py --reload
python autobackup.py --del --all
python autobackup.py --retry -i 0
""")
    quit()

def main():
    import getopt, os, sys, toml
    # 初始化
    local_dir = ""
    config_file = "settings.toml"
    index = -1
    is_all = False
    is_show = False
    is_add = False
    is_delete = False
    is_reload = False
    is_retry = False

    # 解析参数
    options, args = getopt.getopt(
        sys.argv[1:], 
        "hp:c:i:sadrt", 
        ["help", "path=", "config=", "index=", "all", "show", "add", "delete", "reload", "retry"]
        )
    for name, value in options:
        if name in ("-h","--help"):
            usage()
        # 参数
        elif name in ("-p","--path"):
            local_dir = value
        elif name in ("-c","--config"):
            config_file = value
        elif name in ("-i","--index"):
            index = int(value)
        elif name in ("--all"):
            is_all = True
        # 功能
        elif name in ("-a","--add"):
            is_add = True
        elif name in ("-s","--show"):
            is_show = True
        elif name in ("-d","--delete"):
            is_delete = True
        elif name in ("-r","--reload"):
            is_reload = True
        elif name in ("-t","--retry"):
            is_retry = True

    # 检查参数
    if is_add and (config_file == "" or local_dir == ""):
        print("添加配置任务请指定配置文件和目录")
        usage()
    if (is_delete or is_retry) and (index == "" and not is_all):
        print("请使用-i指定要删除的任务id或使用--all清空列表")
        is_delete = False
        is_show = True

    # 请求地址    
    with open("settings.toml", 'r', encoding='utf-8') as f:
        settings = toml.load(f)
    url = "http://{}:{}/autobackup".format(
        settings['server']['host_server'], 
        settings['server']['port_server'],
        )

    # 切换模式
    if is_reload:
        reload_settings(url)
    if is_show:
        show_task(url)
    elif is_add:
        add_task(url, config_file=config_file, local_dir=local_dir)
    elif is_delete or is_retry:
        del_retry_task(url, index, is_clear_all=is_all, retry=is_retry)

if __name__ == "__main__":
    main()
