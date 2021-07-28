# 1. 判断代码内部是否有api接口，获取api接口标志，有下一步，没有判断外部
# 2. 判断代码外部是否有api接口，获取api接口标志，有下一步，没有跳过
# 3. 有api接口的前提下，通过对应的api接口标志遍历api接口代码结构，判断变更代码是否是属于api接口的，只针对代码内部无api接口的
# 4. 然后开始遍历是否有注释信息，通过往api接口标志上找固定范围来判断，找到了即可直接保存
# 5. 如果找不到，则自行生成
# 6. 最后统一保存

import re

def is_api_code(regex, cont, pre_cont, save_dict, code_status, code_line):
    flag, api_flag, record = is_api_incode(regex, cont)
    if flag: # 在里面
        save_msg(save_dict, code_status, code_line, code_line + record)
        is_api_code_util(api_flag, pre_cont+cont[:record], cont[record:], save_dict)
        return True
    else:
        flag2, api_flag2, record2 = is_api_outcode(regex, pre_cont)
        if flag2:
            save_msg(save_dict, code_status, code_line, code_line - record2)
            is_api_code_util(api_flag2, pre_cont[:record2], pre_cont[record2:] + cont, save_dict)
            return True
    return False

def save_msg(save_dict, code_status, code_line, api_code_line):
    save_dict["status"] = code_status
    save_dict["code_line"] = code_line
    save_dict["api_code_line"] = api_code_line

def is_api_code_util(api_flag, cont_one, cont_two, save_dict):
    msg_flag, ans = has_api_msg(cont_one)
    if not msg_flag:
        ans = produce_api_msg(api_flag, cont_two)
    save_dict["origin"] = "Create" if not msg_flag else "Find"
    save_dict["message"] = ans

def is_api_incode(regex, cont):    # in 和 out 的判断代码是一致的，可以统一调用
    flag, api_flag, record, r_end = has_api_flag(regex, cont)
    return flag, api_flag, record

def is_api_outcode(regex, pre_cont):   # 多了一步判断代码结构
    length = len(pre_cont)
    start = 0 if length <= 300 else length - 300
    copy_cont = pre_cont[start: length + 1]
    copy_cont.reverse()
    flag, api_flag, record, r_end = has_api_flag(regex, copy_cont)  # 这里record:是倒着找的行号
    is_flag = False
    if flag:
        record = length - 1 - record
        if in_api_structure(api_flag, r_end, pre_cont[record:]):  # 判断变更代码是否属于api接口代码
            is_flag = True
    return is_flag, api_flag, record

def has_api_flag(regex, cont):  # 这里的regex,还是区分一下文件类型比较好，避免多的差错，cont为需要检查的内容，是否有api接口标志
    api_flag, find, flag = "", False, False
    record, r_end = len(cont), -1
    for line, code_str in enumerate(cont):  # 从0开始
        if not find:
            r = regex.search(code_str)
            if r:
                api_flag, find, record, r_end = r[0], True, line, r.end()
        if find and api_flag != "":
            if api_flag == "api.":
                flag = True
            elif api_flag == "$.ajax" or api_flag == "$http":
                if "url:" in code_str:
                    if "/api/" in code_str[code_str.index("url:") + 4: len(code_str)]:
                        flag = True
            else:
                if "$rules" in code_str:
                    if "=" in code_str[code_str.index("$rules") + 6: len(code_str)]:
                        flag = True
        if flag:
            break
    return flag, api_flag, record, r_end    # record为行号， r_end为行的api标志末尾位置

def in_api_structure_typea(api_flag, pre_cont, stack, flag, in_flag):   # api. 和 $http结构相类似
    num = 1
    for code_str in pre_cont:
        p = -1
        if api_flag == "$http":
            if "url:" in code_str:
                if "/api/" in code_str[code_str.index("url:") + 4: len(code_str)]:
                    in_flag = True
        for index, c in enumerate(code_str):
            if num:
                if c == "(":
                    stack.append("(")
                    flag = True
                if c == ")" and flag:
                    stack.pop()
                    p = index
                if len(stack) == 0 and flag:  # ".then" or ".catch" or ".finally"   api.func().then()
                    num -= 1
                    length = len(code_str)
                    for k in [".then", ".catch", ".finally"]:
                        if k in code_str[p + 1:length]:
                            num += 1
                            break
            else:
                break
        if num == 0:
            break
    if api_flag == "api.":
        return False if len(stack) == 0 else True
    else:
        return False if len(stack) == 0 else True if in_flag else False

