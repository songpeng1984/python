# -*- coding: utf-8 -*-
# @Time  : 2019/10/11 15:49
# @Author : xiaopeng 
# @File  : client.py
# @Software: PyCharm
# coding=utf-8

import urllib.request
from fake_useragent import UserAgent
import requests
import json
import threading, time
import os
import xmltodict
import shutil
import _thread
import zipfile


def Schedule(a, b, c):
    per = 100.0 * a * b / c
    if per > 100:
        per = 100
        print('完成！')
    print('%.2f%%' % per)


s = requests.session()
headers = {'User-Agent': UserAgent().random}

# urllib.request.urlretrieve('http://127.0.0.1:9123/WIN10.GHO', 'D:\\cfile\\WIN10.GHO', Schedule)
rooturl = 'http://127.0.0.1:12345/getfilelist'  # flask api
rxmldir = 'd:\\rxml\\'  # 回执文件夹

deccusdir = 'C:\\ImpPath\\Deccus001\\OutBox\\'  # 报关单待发送文件夹
Sasdir = 'C:\\ImpPath\\Sas\\OutBox\\'  # 核注清单待发送文件夹

deccus_recv = 'C:\\ImpPath\\Deccus001\\InBox\\'  # 报关单回执文件夹
Sas_recv = 'C:\\ImpPath\\Sas\\InBox\\'  # 核注清单回执文件夹

deccus_recv_over = 'C:\\ImpPath\\Deccus001\\RecvoverBox\\'  # 报关单回执处理完的文件夹
Sas_recv_over = 'C:\\ImpPath\\Sas\\RecvoverBox\\'  # 核注清单回执处理完的文件夹


def getfilelist():
    b = s.post(headers=headers, url=rooturl)
    result = json.loads(b.content.decode())['filelist']
    print(json.loads(b.content.decode()))
    if result is not None:
        return result
    else:
        return 0


def downxmlfile():
    if getfilelist() != 0:
        list = tuple(getfilelist())
        for fname in list:
            serverurl = 'http://127.0.0.1:9123/'  # httpserver api
            cfilenameurl = 'http://127.0.0.1:12345/cfilename?filename='  # move the file of done
            if 'xml' in fname:
                urllib.request.urlretrieve(serverurl + fname, deccusdir + fname, Schedule)
            elif 'zip' in fname:
                urllib.request.urlretrieve(serverurl + fname, Sasdir + fname, Schedule)
            cfilenameurl = cfilenameurl + fname
            s.post(headers=headers, url=cfilenameurl)
    else:
        print('0000')
    timer = threading.Timer(5, downxmlfile)
    timer.start()


def parsexml():
    for files in os.walk(deccus_recv):
        pass
        # print(files)
    filenamelist = files[2]

    if len(filenamelist) != 0:
        for filename in filenamelist:
            if 'xml' in filename:
                jxurl = 'http://172.16.10.152:10005/fDecMessage/saveReturnInfo?'
                f = open(deccus_recv + filename, 'r', encoding='GB2312')
                try:
                    f.read()
                except:
                    f = open(deccus_recv + filename, 'r', encoding='UTF-8')
                d = f.read()
                data = xmltodict.parse(d)
                strjson = json.dumps(data, ensure_ascii=False)
                strjson = 'returnInfo={}'.format(strjson)
                jxurl = jxurl + strjson
                print(jxurl)
                print(strjson)
                result = s.post(jxurl, headers=headers)
                f.close()
                if json.loads(result.content.decode())['code'] == 0:
                    shutil.move(deccus_recv + filename, deccus_recv_over + filename)
            else:
                print('我真解析不了这个biang玩意')
    else:
        print('没有报关单文件需要解析')
    timer = threading.Timer(5, parsexml)
    timer.start()


def parsezip():
    for files in os.walk(Sas_recv):
        pass
        # print(files)
    filenamelist = files[2]
    if len(filenamelist) != 0:
        for filename in filenamelist:
            if 'xml' in filename:
                wburl = 'http://172.16.10.142:10005/messageSendAndReceiver/receiver?'
                f = open(Sas_recv + filename, 'r', encoding='GB2312')
                try:
                    f.read()
                except:
                    f = open(Sas_recv + filename, 'r', encoding='UTF-8')
                d = f.read()
                # data = xmltodict.parse(d)
                # strjson = json.dumps(data, ensure_ascii=False)

                strjson = 'data={}'.format(d)
                wburl = wburl + strjson
                print(wburl)
                # print(strjson)
                result = s.post(wburl, headers=headers)
                f.close()
                if json.loads(result.content.decode())['code'] == 0:
                    shutil.move(Sas_recv + filename, Sas_recv_over + filename)
            # for filename in filenamelist:
            #     if 'zip' in filename:
            #
            #         read_zip = zipfile.ZipFile(Sas_recv + filename)
            #         for num in range(len(read_zip.namelist())):
            #             wburl = '172.16.10.142:10005/messageSendAndReceiver/receiver?'
            #             z = read_zip.read(read_zip.namelist()[num])
            #             # z = str(z, 'gb2312')
            #             zdata = xmltodict.parse(z)
            #             zstrjson = json.dumps(zdata, ensure_ascii=False)
            #             zstrjson = 'data={}'.format(zstrjson)
            #             wburl = wburl + zstrjson
            #             print(zstrjson)
            # s.post(url=wburl, headers=headers)
            else:
                print('我真解析不了这个biang玩意')
    else:
        print('没有核注清单文件需要解析')
    timer = threading.Timer(5, parsezip)
    timer.start()


if __name__ == '__main__':
    # # downxmlfile()
    parsexml()
    parsezip()
