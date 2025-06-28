import asyncio, traceback, json
from aiohttp import ClientSession, ClientTimeout
from urllib.parse import quote

from alist import get_alist

class Session():
    max_retries = 6

    def __init__(self, max_retries:int=6):
        self.max_retries = max_retries

    async def request(self, **kwargs):
        '发送请求'
        try:
            async with ClientSession(timeout=ClientTimeout(total=None)) as session:
                async with session.request(**kwargs) as res:
                    response = await res.json()
                    assert res.ok
        except Exception:
            print(f"Request Error: {traceback.format_exc()}")
            return {"code":500, "data":None}
        else:
            print(f"Response: {response}")
            return response

    async def get_alist_token(self, settings_alist:dict):
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
        response_json = await self.request(method="post", url=url, data=json.dumps(params), headers=headers)
        # 获取结果
        if response_json['code'] == 200:
            return response_json['data']['token']
        else:
            return ""

    async def upload_alist(self, settings_alist:dict, token:str, filename:str, dest_filename:str):
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
        with open(filename, 'rb') as f:
            response_json = await self.request(method="put", url=url, data=f, headers=headers)
        
        return response_json

async def __test():
    settings = {
        'url_alist': 'http://localhost:5244',
        'username': 'admin',
        'password': '23dd49243007242245815f9a2948b1e3da9f12bd0dc592ea1e85f4a33fb2bf26',
        }
    session = Session()
    token = await session.get_alist_token(settings)

    res = await get_alist(settings, token, "/baidu/叽叽啊")
    print(json.dumps(res))
    return
    # 传到百度
    dest_filename = "/baidu/test/test.txt"
    res = await session.upload_alist(settings, token, "empty.txt", dest_filename)

    # 传到本地
    dest_filename = "/local/test/test.txt"
    res = await session.upload_alist(settings, token, "empty.txt", dest_filename)


if __name__ == "__main__":
    asyncio.run(__test())