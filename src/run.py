import os
import sys
import git
import json
import time
import re
from pydriller import RepositoryMining, GitRepository, Commit
from diff_parse_algrithm import get_diff_parsed
import Handle_Msg as hmsg

# jenkins执行方式
# export repo=`git rev-parse --show-toplevel`
# python run.py $repo

# 对路径预处理判断一下
def path_judge(file_path):
    test_list = ["app/", "public/heu_assets/", "resources/views/alarm/"]
    for t in test_list:
        if t in file_path:
            return True
    return False

# 判断文件的类型
def filetype_judge(file_path):
    suffix = file_path.split(".")[-1]
    if suffix in ["js", "php"]:
        return True, suffix
    return False, suffix

# 最终保存格式
def save_json(real_ans, last_real_ans):
    if len(real_ans) > 0:
        flag = False
        if os.path.exists("save.json"):
            flag = True
            with open("save.json", "r", encoding="utf-8") as f:
                temp = f.read()
            if len(temp) > 0:
                old_ans = json.loads(temp)
                old_ans.append(real_ans)
                with open("new_save.json", "w", encoding="utf-8") as f_new:
                    f_new.write(json.dumps(old_ans, ensure_ascii=False, indent=4))
                os.remove("save.json")
                os.rename("new_save.json", "save.json")
            else:
                flag = False
        if not flag:
            last_real_ans.append(real_ans)
            with open("save.json", "w", encoding="utf-8") as f:
                f.write(json.dumps(last_real_ans, ensure_ascii=False, indent=4))

if __name__ == "__main__":
    # 开始获取head id
    # real_path = sys.argv[1]
    real_path = r"D:\Workspace\Python_WorkSpace\app"
    gr = GitRepository(real_path)
    head_commit = gr.get_head()

    if head_commit.merge:   # 如果为merge节点不参与分析,有需要补充可以再添加
        pass
    else:
        real_ans, last_real_ans = [], []
        for m in head_commit.modifications:
            change_type_name = m.change_type.name   #ADD、DELETE、MODIFY
            file_path, source_code, diff_msg = "", [], ""
            if change_type_name == "ADD":
                file_path = m.new_path
            if change_type_name == "DELETE" or change_type_name == "MODIFY":
                file_path = m.old_path
                source_code = m.source_code_before.split("\n")
            f_flag, filetype = filetype_judge(file_path)
            # if path_judge(file_path) and f_flag:
            if f_flag:
                diff_msg = m.diff
                diff_parse_msg = get_diff_parsed(diff_msg, source_code)
                regex_js = re.compile(r"\bapi\.|(?<!\w)\$\.ajax(?!\w)|^\s*\$http(?!\w)")  # 将正则对象提前准备好，优化时间
                regex_php = re.compile(r"\bpublic\s+function(?!\w)")  #
                
                regex = regex_js if filetype == "js" else regex_php
                pre_cont, id = [], head_commit.hash
                temp_save, linea, lineb = [], 1, 1
                for cont in diff_parse_msg:
                    temp_dict = {}
                    if "ab" in cont:  # 公共代码, 记录代码行号，同时记录
                        pre_cont = cont["ab"]
                        linea += len(pre_cont)
                        lineb += len(pre_cont)
                    elif "a" in cont and "b" not in cont:  # 删除, 判断a, 记录代码行号
                        hmsg.is_api_code(regex, cont["a"], pre_cont, temp_dict, "Delete", linea)
                        linea += len(cont["a"])
                    elif "b" in cont and "a" not in cont:  # 新增，判断b，记录代码行号
                        hmsg.is_api_code(regex, cont["b"], pre_cont, temp_dict, "Add", lineb)
                        lineb += len(cont["b"])
                    else:  # 修改，调用删除，新增接口
                        hmsg_flag = hmsg.is_api_code(regex, cont["a"], pre_cont, temp_dict, "Modify", linea)
                        if not hmsg_flag:
                            hmsg.is_api_code(regex, cont["b"], pre_cont, temp_dict, "Modify", lineb)
                        linea += len(cont["a"])
                        lineb += len(cont["b"])
                    if len(temp_dict) > 0:
                        temp_save.append(temp_dict)
                if len(temp_save) > 0:
                    file_dict = {}
                    file_dict[id] = temp_save
                    file_dict["file_path"] = file_path
                    real_ans.append(file_dict)
        
        save_json(real_ans, last_real_ans)
