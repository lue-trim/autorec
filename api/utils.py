from functools import reduce
import datetime, re

def parse_macro(s: str, data: dict):
    '将配置文件含宏部分解析成对应字符串'
    parsed_s = s
    # 匹配
    re_res = re.findall(r'{[^}]*/[^}]*}', s)
    if not re_res:
        return parsed_s
    
    #print(re_res.groups())
    # 解析
    for match_res in re_res:
        split_list = match_res[1:-1].split('/')
        #print(split_list)
        
        if split_list[0] == 'time':
            # 时间解析
            time_now = datetime.datetime.now()
            replaced_s = time_now.strftime(split_list[1])
        else:
            # 字典解析
            replaced_s = str(reduce(lambda x,y:x[y], split_list, data))
        
        # 替换
        parsed_s = re.sub(match_res, replaced_s, parsed_s)
    
    return parsed_s