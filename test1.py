# -*- coding: utf-8 -*-
# @Time  : 2019/9/19 16:53
# @Author : xiaopeng 
# @File  : test1.py
# @Software: PyCharm


import requests
import hashlib
from aip import AipOcr
from lxml import etree
import random
import re, os
import time, datetime
from fake_useragent import UserAgent
from pymongo import MongoClient
import warnings
import json
from flask import Flask, request
from multiprocessing import Pool
import _thread
from multiprocessing import cpu_count
import threading

server = Flask(__name__)

try:
    conn = MongoClient('127.0.0.1', 27017)
    db = conn.db
    user = db.user
    sasdetails = db.sasdetails
    log = db.invtlog
    # set = db.Checklist  # 特殊监管区域核注清单集合 富斯捷
except:
    print("mnongo连接失败")

# auth = {'8950000063362': 'aA666666', '2100030014039': 'dsy123456'}
APP_ID = '5dc8fb00f81c4b72b2ec483c6ca3ede9'
API_KEY = '9605ee4d24544a7b82b8c832ec0cfeaa'
SECRET_KEY = 'd8e3fcd43a7d4202bb33f1ef7a3e7242'
client = AipOcr(APP_ID, API_KEY, SECRET_KEY)


# md5加密
def get_md5_of_string(src):
    md1 = hashlib.md5()
    md1.update(src.encode('UTF-8'))
    return md1.hexdigest()


# 获取验证码
def get_code(ssss):
    headers = {'User-Agent': UserAgent().random}
    rsp = ssss.get(url='https://app.singlewindow.cn/cas/plat_cas_verifycode_gen?r=' + str(random.random()), headers=headers)
    res = client.basicGeneral(rsp.content)
    # print(res['words_result_num'])
    if res['words_result_num'] > 0:
        word = res['words_result'][0]['words'].replace(" ", '')
        fil = re.compile(u'[^0-9a-zA-Z]+', re.UNICODE)
        word = re.sub(fil, "", word)
        return word
    else:
        return '1111'


def save_data(r_list, sess, name):
    for r_seqno in r_list:
        headers = {'User-Agent': UserAgent().random}
        sasdetails_url = 'https://swapp.singlewindow.cn/sasserver/sw/ems/invt/Sas/details/{}'.format(r_seqno)
        rc = sess.post(url=sasdetails_url, headers=headers)
        results = json.loads(rc.content.decode())['data']
        results['seqNo'] = r_seqno
        results['account'] = name
        results['dataTime'] = json.loads(rc.content.decode())['data']['invtHeadType']['invtDclTime']
        try:
            t = time.time()
            sasdetails.insert(results)
            t1 = time.time()
            print(r_seqno, t1 - t)

        except:
            print('有问题')
            return 'faild'


def print_test(num):
    print(num, time.time())


# @server.route('/', methods=['POST'])
def server_post():
    if request.method == 'POST':
        name = request.values.get('name')
        passwd = request.values.get('passwd')
        entNo = request.values.get('entNo')
        userList = []
        for x in user.find({}, {"_id": 0, 'name': 1, "entNo": 1}):
            userList.append(x['entNo'])
            userList.append(x['name'])
        if entNo not in userList or name not in userList:
            user.insert({'name': name, 'passwd': passwd, 'entNo': entNo})
            # print(list(user.find({}, {"_id": 0, "entNo": 1})))
            return {'name': name, 'passwd': passwd, 'entNo': entNo}
        else:
            return '具有相同客户'


