import tortoise
from tortoise import Tortoise
from static import config
from urllib.parse import quote
from .models import *

async def init_db():
    '初始化数据库'
    user = quote(config.db['pg_user'])
    passwd = quote(config.db['pg_password'])
    db_host = quote(config.db['pg_host'])
    db_port = config.db['pg_port']
    database = quote(config.db['pg_database'])
    config_db = {
            "connections": {
                "autorec_db": f"postgres://{user}:{passwd}@{db_host}:{db_port}/{database}"
            },
            "apps": {
                "autorec_app": {
                    "models": ["db.models"],
                    "default_connection": "autorec_db",
                }
            },
        }
    await Tortoise.init(config_db)
    await Tortoise.generate_schemas(safe=True)

async def close():
    '关闭数据库连接'
    await tortoise.connections.close_all(discard=False)
