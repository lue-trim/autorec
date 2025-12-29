import json, asyncio, traceback

import bilibili_api as bili
from bilibili_api import login_v2, request_settings
from bilibili_api.login_v2 import QrCodeLoginEvents
from bilibili_api.utils.network import get_buvid, get_bili_ticket

from loguru import logger

from static import config
from blrec import check_blrec_cookies, set_blrec


def cookie_dict2str(data:dict):
    'cookie_dict转换为字符串'
    s = ''
    for i in data.keys():
        s += "{}={};".format(i, data[i])
    return s

def load_credential():
    '从json导入credential'
    with open("credential.json", 'r') as f:
        credential_dict = json.load(f)
    credential = bili.Credential.from_cookies(credential_dict)
    return credential, credential_dict

def dump_credential(credential:bili.Credential):
    '导出credential到json'
    credential_dict = credential.get_cookies()
    with open("credential.json", 'w') as f:
        json.dump(credential_dict, f)

async def login(is_tv=False):
    '登录账号'
    if is_tv:
        qr = login_v2.QrCodeLogin(platform=login_v2.QrCodeLoginChannel.TV)
    else:
        # 生成二维码登录实例，平台选择网页端
        qr = login_v2.QrCodeLogin(platform=login_v2.QrCodeLoginChannel.WEB) 

    # 生成二维码
    await qr.generate_qrcode()

    # 检查状态
    while not qr.has_done():
        print(qr.get_qrcode_terminal())
        while (await qr.check_state()) != QrCodeLoginEvents.TIMEOUT:                                            # 在完成扫描前轮询
            # print(bili.sync(qr.check_state())) 
            # 轮询间隔建议 >=1s
            await asyncio.sleep(2)

    # 建立credential
    credential = qr.get_credential()
    #credential = bili.login.login_with_qrcode_term()

    # 检查有效性
    if not (await credential.check_valid()):
        ans = input("\nWarning: this account maybe invalid, continue?(y/N)")
        if ans.lower() != 'y':
            return
    logger.info("Login complete, syncing to blrec...")

    # 保存并同步
    await sync_cookies(credential=credential)

async def refresh_cookies(is_forced=False, silent=False):
    '刷新cookies'
    # 加载cookies
    credential, cookies_dict = load_credential()
    cookies = cookie_dict2str(cookies_dict)
    
    # 检查是否需要更新
    if not is_forced:
        msg = "Checking cookies..."
        logger.info(msg)
        # print(msg)

        # 读取cookies状态
        res = await check_blrec_cookies(cookies)
        if not res['data']['isLogin']:
            msg = "Cookies expired, refreshing..."
            logger.info(msg)
            # print(msg)
        elif silent:
            return
        else:
            ans = input("Cookies not expired, proceed refreshing?(y/N): ")
            if ans.lower() != 'y':
                return
    
    # 刷新
    await credential.refresh()

    # 保存并同步
    await sync_cookies(credential=credential)

async def sync_cookies(credential:bili.Credential|None=bili.Credential()):
    '保存cookies并同步到blrec'
    if not credential:
        credential, credential_dict = load_credential()
    else:
        if not credential.has_buvid3() or not credential.has_buvid4():
            credential.buvid3, credential.buvid4 = await get_buvid()
        dump_credential(credential)
        credential_dict = credential.get_cookies()
    bili_tickets = await try_bili_ticket(credential)
    if bili_tickets:
        credential_dict.update(bili_tickets)
    new_cookies = cookie_dict2str(credential_dict)[:-1] # 去除最后的分号

    # 更新blrec的cookies
    new_data = {"header": {"cookie": new_cookies}}
    await set_blrec(new_data)

    # print(new_cookies)
    logger.info(f"New cookies: {new_cookies}")
    print("Cookies sync complete.")

async def try_bili_ticket(credential:bili.Credential):
    '尝试获取bili_ticket'
    try:
        bili_ticket, bili_ticket_expires = await get_bili_ticket(credential)
    except Exception:
        msg = f"Warning: \nFailed to get bili_ticket: {traceback.format_exc()}"
        logger.warning(msg)
        print(msg)
        return {}
    else:
        return {
            'bili_ticket': bili_ticket, 
            'bili_ticket_expires': bili_ticket_expires
            }
