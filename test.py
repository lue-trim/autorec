import asyncio
from cookies_checker import scheduled_refresh

async def __test():
    '测试用'
    await scheduled_refresh()

if __name__ == "__main__":
    asyncio.run(__test())