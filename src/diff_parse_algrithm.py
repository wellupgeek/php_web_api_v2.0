from copy import deepcopy
import json

# 获取diff信息中每个'@@'段的行号
def get_line_numbers(msg):
    token = msg.split(" ")
    numbers_old_file = token[1]
    delete_line_number = int(numbers_old_file.split(",")[0].replace("-", ""))
    return delete_line_number

# 合并两个字典
def Merge(dict1, dict2): 
    res = {**dict1, **dict2} 
    return res 

# 主要算法
def diff_parsed(diff, source_code):
    diff_msg = diff.split("\n") # 将str->list
    code_list, temp = [], []
    # 第一步，先把所有的'@@'找到，并提取信息，当前行和真实记录行
    if r"\ No newline at end of file" in diff_msg:
        diff_msg.remove(r"\ No newline at end of file")
    for i, msg in enumerate(diff_msg):
        if msg.startswith("@@"):
            line = get_line_numbers(msg)
            temp_dict = {}
            temp_dict["i"] = i          # 当前diff_msg中的位置，最小从0开始
            temp_dict["line"] = line    # 在原代码中的真实位置
            temp.append(temp_dict)
    # 第二步，根据temp中记录的内容，存入变更代码段
    for index in range(len(temp) - 1):
        start_line, end_line = temp[index]["i"] + 1, temp[index + 1]["i"]   # 这里是@@的起始终止（到下一个@@之前）
        temp[index]["content"] = diff_msg[start_line:end_line]
    temp[-1]["content"] = diff_msg[temp[-1]["i"] + 1:]
    # 第三步，根据每个temp中的内容进行处理
    pre_common = 1  # 这是为了记录common设计的
    for t in temp:
        change_start_line, change_end_line = 0, 0
        for i, code in enumerate(t["content"]):   # 先找开头非common和结尾非common的
            if code.startswith("-") or code.startswith("+"):    # 记录行号
                # common 为 [pre_common:line + i] 行号方面为：pre_common ~ line + i - 1
                save_dict = {}
                save_dict["ab"] = [source_code[x] for x in range(pre_common, t["line"] + i)] if len(source_code) > 0 else ""    # 这里需要判断一下，是否为空
                pre_common = t["line"] + i
                if len(save_dict["ab"]) > 0:
                    code_list.append(save_dict)
                change_start_line = i
                break
        for i in range(len(t["content"])-1, -1, -1):
            if t["content"][i].startswith("-") or t["content"][i].startswith("+"):
                change_end_line = i + 1
                break
        # 集中处理(-/+)~(-/+)中间段 
        change_cont = t["content"][change_start_line:change_end_line]
        temp_code_list, temp_list = [], []
        pre_type, count_num = "", 0
        for c in change_cont:
            if len(c) == 0:     # 某些以空行开头的，算成common
                count_num += 1
            else:
                if pre_type == "":
                    pre_type = c[0]
                    temp_list.append(c[1:])
                    if pre_type != "+":
                        count_num += 1
                else:
                    if c[0] == pre_type:    # 和之前的相同
                        temp_list.append(c[1:])
                        if pre_type != "+":
                            count_num += 1
                    else:   # 分情况
                        now_flag, t_dict = "", {}
                        if pre_type == '-':
                            pre_type = "+" if c[0] == "+" else " "
                            if pre_type == "+":
                                pre_common += count_num
                                count_num = 0
                            else:
                                count_num += 1
                            now_flag = "a"
                        elif pre_type == '+':   # add
                            pre_type = ' '
                            count_num += 1
                            now_flag = "b"
                        else:   # pre_type == ' '
                            pre_type = "-" if c[0] == '-' else '+'
                            if pre_type == "-":
                                count_num += 1
                            else:
                                pre_common += count_num
                                count_num = 0
                            now_flag = "ab"
                        t_dict[now_flag] = deepcopy(temp_list)
                        temp_code_list.append(t_dict)
                        temp_list.clear()
                        temp_list.append(c[1:])
        if len(temp_list) > 0:
            now_flag, t_dict = "", {}
            if pre_type == '-':
                now_flag = "a"
                if count_num > 0:
                    pre_common += count_num
            elif pre_type == '+':   # add
                now_flag = "b"
            else:   # pre_type == ' '
                now_flag = "ab"
                if count_num > 0:
                    pre_common += count_num
            t_dict[now_flag] = deepcopy(temp_list)
            temp_code_list.append(t_dict)
        
        # 对于now_flag a 和 b相连
        deal_temp_list, num = [], 0
        while num < len(temp_code_list):
            if "a" in temp_code_list[num].keys():
                if num + 1 < len(temp_code_list) and "b" in temp_code_list[num + 1].keys():
                    merge_dict = Merge(temp_code_list[num], temp_code_list[num + 1])
                    deal_temp_list.append(merge_dict)
                    num += 2
                    continue
            deal_temp_list.append(temp_code_list[num])
            num += 1
        code_list += deal_temp_list
    
    if pre_common <= len(source_code):
        save_dict = {}
        save_dict["ab"] = [source_code[x] for x in range(pre_common, len(source_code) + 1)] if len(source_code) > 0 else ""
        if len(save_dict["ab"]) > 0:
            code_list.append(save_dict)
    
    return code_list

def get_diff_parsed(diff_msg, temp_code):
    source_code = {k + 1 : v for k, v in enumerate(temp_code)}
    save_list = diff_parsed(diff_msg, source_code)
    return save_list