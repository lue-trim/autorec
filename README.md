# autorec
一个利用blrec的webhook和alist的API实现录播完成后自动把文件上传到服务器并删除本地文件、自动更新cookies操作的server
理论上稍微改改，也能用在命令行版录播姬上

# 基于项目
- [acgnhiki / blrec](https://github.com/acgnhiki/blrec)；
- [SocialSisterYi / bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect)；
- [alist-org / docs](https://github.com/alist-org/docs)

# 使用方法
## conda环境
参考另一个项目[bili_login的环境](https://github.com/lue-trim/bilibiliLogin/blob/main/bili_login.yaml)
## 配置文件
- `settings.toml`中设置blrec的主机与端口号
- `settings.toml`中设置alist的主机、端口号、用户名、加密后的密码（获取方法[在这](https://alist-v3.apifox.cn/api-128101242)）
## blrec设置
- 在blrec的Webhook设置中添加autorec的url(默认是`http://localhost:23560`)
- 至少勾选`VideoPostprocessingCompletedEvent`（自动上传视频和弹幕）和`RecordingFinishedEvent`（自动更新cookies）
## 修改并运行
- 要上传的本地文件路径和上传到服务器的目标路径写死在autorec.py的upload_video方法里，有需要自己改
- `python autorec.py`
