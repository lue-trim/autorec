import autorec
import getopt, os, sys, toml
from static import config, logger
from tortoise import run_async

def usage():
    '--help'
    print("""手动添加即时上传任务(不支持嵌套目录，如需定时备份功能请使用autobackup.py)
上传结果: /local/dir1/dir2/*.* -> /remote/dir2/*.*
-c/--config <config_file> \t上传服务器配置，默认值settings.toml
-p/--path <pathname> \t要上传的文件所在目录
""")
    quit()

def main():
    # 初始化
    local_dir = ""
    config_file = "settings.toml"

    # 解析参数
    options, args = getopt.getopt(sys.argv[1:], "hf:p:c:", ["help", "path=", "config="])
    for name, value in options:
        if name in ("-h","--help"):
            usage()
        elif name in ("-p", "--path"):
            local_dir = value
        elif name in ("-c", "--config"):
            config_file = value
    
    # 检查参数
    if local_dir == "":
        print("参数不全")
        usage()
    
    # 获取文件名，去除文件夹
    filenames = os.listdir(local_dir)
    last_dir = os.path.split(os.path.split(local_dir)[0])[1]
    for idx, filename in enumerate(filenames):
        if os.path.isdir(os.path.join(local_dir, filename)):
            del filenames[idx]
    
    # 读取配置
    if config_file != "settings.toml":
        config.load(config_file)
    settings_autobackup = config.autobackup

    # 读取备份设置
    for settings_alist in settings_autobackup['servers']:
        dest_dir = settings_alist['remote_dir']
        # 获取token
        session = autorec.AutoRecSession()
        token = run_async(session.get_alist_token(settings_alist))

        # 上传
        total = len(filenames)
        for idx, filename in enumerate(filenames):
            local_filename = os.path.join(local_dir, filename)
            dest_filename = os.path.join(dest_dir, last_dir, filename)
            logger.log("Uploading: {} -> {} ({}/{})".format(local_filename, dest_filename, idx+1, total))
            run_async(session.upload_alist(settings_alist, token, local_filename, dest_filename))
    
if __name__ == "__main__":
    main()