def in_api_structure_typeb(api_flag, pre_cont, stack, flag, in_flag):   # $.ajax 和 public function结构相类似
    if api_flag == "$.ajax":
        url_flag, other_flag, left, right = "url:", "/api/", "(", ")"
    else:
        url_flag, other_flag, left, right = "$rules", "=", "{", "}"
    for code_str in pre_cont:
        if url_flag in code_str:
            if other_flag in code_str[code_str.index(url_flag) + len(url_flag): len(code_str)]:
                in_flag = True
        for c in code_str:
            if c == left:
                stack.append(left)
                flag = True
            if c == right and flag:
                stack.pop()
            if len(stack) == 0 and flag:
                break
    return False if len(stack) == 0 else True if in_flag else False

def in_api_structure(api_flag, r_end, pre_cont):
    pre_cont[0], stack, flag, in_flag = pre_cont[0][r_end: len(pre_cont[0])], [], False, False
    if api_flag == "api." or api_flag == "$http":
        return in_api_structure_typea(api_flag, pre_cont, stack, flag, in_flag)
    else:
        return in_api_structure_typeb(api_flag, pre_cont, stack, flag, in_flag)

def has_api_msg(pre_cont): # 是否有对应的注释信息，有则提取
    length = len(pre_cont)  # 进行范围的限制，避免无效的搜索
    end = 0 if length <= 20 else length - 20
    flag, record, save_list = False, 0, []
    for i in range(length - 1, end - 1, -1):
        if "*/" in pre_cont[i]:
            flag, record = True, i
            break
    if flag:
        end_flag = False
        for j in range(record - 1, -1, -1):
            if not end_flag and "*" in pre_cont[j]:
                temp = pre_cont[j].split("*")[-1].strip()
                if len(temp) > 0:
                    save_list.append(temp)
                if "/**" in pre_cont[j]:
                    end_flag = True
            else:
                break
        if len(save_list) >= 3:  # 意味着已经注释完成，如果没有":"，即如果是其他，此时save_list仍然为空，这种依然没有意义, 排除某些单个注释的
            save_list.reverse()
            return True, save_list
    save_list.clear()
    return False, save_list  # 没有找到*/ or save_list为空都算是没有意义的

def produce_api_msg_util(other_code, param_dict, left, right, split_sign):  # 在自行生成api注释信息时的公共处理部分
    stack, flag, begin, end = [], False, 0, 0
    for i, s in enumerate(other_code):
        if s == left:
            if not flag:
                begin = i + 1
            stack.append(s)
            flag = True
        if s == right and flag:
            stack.pop()
        if len(stack) == 0 and flag:
            end = i
            break
    if len(stack) > 0 and flag:  # { ... 这种情况
        end = len(other_code)
    param_str = other_code[begin:end] if begin < end else ""
    if param_str:
        param_list = param_str.split("\n")
        for param in param_list:
            if len(param.strip()) > 0:
                params = param.split(split_sign)
                if len(params) > 1:
                    key = params[0].strip() if len(params[0].strip()) > 0 else ""
                    value = params[1].strip() if len(params[1].strip()) > 0 else ""
                    if key and value and "//" not in key and "//" not in value:
                        param_dict[key] = value

def produce_api_msg(api_flag, cont): # 尽最大可能准确的分析
    function_name, temp_dict = "func_name", {}
    func_name, param_dict = "", {}
    if api_flag == "api.":
        regex_func = re.compile(r"(?<=api\.)(\w+)")
        m1 = regex_func.search(cont[0])
        func_name = m1[0] if m1 else "" # 到此为此function名提取成功
        copy_cont = cont[:]
        copy_cont[0] = copy_cont[0][m1.end():]
        other_code = "\n".join(copy_cont) # function名后的所有代码
        produce_api_msg_util(other_code, param_dict, "{", "}", ":")

    elif api_flag == "$.ajax" or api_flag == "$http":
        param_flag = "data:" if api_flag == "$.ajax" else "params:"
        for code_str in cont:
            if "url:" in code_str:
                temp = code_str.split(":")[-1].split(",")[0].strip()
                split_sign = "'" if "'" in temp else '"'
                func_name = temp.split(split_sign)[1] if len(temp.split(split_sign)) > 2 else ""
                break
        all_code = "\n".join(cont)
        if param_flag in all_code:
            other_code = all_code[all_code.index(param_flag) + len(param_flag):]
            produce_api_msg_util(other_code, param_dict, "{", "}", ":")
        function_name = "url"

    else:
        regex_func = re.compile(r"\w+\s*\(.*?\)")
        m1 = regex_func.search(cont[0])
        if m1:
            func_name = m1[0].split("(")[0]
            temp_param = m1[0].split("(")[-1].split(")")[0].strip()
            if len(temp_param.split()) > 1:
                param_dict[temp_param.split()[0]] = temp_param.split()[-1]
        all_code = "\n".join(cont)
        if "$rules" in all_code:
            other_code = all_code[all_code.index("$rules") + 6:]
            produce_api_msg_util(other_code, param_dict, "[", "]", "=>")

    if len(func_name) > 0:
        temp_dict[function_name] = func_name
    if len(param_dict) > 0:
        temp_dict["params"] = param_dict
    return temp_dict