@server.route('/pz', methods=['POST'])
def loadData():
    name, passwd, entNo = server_post().values()
    while True:
        headers = {'User-Agent': UserAgent().random}
        root_url = 'https://app.singlewindow.cn/cas/login?service=http%3A%2F%2Fwww.singlewindow.cn%2Fsinglewindow%2Flogin.jspx'
        sess = requests.session()
        rsp = sess.get(root_url, headers=headers)

        dom = etree.HTML(rsp.text)
        lt = dom.xpath('//input[@id="lt"]/@value')[0]
        execution = dom.xpath('//input[@id="execution"]/@value')[0]
        swLoginFlag = dom.xpath('//input[@id="swLoginFlag"]/@value')[0]
        lpid = dom.xpath('//input[@id="lpid"]/@value')[0]

        while True:
            code = get_code(sess)
            if len(code) == 4:
                break
            else:
                print("当前识别验证码为：", code)
                print("重新识别中")
        print("当前识别验证码为：", code)
        print("尝试登陆")
        data = {
            'swy': name,
            'swm2': '',
            'swm': get_md5_of_string(passwd),
            'verifyCode': code,
            'lt': lt,
            'execution': execution,
            'swLoginFlag': swLoginFlag,
            'lpid': lpid,
            '_eventId': 'submit',
            'name': ''
        }
        data_t = {'bizopEtpsNo': '',
                  'bondInvtNo': '',
                  'etpsInnerInvtNo': '',
                  'impExpMarkCd': '',
                  'impExpMarkCdName': '',
                  'inputDateEnd': str(datetime.date.today()).replace("-", ""),
                  'inputDateStart': '20190101',
                  'invtType': '',
                  'invtTypeName': '',
                  'selTradeCode': entNo,
                  'seqNo': '',
                  'status': 'B',
                  'statusName': '海关终审通过',
                  'vrfdedMarkcd': '',
                  'vrfdedMarkcdName': ''}
        hzqd_url = 'https://swapp.singlewindow.cn/sasserver/sw/ems/invt/Sas/list'
        rsp = sess.post(url=root_url, headers=headers, data=data)
        rsp.encoding = 'utf-8'
        pool = Pool()
        if '退出' in rsp.text:
            print("登陆成功")
            try:
                request_1 = sess.get(
                    url='https://swapp.singlewindow.cn/deskserver/sw/deskIndex?menu_id=sas', headers=headers
                )
                print("进入到特殊监管区域页面,准备拉取核注清单")
            except:
                print("进入特殊监管区域界面失败")
            io = {'I': '进口', 'E': '出口'}
            r = []
            if list(sasdetails.find({'account': name}).sort([('_id', -1)]).limit(1)) == []:
                for ie in io:
                    data_t['impExpMarkCd'] = ie
                    data_t['impExpMarkCdName'] = io[ie]
                    request = sess.post(url=hzqd_url, json=data_t, headers=headers)
                    if json.loads(request.content.decode())['code'] == 0:

                        print(len(json.loads(request.content.decode())['data']['resultList']))

                        for seqno in json.loads(request.content.decode())['data']['resultList']:
                            try:
                                r.append(seqno['seqNo'])
                            except:
                                log.insert({'exceptionTime': seqno['invtDclTime'], 'seqno': seqno['seqno']})
            k = 0
            for n in range(1, cpu_count() + 1):
                m = r[k:len(r) // (cpu_count() - 1) * n]

                try:
                    _thread.start_new_thread(save_data, (m, sess, name))
                    # _thread.start_new_thread(print_time, ("Thread-2", 4,))
                    print('线程数{}'.format(n))
                except:
                    print('有问题')

                k = k + len(r) // (cpu_count() - 1)
                if cpu_count() - n == 0:
                    m = r[k - len(r) // (cpu_count() - 1):]
                    _thread.start_new_thread(save_data, (m, sess, name))
                    print('线程数{}'.format(n))

            # pool.map(print_test, r)
            # pool.close()
            # pool.join()

            break
        print("------------------------")
        print("登陆失败，继续登陆")
        time.sleep(2)

        # return {'list': tuple(r)}
    return '完毕'


if __name__ == '__main__':
    warnings.filterwarnings("ignore")
    server.run(debug=True, host='127.0.0.1', port='12345')
