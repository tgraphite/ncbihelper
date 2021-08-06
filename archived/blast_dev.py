import re
from time import sleep

import requests
from prettytable import PrettyTable


class NCBI_search(object):
    def __init__(self, seq, savename, program='blastn', database='nt', desc=20, checkmax=20, postmax=5, reportmax=3):

        # 使用NCBI Blast API
        # program, database:  请求blast网站使用的搜索比对程序和数据库。
        # desc:               对每一个搜索对象，要求blast网站返回的条目数（按打分降序），默认20条。
        # checkmax:           反复检查blast网站是否出结果的最大次数，超过次数无结果即放弃，默认20次。

        # 状态码:
        #     0:  未开始
        #     10: 已提交
        #     19: 提交错误
        #     20: 已检查 - 就绪
        #     21: 已检查 - 等待
        #     22: 已检查 - 未知
        #     28: 检查超时
        #     29: 检查错误
        #     30: 已储存报告
        #     39: 报告错误
        #
        # @property方法info()返回状态码对应的中文大体含义。

        # post_search()、check_search()、report_search()对应API的提交、检查远端程序状态、索取报告操作，并更新状态码。
        # 每次调用process()方法时，根据当前状态码，决定进行以上三种操作之一，推进查询进度，若正常结束或意外失败，使self.running为非。
        # self.running为非时，上级代码应停止调用本对象的process方法，否则等于无意义的循环。

        # 根据远端服务器和本地网络的状况，可以谨慎地调整checkmax和各方法的timeout参数。

        self.url = 'https://blast.ncbi.nlm.nih.gov/Blast.cgi'
        self.savename = savename
        self.seq = seq
        self.program = program
        self.database = database
        self.desc = desc

        self.rid = str()
        self.report = str()
        self.status = int()

        self.posttime = int()
        self.checktime = int()
        self.reporttime = int()
        self.postmax = postmax  
        self.checkmax = checkmax
        self.reportmax = reportmax

        self.running = True

    def post_search(self):
        search_params = {
            'PROGRAM': self.program,
            'DATABASE': self.database,
            'QUERY': self.seq,
            'DESCRIPTIONS': self.desc,
            'CMD': 'Put',
        }

        try:
            search = requests.post(
                url=self.url, data=search_params, timeout=60)

            rid_regex = r'RID\ \=\ .*'
            rid = re.search(pattern=rid_regex,
                            string=search.text).group().split(' ')[-1]

        except BaseException:
            self.posttime += 1

            if self.posttime > 0 and self.posttime <= self.postmax:
                self.status = 18

            else:
                self.status = 19

        else:
            self.rid = rid
            self.status = 10

    def check_search(self):
        check_params = {
            'FORMAT_OBJECT': 'SearchInfo',
            'RID': self.rid,
            'CMD': 'Get',
        }

        try:
            check = requests.post(url=self.url, data=check_params, timeout=20)

            status_regex = r'(WAITING)|(UNKNOWN)|(READY)'
            status = re.search(pattern=status_regex, string=check.text).group()

        except BaseException:
            self.checktime += 3
            self.status = 22

        else:
            if status == 'WAITING':
                self.status = 21
            elif status == 'UNKNOWN':
                self.status = 22
            elif status == 'READY':
                self.status = 20

            self.checktime += 1
            if self.checktime > self.checkmax:
                self.status = 29

    def report_search(self):
        report_params = {
            'FORMAT_TYPE': 'Text',
            'RID': self.rid,
            'CMD': 'Get',
        }

        try:
            report = requests.post(
                url=self.url, data=report_params, timeout=60)
            file = open(self.savename, 'w')
            file.write(report.text)
            file.close()

        except BaseException:
            if self.reporttime >= self.reportmax:
                self.status = 39  
            else:
                self.reporttime += 1

        else:
            self.status = 30

    @property
    def info(self):
        if self.status == 0:
            info_status = '- 待机'
        elif self.status == 10:
            info_status = '> 提交'
        elif self.status == 18:
            trial_last = self.postmax - self.posttime
            infomation = '> 再次提交 剩余次数:{t}/{m}'.format(
                t=trial_last, m=self.postmax)
            info_status = infomation
        elif self.status == 19:
            info_status = 'X 提交错误'
        elif self.status >= 20 and self.status <= 22:
            trial_last = self.checkmax - self.checktime
            infomation = '> 等待报告 剩余次数:{t}/{m}'.format(
                t=trial_last, m=self.checkmax)
            info_status = infomation
        elif self.status == 28:
            info_status = 'X 检查错误'
        elif self.status == 29:
            info_status = 'X 超时'
        elif self.status == 30:
            info_status = 'O 成功'
        elif self.status == 39:
            info_status = 'X 报告错误'

        return info_status

    def process(self):
        if self.status == 30:
            self.running = False
        elif self.status == 0 or self.status == 18:
            self.post_search()
        elif self.status == 10 or self.status == 21 or self.status == 22:
            self.check_search()
        elif self.status == 20:
            self.report_search()
            if self.status == 30:
                self.running = False
        else:
            self.running = False


