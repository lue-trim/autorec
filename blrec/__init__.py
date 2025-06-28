import asyncio, traceback, json, os

from aiohttp import ClientSession, ClientError, ClientTimeout
from urllib.parse import quote

from static import config, logger

async def send_request(timeout=20, **kwargs):
    '发送请求'
    async with ClientSession(timeout=ClientTimeout(total=timeout)) as session:
        async with session.request(**kwargs) as res:
            response = await res.json()
            if not res.ok:
                logger.error(f"Sending to blrec error: \n{response}")
                return {}
            else:
                return response

async def set_blrec(data: dict):
    '更改blrec设置'
    url = f"{config.blrec['url_blrec']}/api/v1/settings"
    # body = utils.dict2str(data)
    body = data

    # 请求API
    resp = await send_request(timeout=20, method="PATCH", url=url, json=body)
    assert resp

async def get_blrec_data(room_id=-1, page=1, size=100, select="all"):
    '获取blrec信息'
    params = {
        "select": select,
        "size": size,
        "page": page,
        }
    if room_id != -1:
        url = f"{config.blrec['url_blrec']}/api/v1/tasks/{room_id}/data"
    else:
        url = f"{config.blrec['url_blrec']}/api/v1/tasks/data"
    response_json = await send_request(method="GET", url=url, params=params)

    return response_json

async def check_blrec_cookies(cookies:str):
    '通过blrec的API检查cookies'
    # logger.info(cookies)
    body = {
        'cookie': cookies
    }
    url = f"{config.blrec['url_blrec']}/api/v1/validation/cookie"
    response_json = await send_request(method="POST", url=url, json=body)
    return response_json

