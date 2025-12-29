from aiohttp import ClientSession, ClientTimeout

from static import logger, Config
from cookies_checker.utils import login, refresh_cookies, sync_cookies

import argparse, asyncio, json

async def request(**kwargs):
    '向服务端发送'
    headers = {
            'Content-Type': 'application/json'
    }

    # 发起请求
    async with ClientSession(timeout=ClientTimeout(None)) as session:
        async with session.request(headers=headers, **kwargs) as req:
            # content = await req.text()
            # print(content)
            logger.debug(f"Sending request: {req.url}")
            res = await req.json(content_type=None)
            if not req.ok:
                logger.error(f"Server Error: {res}")
            else:
                logger.debug(f"Request success: {res}")

    return res

async def add_task(url, local_dir, config_file, now=False):
    '添加任务'
    url = f"{url}/autobackup"
    data = {
        "local_dir": local_dir,
        "config_toml": config_file,
        "now": str(now),
    }

    # 请求API
    data = await request(method="post", url=url, params=data)
    logger.info("Autobackup task created.")
    # logger.info(data)
    print(data['data'])

async def dump_load_reload(url, filename, mode="dump"):
    '导出/导入任务列表或重载配置'
    # 请求参数
    params = {
        'filename': filename
    }

    # API分流
    if mode == "dump":
        url = f"{url}/autobackup/dump"
        data = await request(method="post", url=url, params=params)
        logger.info(f"Dumped tasks to {filename}.")
    elif mode == "load":
        url = f"{url}/autobackup/load"
        data = await request(method="post", url=url, params=params)
        logger.info(f"Loaded tasks from {filename}.")
    elif mode == "reload":
        url = f"{url}/settings/reload"
        data = await request(method="post", url=url, params=params)
        logger.info(f"Reloaded {filename}.")
    else:
        return
    print(data['data'])


async def show_del_retry(url, index:int|None=-1, mode="show", is_all=False):
    '获取列表、删除或重试任务'
    # 请求参数
    params = {
        "id": index,
        "all": str(is_all),
    }

    # 请求API
    if mode == "retry":
        data = await request(method="post", url=f"{url}/autobackup/retry", params=params)
        logger.info(f"Retried task {index}.")
    elif mode == "delete":
        data = await request(method="delete", url=f"{url}/autobackup", params=params)
        logger.info(f"Deleted task {index}.")
    elif mode == "show":
        data = await request(method="get", url=f"{url}/autobackup")
        logger.info(f"Fetched tasks.")
    else:
        return
    print(data['data'])


async def __handle_cookies(args):
    if args.login:
        await login(args.tv)
    elif args.check:
        await refresh_cookies(args.forced)
    elif args.sync:
        await sync_cookies(credential=None)

async def __handle_backup(args):
    config_file = args.config if args.config else "settings.toml"
    config = Config(config_file)
    url = f"http://{config.app['host_server']}:{config.app['port_server']}"

    if args.show:
        await show_del_retry(url, mode="show")
    elif args.add != "":
        await add_task(url, config_file=config_file, local_dir=args.add)
    elif args.dump != "":
        await dump_load_reload(url, filename=args.dump, mode="dump")
    elif args.load != "":
        await dump_load_reload(url, filename=args.load, mode="load")
    elif args.delete != "":
        if args.delete == "all":
            await show_del_retry(url, -1, is_all=True, mode="delete")
        else:
            await show_del_retry(url, int(args.delete), is_all=False, mode="delete")
    elif args.retry != "":
        if args.retry == "all":
            await show_del_retry(url, -1, is_all=True, mode="retry")
        else:
            await show_del_retry(url, int(args.retry), is_all=False, mode="retry")
    elif args.upload  != "":
        await add_task(url, config_file=config_file, local_dir=args.upload, now=True)

async def __handle_config(args):
    if args.reload:
        config = Config(args.reload)
        url = f"http://{config.app['host_server']}:{config.app['port_server']}"
        await dump_load_reload(url, args.reload, mode="reload")
    elif args.version:
        config = Config(args.config)
        url = f"http://{config.app['host_server']}:{config.app['port_server']}/version"
        data = await request(method="get", url=url, params={'package': args.version})
        if data['code'] == 200:
            ver_dict = data['data']
            logger.info(f"{ver_dict['name']}: {ver_dict['version']}")
        else:
            logger.error(f"Get version for {args.version} failed: \n{data['data']}")

def main():
    'main'
    # 解析参数
    p = argparse.ArgumentParser()
    p.add_argument("--config", help="载入临时配置文件", default="settings.toml")
    p.add_argument("--reload", help="重新载入全局配置")
    p.add_argument("--version", help="查看运行中的包版本")
    p.set_defaults(func=lambda x:asyncio.run(__handle_config(x)))

    sp = p.add_subparsers(title="subcommand")

    p_cookies = sp.add_parser("cookies", help="Cookies相关")
    p_cookies.add_argument("-l", "--login", help="登录账号并记录cookies", action="store_true", default=False)
    p_cookies.add_argument("-t", "--tv", help="是否使用TV端登录, False则使用默认的Web端", action="store_true", default=False)
    p_cookies.add_argument("-c", "--check", help="检查cookies", action="store_true", default=False)
    p_cookies.add_argument("-f", "--forced", help="是否强制刷新", action="store_true", default=False)
    p_cookies.add_argument("-s", "--sync", help="把cookies同步到blrec", action="store_true", default=False)
    p_cookies.set_defaults(func=lambda x:asyncio.run(__handle_cookies(x)))

    p_autobackup = sp.add_parser("backup", help="自动备份任务相关")
    p_autobackup.add_argument("-s", "--show", help="显示所有任务", action="store_true", default=False)
    p_autobackup.add_argument("-a", "--add", help="将指定文件夹添加为备份任务", default="")
    p_autobackup.add_argument("-j", "--dump", help="将当前所有备份任务导出为json", default="")
    p_autobackup.add_argument("-l", "--load", help="从文件中载入备份任务(保留现有)", default="")
    p_autobackup.add_argument("-u", "--upload", help="立即上传指定文件夹", default="")
    p_autobackup.add_argument("-t", "--retry", help="重试指定任务(可以是all)", default="")
    p_autobackup.add_argument("-d", "--delete", help="删除指定备份任务(可以是all)", default="")
    p_autobackup.set_defaults(func=lambda x:asyncio.run(__handle_backup(x)))

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
