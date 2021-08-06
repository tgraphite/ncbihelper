import sys
import re
from os import path, system


def run(filepath):
    re_suffix = re.compile(r'\..*')
    outpath = re.sub(re_suffix, '.txt', filepath)
    command = "blastn.exe -db nt -query {fp} -out {op} -remote".format(
        fp=filepath, op=outpath)

    try:
        print('尝试提交')
        system(command)
    except BaseException:
        print('远程数据库连接错误')
    else:
        print('已返回结果' + outpath)


def parse(filepath, testmode=False):
    re_query = re.compile(r'^Query=\ .*$')
    # re_seq = re.compile(r'^[A-Z]+_?[0-9]+\..*[0-9]+.*$')
    re_seq_record = re.compile(r'^>[A-Z]+_?[0-9]+\..*$')
    re_seq_i10s = re.compile(r'^\ Identities.*$')
    re_seq_len = re.compile(r'^Length=[0-9]+')
    re_suffix = re.compile(r'\..*')

    report = open(filepath, 'r')

    result_dict = dict()
    line_count = int(-9999)

    for line in report:
        line_count += 1

        if re.match(re_query, line):
            line_count = int(0)
            this_query = line.split(' ')[1]
            result_dict[this_query] = list()

        elif line_count <= 8 and re.match(re_seq_len, line):
            this_query_len = float(line.split('=')[1])

        elif line_count >= 8 and line_count <= 12:
            result_dict[this_query].append(line)

        elif line_count >= 13:
            if re.match(re_seq_record, line):
                this_seq = line.split(' ')[0]
                this_seq = this_seq.replace('>', '')

            # elif re.match(re_seq_len, line):
            #     ref_seq_len = float(line.split('=')[1])

            elif re.match(re_seq_i10s, line):
                i10s = ' ' + line.split(' ')[4]
                i10s = i10s.replace('(', '').replace('),', '')

                gap_card = line.split(' ')[7]
                # gap = float(gap_card.split('/')[0])
                cover = float(gap_card.split('/')[1])
                # net_cover = cover #- gap
                coverage = round(100 * cover / this_query_len, 1)
                coverage = str(coverage) + '%'

                info_card = i10s + '  ' + coverage

                for item in result_dict[this_query]:
                    if this_seq in item:
                        if not info_card in item:
                            new_item = item.replace('\n', '') + info_card + '\n'
                            result_dict[this_query].append(new_item)
                            result_dict[this_query].remove(item)
                        # print(result_dict[this_query])
                        # result_dict[this_query].remove(item)
                        # # print('-'*40)
                        pass

        else:
            pass

    if testmode:
        for key in result_dict.keys():
            print('----------------------------------------\n')
            print(key)
            print('Sequence for alignment | Score | E-Value | Identities | Coverage\n')
            for inst in result_dict[key]:
                print(inst)

    outpath = re.sub(re_suffix, '_parsed.txt', filepath)
    outfile = open(outpath, 'w')

    for key in result_dict.keys():
        outfile.write('----------------------------------------\n')
        outfile.write(key)
        outfile.write(
            'Sequence for alignment | Score | E-Value | Identities | Coverage\n')
        outfile.write('\n')

        for inst in result_dict[key]:
            outfile.write(inst)

    print('已解析结果' + outpath)


def dev_mode():
    file_path_fasta = '3.fasta'
    file_path_report = 'example.txt'
    parse(file_path_report, testmode=True)


def main():
    notif = '''
    NCBI-Blast-NT助手 版本0.31
    
    用法：
    1、将.fas/.fasta拖入本窗口，将调用远端数据库进行比对，等待返回未解析的.txt文件。
    2、将上一步产生（或其他方式获得）的未解析.txt文件拖入本窗口，立即返回已解析的_parse.txt文件。
    
    提示：
    1、本工具及其组件的路径、输入文件的路径和内容中，不要有非英文字符和不必要的空格。
    2、远端数据库返回速度取决于数据量和网络状况，一般耗时0.1-3小时不等，通常在白天工作时间最快。
    3、一次建议比对数据量小于150个，过大容易引起远端数据库长时间不返回。
    
    维护与功能定制：
    微信 TGraphite
    '''
    print(notif)

    filepath = input()
    file_basename = path.basename(filepath)

    re_fasta = re.compile(r'.*\.(fas|fasta)')
    re_txt = re.compile(r'.*\.txt')

    if not path.exists(filepath):
        print('无此文件')
    elif re.match(re_fasta, file_basename):
        run(filepath)
    elif re.match(re_txt, file_basename):
        parse(filepath)

    print('按回车键退出')
    nothing = input()


if __name__ == "__main__":
    # main()
    dev_mode()
