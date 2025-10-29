import asyncio, traceback, json, os

from aiohttp import ClientSession, ClientError, ClientTimeout
from urllib.parse import quote

from static import config, logger
from .utils import parse_macro

async def __request(**kwargs):
    async with ClientSession(timeout=ClientTimeout(total=None)) as session:
        async with session.request(**kwargs) as res:
            response = await res.json()
            # 如果alist报错找不到文件，返回码改成200
            if "object not found" in response.get('message', ''):
                response.update({'code': 200})
                return response
            # 其他情况只要OK就可以返回
            assert res.ok
            return response

async def request(filename="", max_retries=0, **kwargs):
    '发送请求'
    if max_retries <= 0:
        max_retries = config.app.get('max_retries', 6)

    # 自动重试
    for i in range(max_retries):
        sleep_sec = min(4**(i-1), 600)
        logger.info(f"({i+1}/{max_retries}) Requesting after {sleep_sec} seconds: {kwargs['url']}")
        await asyncio.sleep(sleep_sec)
        try:
            if filename:
                if os.path.getsize(filename) == 0:
                    logger.warning(f"Skipping empty file {filename}..")
                    return {'code': 200, 'data': None}
                else:
                    logger.debug(f"Loading file {filename}")
                    with open(filename, "rb") as f:
                        response = await __request(data=f, **kwargs)
            else:
                response = await __request(**kwargs)
        except AssertionError:
            logger.warning(f"Response Error: {response}, retrying...")
        except ClientError as e:
            logger.warning(f"Request Error, retrying: {e}")
        except TimeoutError:
            logger.warning("Request time out, retrying...")
        except Exception:
            logger.warning(f"Unknown Error, retrying: {traceback.format_exc()}")
        else:
            # return json.loads(response)
            # logger.debug(response)
            if response.get("code", 200) == 200:
                return response
            else:
                logger.warning(f"Response Error, retrying: {response}")
    else:
        logger.error("All requests failed.")
        return {'code': 500, 'data': None}

async def get_alist_token(settings_alist:dict):
    '获取alist管理token'
    url = f"{settings_alist['url_alist']}/api/auth/login/hash"
    params = {
        "username": settings_alist['username'],
        "password": settings_alist['password'].lower()
    }
    headers = {
        'Content-Type': 'application/json'
    }

    # 请求API
    response_json = await request(
        method="post",
        url=url, 
        data=json.dumps(params), 
        headers=headers
        )
    # 获取结果
    if response_json['code'] == 200:
        return response_json['data']['token']
    else:
        return ""

async def get_alist(settings_alist:dict, token:str, path:str):
    '获取文件信息'
    url = f"{settings_alist['url_alist']}/api/fs/get"
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }
    data = {
        "path": path,
    }

    # 获取请求结果
    res = await request(
        # max_retries=1,
        method="post", 
        url=url, 
        data=json.dumps(data), 
        headers=headers
        )

    if res['code'] == 200:
        return res['data']
    else:
        logger.error(f"Unknown error when getting path {path}")
        return {}

async def copy_alist(settings_alist:dict, token:str, source_dir:str, filenames:list, dist_dir:str):
    '复制文件'
    # 请求参数
    url = f"{settings_alist['url_alist']}/api/fs/copy"
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
    data = await request(
        method="post",
        url=url, 
        data=json.dumps(data), 
        headers=headers
        )

    # 获取结果
    if data['code'] == 200:
        logger.info("Copy success.")
    else:
        logger.error("Copy failed,", data['message'])
    
    return data['code']

async def rm_alist(settings_alist:dict, token:str, dirname:str, filenames:list):
    '删除文件'
    # 请求参数
    url = f"{settings_alist['url_alist']}/api/fs/remove"
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }
    data = {
        "dir": dirname,
        "names": filenames
    }

    # 请求API
    data = await request(
        method="post",
        url=url, 
        data=json.dumps(data), 
        headers=headers
        )

    # 获取结果
    if data['code'] == 200:
        logger.info("Remove success:", dirname, filenames)
    else:
        logger.error("Remove failed:", dirname, filenames, data['message'])
    
    return data['code']

async def upload_alist(settings_alist:dict, token:str, filename:str, dest_filename:str):
    '流式上传文件'
    dest_filename = quote(dest_filename) # URL编码

    # 请求参数
    url = f"{settings_alist['url_alist']}/api/fs/put"
    headers = {
        "Authorization": token,
        "File-Path": dest_filename,
        "As-Task": "True",
        "Content-Type": "application/octet-stream",
    }

    # 打开文件
    response_json = await request(
        filename=filename, 
        method="put", 
        url=url, 
        headers=headers
        )
    # 不能在这一步加载文件，否则会出现重试时无法载入已关闭文件描述符的bug

    if response_json['code'] == 200:
        logger.info(f"Upload success: {filename}")
        # 是否在上传后删除文件
        if settings_alist['remove_after_upload']:
            os.remove(filename)
        return True
    else:
        logger.error("{} Upload failed: {}".format(filename, response_json))
        return False


### Frequently Used Methods
async def upload_video(video_filename:str, settings_alist:dict={}, rec_info:dict={}):
    '上传视频'
    # 判断一下有没有开启自动上传功能
    if not settings_alist['enabled']:
        return

    # 获取token
    token = await get_alist_token(settings_alist)

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
            dist_dir = parse_macro(settings_alist['remote_dir'], rec_info)
            dest_filename = os.path.join(dist_dir, os.path.split(local_filename)[1])
            # 检测文件是否已在远程目录存在
            if await get_alist(
                token=token, 
                path=dest_filename, 
                settings_alist=settings_alist
                ) is not None:
                logger.warning(f"Remote file {dest_filename} exists, skipping...")
                continue
        else:
            dest_filename = settings_alist['remote_dir']

        # [本地文件名, 远程文件名]
        filenames.append([local_filename, dest_filename])
    

    # 上传文件
    loop = asyncio.get_event_loop()
    tasks = []
    for i in filenames:
        local_filename = i[0]
        dest_filename = i[1]
        tasks.append(upload_alist(settings_alist, token, local_filename, dest_filename))
    wait_coro = asyncio.wait(tasks)
    loop.run_until_complete(wait_coro)
    loop.close()