class batch_search(object):
    def __init__(self, seq_file, interval=5, loop_interval=180, test_mode=False):

        # seq_file -> seq_dict:
        # {
        #     seq_num: [seq_string, search_object=None]
        # }

        # 对于总数为N的搜索对象，每一次循环顺序地调用各对象的process()方法。
        # interval是两次调用之间的等待时长，loop_interval是上一循环结束到下一时长开始之间的等待时长。
        # 这是为了防止不断请求导致blast网站将本地IP降权，并节约本地网络资源。
        # 根据远端服务器和本地网络状况，可以谨慎地调节interlval和loop_interval参数。

        # 一次循环的实际耗时 = 网络接口的耗时 + N * interval + loop_interval
        # 如果一个对象的object.running值为False，也不将它从队列(seq_dict)中删除，但不再调用其process()方法，只提示状态(object.status)。

        file = open(seq_file, 'r')
        seq_index_regex = re.compile(r'\>.*')
        seq_regex = re.compile(r'[ATCGU]{10,}')
        seq_dict = dict()
        seq_pair_index = str()
        seq_pair = str()

        for line in file:
            if re.match(seq_index_regex, line):
                seq_pair_index = line.replace('>', '')
            elif re.match(seq_regex, line):
                seq_pair = line
            else:
                print("无法识别以下内容")
                print(line)
                raise FileNotFoundError


            if seq_pair_index and seq_pair:
                # print(seq_pair_index, seq_pair[:8])
                seq_dict[seq_pair_index] = [seq_pair, ]
                seq_pair_index = str()
                seq_pair = str()

        # seq_find_regex = re.compile(r'\>.*\s*[ATCGU]{50,}')
        # find_list = re.findall(seq_find_regex, file.read())
        # file.close()

        # seq_index_regex = re.compile(r'\>.*\s')
        # seq_regex = re.compile(r'[ATCGU]{50,}')
        # seq_dict = dict()

        # for inst in find_list:
        #     index = re.search(seq_index_regex, inst)
        #     index = index.group().replace('>', '')
        #     seq = re.search(seq_regex, inst).group()
        #     seq_dict[index] = [seq, ]

        self.seq_dict = seq_dict
        self.interval = interval
        self.loop_interval = loop_interval

        for inst in self.seq_dict.keys():
            seq = self.seq_dict[inst][0]
            savename = inst + '.txt'
            search = NCBI_search(seq, savename)
            self.seq_dict[inst].append(search)

        print(self.status)

    @ property
    def status(self):
        tab = PrettyTable(["测序号", "前8位", "RID", "状态"])
        for inst in self.seq_dict.keys():
            search = self.seq_dict[inst][1]
            tab.add_row([inst, self.seq_dict[inst][0]
                         [:8], search.rid, search.info])

        return tab

    def process(self):
        total_search = len(self.seq_dict)

        while True:
            end_search = int()

            for inst in self.seq_dict.keys():
                search = self.seq_dict[inst][1]
                search.process()
                print(inst, "  ", search.info)

                if not search.running:
                    end_search += 1
                if self.interval > 0:
                    sleep(self.interval)

            print(self.status)
            print("总计: {t} 已结束: {e}".format(t=total_search, e=end_search))

            if end_search == total_search:
                break

            if self.loop_interval > 0:
                sleep(self.loop_interval)


def main():
    desc_intro_1 = "NCBI Blast下载小工具 | 版本0.2"
    desc_intro_2 = "默认配置 | blastn远端程序 | nt数据库 | 单次请求间隔5秒 | 请求波次间隔90秒 | 检查超时次数20"
    desc_intro_4 = "指定客户定制 | 无限制免费维护与各类技术协助"
    desc_intro_3 = "北京时间早9时-晚6时（即美东时间夜晚）效果最佳"
    desc_intro_5 = "建议将本工具、blast报告处理工具、待查询的FASTA文件置于同一新建目录下"
    desc_intro_6 = "可使用python >= 3.8解释器修改配置或直接运行源码"

    desc_init_input = "请拖入FASTA文件或手动输入路径 | 输入SETTINGS谨慎地更改网络设置"
    desc_file_input = "请拖入FASTA文件或手动输入路径"
    desc_param_input = "请输入新的网络设置，以空格分隔，回车结束"
    desc_param_input_2 = "单次请求间隔 | 请求波次间隔"
    desc_continue = "请按任意键继续"
    desc_fatal_error = "程序意外终止，请按任意键退出"
    desc_finish = "工作完成，请按任意键结束"

    desc_split_line = '--------------------------------------------------------------------------------'

    print(desc_split_line)
    print(desc_intro_1)
    print(desc_intro_2)
    print(desc_intro_3)
    print(desc_split_line)
    print(desc_intro_4)
    print(desc_intro_5)
    print(desc_intro_6)
    print(desc_split_line)
    print(desc_init_input)

# try:
    init_input = input()

    if init_input == "SETTINGS":
        print(desc_param_input)
        print(desc_param_input_2)

        param_input = input()
        params = param_input.split(' ')[:2]
        i_interval = int(params[0])
        i_loop_interval = int(params[1])

        print(desc_file_input)
        file_path = input()

        b = batch_search(
            file_path, loop_interval=i_loop_interval, interval=i_interval)
        b.process()

    else:
        file_path = init_input

        b = batch_search(file_path, loop_interval=90, interval=5)
        b.process()

# except BaseException:
#     print(desc_split_line)
#     print(desc_fatal_error)
#     nothing = input()

# else:
    print(desc_split_line)
    print(desc_finish)
    nothing = input()


if __name__ == "__main__":
    main()
