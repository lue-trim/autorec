# autorec
一个利用blrec的webhook和alist的API，实现录播完成后自动把文件上传到服务器并删除本地文件、每日自动备份文件到其他存储、自动更新cookies操作的脚本  
理论上稍微改改API，也能用在命令行版录播姬上  
> PS: openlist之类的社区版alist也能用
## 基于项目
- [acgnhiki/blrec](https://github.com/acgnhiki/blrec)；
- [nemo2011/bilibili-api](https://github.com/nemo2011/bilibili-api)；
- [alist-org/docs](https://github.com/alist-org/docs)

# 环境
## Postgres
最简单的办法是直接通过官方Docker镜像部署，版本随意，如果已经有了就不用再装一个
1. 下载  
    ```bash
    docker pull postgres:latest
    ```
1. 运行  
    可以参考以下配置
    ```bash
    docker run -d \
    -e POSTGRES_PASSWORD=<数据库密码> \ # 自己取
    -e POSTGRES_HOST_AUTH_METHOD=trust \
    -v <路径>:/var/lib/postgresql/data \ # 存放数据库用的，最好是空文件夹
    -p <端口号>:5432 \ # 映射到本地的端口号，随便取，注意要和后端的设置对应上
    --restart unless-stopped \ # 崩溃时自动重启
    --name postgres \ # 容器名称，可以随便设置
    postgres:latest
    ```
1. 不出意外的话只要让它一直运行就可以了
## Python 3.10
按理来说直接使用[Haruka-Bot](https://github.com/lue-trim/haruka-bot)的环境应该就可以  
如果不要haruka-bot的话可以把它去掉
```
aiohttp==3.8.6
aiosignal==1.3.2
aiosqlite==0.21.0
anyio==4.9.0
APScheduler==3.11.0
async-timeout==4.0.3
asyncpg==0.28.0
attrs==25.3.0
aunly-captcha-solver==0.1.3
beautifulsoup4==4.13.4
bilibili-api-python==17.1.4
bilireq==0.2.13
Brotli==1.1.0
certifi==2025.4.26
chardet==4.0.0
charset-normalizer==3.4.1
click==8.1.8
colorama==0.4.6
exceptiongroup==1.2.2
fastapi==0.115.12
frozenlist==1.6.0
greenlet==3.2.1
grpcio==1.71.0
h11==0.16.0
haruka-bot @ file:///home/admin/Apps/haruka-bot
httpcore==1.0.9
httptools==0.6.4
httpx==0.27.2
idna==3.10
iso8601==2.1.0
loguru==0.7.3
lxml==5.3.2
msgpack==1.1.0
multidict==6.4.3
nest-asyncio==1.5.9
nonebot-adapter-onebot==2.4.6
nonebot-plugin-apscheduler==0.5.0
nonebot-plugin-guild-patch==0.2.3
nonebot2==2.4.2
packaging==25.0
pillow==11.1.0
playwright==1.51.0
propcache==0.3.1
protobuf==6.30.2
pycryptodome==3.22.0
pycryptodomex==3.21.0
pydantic==1.10.22
pyee==12.1.1
pygtrie==2.5.0
PyJWT==2.10.1
pypika-tortoise==0.5.0
python-dotenv==1.1.0
pytz==2025.2
PyYAML==6.0.2
qrcode==8.1
qrcode-terminal==0.8
requests==2.32.3
sniffio==1.3.1
soupsieve==2.7
starlette==0.46.2
tomli==2.2.1
tortoise-orm==0.25.0
typing_extensions==4.13.2
tzlocal==5.3.1
urllib3==1.26.20
uvicorn==0.34.2
uvloop==0.21.0
watchfiles==1.0.5
websockets==15.0.1
yarl==1.18.3
```
## 环境安装示例
1. 保存如上部分为`requirement.txt`(记得修改haruka-bot的路径或者干脆把这行删掉)
1. 通过pip安装
```bash
pip install -r requirement.txt
```

# 功能说明
## 运行方法与初次设置
- 直接在终端运行`python server.py`，或者自己写一个`autorec.service`添加到systemctl都可以，能跑起来就行

- 第一次运行的时候会生成配置模板`settings.toml`并退出，需要根据实际运行环境自行修改参数

### `db`模块
运行前需要设置postgres数据库的地址、账号等信息并手动创建数据库  
示例：假设用户名为postgres，docker容器名为pg_container，`settings.toml`中设置的数据库名称为autorec_db
- docker: 
  ```bash
  docker exec -it pg_container psql -U postgres
  CREATE DATABASE autorec_db;
  \q
  ```
- 原生:
  ```bash
  psql -U postgres
  CREATE DATABASE autorec_db;
  \q
  ```
### 其他模块
直接参考生成的默认配置文件里的说明就行

## `client.py`使用说明
### 基本使用
- 使用`-h/--help`参数获取帮助，`--config 配置文件名称`临时加载配置，`--reload 配置文件名称`更新全局配置，`--version 包名`获取运行中的包版本信息

示例：
```bash
python client.py --help
python client.py --reload config2.toml
python client.py --version bilibili-api-python
```
### cookies模块
用于管理供blrec、HarukaBot等其他项目使用的cookies，完整帮助参见`python client.py cookies --help`
1. 第一次使用需运行`python client.py cookies -l`扫码登录
2. 在`settings.toml`中，如果配置了`cookies.check_interval`，则会自动根据时间间隔检测cookies是否有效，要是失效了会自动更新  
  > 也可以`python client.py cookies -c`手动检查一下cookies有没有过期，如果检查发现过期会自动更新  
  > 当然还可以通过`python client.py cookies -cf`强制刷新
3. 一般来说登录或刷新后会自动把获取到的cookies同步到blrec，如果同步失败，可以尝试`python client.py cookies -s`重新同步
  > 若Cookies更新提示correspondPath获取失败，请先同步本地时间后再试
### 自动备份模块
- 管理每日自动备份任务
- 完整帮助参见`python client.py backup --help`
#### 每日自动备份
用于在每天指定时段向特定alist存储备份刚刚录制好的文件（但是不能使用立即上传功能的路径模板）  
要完全关闭该功能，把server项给置空就可以  
- 在`settings.toml`中对应的位置设置alist的主机、端口号、用户名、加密后的密码（获取方法[在这](https://alist-v3.apifox.cn/api-128101242)）
- 在`settings.toml`\[autobackup\]模块中的`interval`项设置时间检查间隔（区间越短CPU占用越大）
- 按照与\[alist\]模块相同的格式，把要添加到的存储添加到`autobackup.servers`列表，可以同时备份到多个存储  
（参见第一次运行时生成的配置模板）  
（除了不能用路径模板以外，其他内容都和\[alist\]里一样）  
- 对于每个`autobackup.servers`项，都需要设置一个预定上传时间  
（格式是`"%H:%M:%S"`）
- 每个存储可以和\[alist\]模块一样通过设置`enabled`项控制开关
- **注意**：如果要备份到多个存储，并且上传后自动删除文件，记得把`remove_after_upload=true`放在**最后一个**存储下
#### 手动补录/取消备份
直接举例子吧：  
手动加载配置文件并添加备份任务：`python client.py backup -a /local/records -c upload_config.toml`  
看看当前任务和历史记录：`python client.py backup -s`  
删掉最早的自动备份任务：`python client.py backup -d 0`  
立即上传：`python client.py backup -u /local/records/1/`  


## 录制完成立即上传功能
- 使用预设的路径模板，在视频完成录制后自动上传到指定alist存储
- 可以通过设置\[alist\]模块的`enabled`字段控制自动上传功能开启/关闭  
- 如果不需要立即上传并且用不到路径模板，那么更推荐直接使用上文的**自动备份模块**
### 使用配置
#### blrec
1. 在blrec的Webhook设置中添加autorec的url(默认是`http://localhost:23560`)
1. 至少勾选`VideoPostprocessingCompletedEvent`（自动上传视频和弹幕）和`RecordingFinishedEvent`（自动更新cookies）
1. 在`settings.toml`\[blrec\]模块中设置blrec的主机与端口号
#### autorec
- 各项参数的具体用法可以参考第一次运行时生成的配置模板
- **注意**：如果要设置每日自动备份，记得把`remove_after_upload`给设成`false`
##### 上传路径模板说明 
模板示例：`{room_info/room_id}_{user_info/name}/{time/%y%m%d}_{room_info/title}`

自动填充模板格式详情：  
- `time`开头:  
上传前立即获取的时间信息，`/`后接python的时间格式化字符串  
- `room_info`/`user_info`/`task_status`开头:  
从blrec处获取的录制信息，`/`后接具体的属性名称

举例: 从blrec获取的录制信息如下:   
（可以通过向blrec的`/api/v1/tasks/{room_id}/data`发送get请求获取）
```json
{
  "user_info": { 
    "name": "早稻叽", 
    "gender": "女", 
    "face": "https://i1.hdslb.com/bfs/face/***.jpg", 
    "uid": 1950658, 
    "level": 6, 
    "sign": "<ChaosLive>励志给人类带来幸福的光之恶魔✨商务合作请戳1767160966（不看私信，谢）" 
  },
  "room_info": {
    "uid": 1950658,
    "room_id": 41682,
    "short_room_id": 631,
    "area_id": 745,
    "area_name": "虚拟Gamer",
    "parent_area_id": 9,
    "parent_area_name": "虚拟主播",
    "live_status": 2,
    "live_start_time": 0,
    "online": 0,
    "title": "晚上不好",
    "cover": "https://i0.hdslb.com/bfs/live/new_room_cover/***.jpg",
    "tags": "VTUBER,VUP,虚拟主播,歌姬,早稻叽,虚拟UP主",
    "description": "诞生于粉丝满满心意的全新3D虚拟星球正在开幕中！5位重磅UP首批强势入驻！@泠鸢yousa@兰音reine@C酱です@AIChannel中国绊爱@早稻叽（排名不分先后）\n锁定直播间，来和心爱的主播贴贴、坐摩天轮吧~观看直播，还有机会赢取苹果14手机、100元现金红包哟~观看有礼一键传送https://www.bilibili.com/blackboard/live/activity-eWPyQBs0W6.html"
  },
  "task_status": {
    "monitor_enabled": true,
    "recorder_enabled": true,
    "running_status": "waiting",
    "stream_url": "https://d1--ov-gotcha05.bilivideo.com/***",
    "stream_host": "d1--ov-gotcha05.bilivideo.com",
    "dl_total": 5632504232,
    "dl_rate": 475005.92442482925,
    "rec_elapsed": 10838.652142584091,
    "rec_total": 5627981824,
    "rec_rate": 474669.98430827376,
    "danmu_total": 0,
    "danmu_rate": 0,
    "real_stream_format": null,
    "real_quality_number": null,
    "recording_path": "",
    "postprocessor_status": "waiting",
    "postprocessing_path": null,
    "postprocessing_progress": null
  }
}
```
