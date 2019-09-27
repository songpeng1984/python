# -*- coding: utf-8 -*-
# @Time  : 2019/9/19 16:53
# @Author : xiaopeng 
# @File  : test1.py
# @Software: PyCharm
# !/usr/bin/env Python
# coding=utf-8

import requests
import hashlib
from aip import AipOcr
from lxml import etree
import random
import re
import time, datetime
from fake_useragent import UserAgent
from pymongo import MongoClient
import warnings
import json
from flask import Flask, request
from multiprocessing import Pool
import threading

server = Flask(__name__)

try:
    conn = MongoClient('10.1.0.10', 27017)
    db = conn.db
    user = db.user
    sasdetails = db.sasdetails
    exception = db.exception
    log = db.invtlog
    invetfile = db.invetfile
    excepinvet = db.excepinvet
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


def save_data_b(list_i, sess, name):
    down_ck = 'https://swapp.singlewindow.cn/decserver/sw/dec/merge/queryDecData'
    headers = {'User-Agent': UserAgent().random}
    for cusNo in list_i:
        ck_data = {'cusCiqNo': cusNo, 'cusIEFlag': cusNo[0], 'operationType': 'cusEdit'}
        ck_rs = sess.post(url=down_ck, json=ck_data, headers=headers)
        try:
            results = json.loads(ck_rs.content.decode())['data']['preDecHeadVo']
            # results['createTime'] = str(datetime.date.today()).replace("-", "")
            results['account'] = name
            results['dataTime'] = results['declDate']
        except:
            excepinvet.insert({'cusNo': cusNo})
        try:
            t = time.time()
            invetfile.insert(results)
            t1 = time.time()
            print(cusNo, t1 - t)

        except:
            print('有问题')
            return 'faild'


def save_data_h(r_list, sess, name):
    for r_seqno in r_list:
        headers = {'User-Agent': UserAgent().random}
        sasdetails_url = 'https://swapp.singlewindow.cn/sasserver/sw/ems/invt/Sas/details/{}'.format(r_seqno)
        rc = sess.post(url=sasdetails_url, headers=headers)
        try:
            results = json.loads(rc.content.decode())['data']
            results['seqNo'] = r_seqno
            results['account'] = name
            results['dataTime'] = json.loads(rc.content.decode())['data']['invtHeadType']['invtDclTime']
        except:
            exception.insert({'seqNo': r_seqno})

        try:
            t = time.time()
            sasdetails.insert(results)
            t1 = time.time()
            print(r_seqno, t1 - t)

        except:
            print('有问题')
            return 'faild'


@server.route('/', methods=['POST'])
def server_post():
    if request.method == 'POST':
        name = request.values.get('name')  # 用户名
        passwd = request.values.get('passwd')  # 密码
        entNo = request.values.get('entNo')  # 授权企业编号
        serverlist = request.values.get('serverlist')  # 服务传0 或1 0：启用  1：不启用     组合 0,0 0,1 1,0
        userList = []
        for x in user.find({}, {"_id": 0, 'name': 1, "entNo": 1}):
            userList.append(x['entNo'])
            userList.append(x['name'])
        if entNo not in userList or name not in userList:
            user.insert({'name': name, 'passwd': passwd, 'entNo': entNo, 'serverlist': serverlist})
            # print(list(user.find({}, {"_id": 0, "entNo": 1})))
            return {'name': name, 'passwd': passwd, 'entNo': entNo, 'serverlist': serverlist}
        else:
            return '具有相同客户'


@server.route('/data', methods=['POST'])
def search_data():
    maoyie = 0.0
    goodslist = set()
    b_goodslist = set()
    entlist = []
    dclqty = 0
    i = 0
    e = 0
    ii = 0
    ee = 0
    b_maoyie = 0.0  # 报关单的贸易额
    client_list = set()  # 收发货人（）家
    if request.method == 'POST':
        name = request.values.get('name')
        passwd = request.values.get('passwd')
        if list(user.find({}, {'account': name, 'passwd': passwd})) != []:
            num = len(list(sasdetails.find({}, {'account': name})))
            b_num = len(list(invetfile.find({}, {'account': name})))
            z_num = len(list(sasdetails.find({}, {'account': name, 'dataTime': str(datetime.date.today() - datetime.timedelta(days=1)).replace("-", "")})))
            bz_num = len(list(invetfile.find({}, {'account': name, 'dataTime': str(datetime.date.today() - datetime.timedelta(days=1))})))
            for sr in invetfile.find({}, {'account': name, 'ownerName': 1}):
                client_list.add(sr['ownerName'])

            for b_ie in invetfile.find({}, {'account': name, 'ciqIEFlag': 1}):
                if b_ie['ciqIEFlag'] == 'I':
                    ii = ii + 1
                else:
                    ee = ee + 1
            for ie in sasdetails.find({}, {'account': name, 'invtHeadType': 1}):
                for iore in ie['invtHeadType']['impexpMarkcd']:
                    if iore == 'I':
                        i = i + 1
                    else:
                        e = e + 1

            for en in user.find({}, {'account': name, 'entNo': 1}):
                if ',' in en['entNo']:
                    entlist = en['entNo'].split(',')
                else:
                    entlist = ['1']

            for invtHeadType in sasdetails.find({}, {'account': name, 'invtListType': 1}):
                for totalAmt in invtHeadType['invtListType']:
                    goodslist.add(totalAmt['gdecd'])
                    maoyie = maoyie + float(totalAmt['dclTotalAmt'])
                    dclqty = dclqty + int(totalAmt['dclQty'])

            for decMergeListVo in invetfile.find({}, {'account': name, 'decMergeListVo': 1}):
                for declTotal in eval(decMergeListVo['decMergeListVo']):
                    # print(declTotal['declTotal'])
                    b_goodslist.add(declTotal['codeTs'])
                    b_maoyie = b_maoyie + float(declTotal['goodsToalVal'])

            # num:总单量   maoyie：总贸易额 goodsnum：总贸易商品  entnum：授权企业数量 z_num：昨日单量 hi：核注清单进口量  he：核注清单出口量
            return {'numz': num + b_num, 'maoyie': maoyie + b_maoyie, 'goodsnum': len(goodslist) + len(b_goodslist), 'entnum': len(entlist), 'z_num': z_num,
                    'hi': i, 'he': e, 'bi': ii, 'be': ee, 'sr': len(client_list), 'bz_num': bz_num}
        else:
            return {'code': 1, 'message': '登录失败,请确认用户名和密码'}


@server.route('/pz', methods=['POST'])
def loadData():
    name = request.values.get('name')
    for t in user.find({'name': name}):
        passwd = t['passwd']
        entNo = t['entNo']
        serverlist = t['serverlist']

    # name, passwd, entNo, serverlist = server_post().values()
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
        if '退出' in rsp.text:
            print("登陆成功")
            if serverlist == '0,0':
                try:
                    request_1 = sess.get(
                        url='https://swapp.singlewindow.cn/deskserver/sw/deskIndex?menu_id=sas', headers=headers
                    )
                    print("进入到特殊监管区域页面,准备拉取核注清单")
                except:
                    print("进入特殊监管区域界面失败")
                io = {'I': '进口', 'E': '出口'}
                r = []
                old = []
                if list(sasdetails.find({'account': name}).sort([('_id', -1)]).limit(1)) == []:
                    for ie in io:
                        data_t['impExpMarkCd'] = ie
                        data_t['impExpMarkCdName'] = io[ie]
                        request_h = sess.post(url=hzqd_url, json=data_t, headers=headers)
                        if json.loads(request_h.content.decode())['code'] == 0:

                            print(len(json.loads(request_h.content.decode())['data']['resultList']))

                            for seqno in json.loads(request_h.content.decode())['data']['resultList']:
                                try:
                                    r.append(seqno['seqNo'])
                                except:
                                    log.insert({'exceptionTime': seqno['invtDclTime'], 'seqno': seqno['seqno']})
                if list(sasdetails.find({'account': name}).sort([('_id', -1)]).limit(1)) != []:
                    for oldlist in sasdetails.find({'account': name}):
                        old.append(oldlist['seqNo'])

                    for ie in io:
                        data_t['impExpMarkCd'] = ie
                        data_t['impExpMarkCdName'] = io[ie]
                        request_h = sess.post(url=hzqd_url, json=data_t, headers=headers)
                        if json.loads(request_h.content.decode())['code'] == 0:

                            print(len(json.loads(request_h.content.decode())['data']['resultList']))

                            for seqno in json.loads(request_h.content.decode())['data']['resultList']:
                                try:
                                    r.append(seqno['seqNo'])
                                except:
                                    log.insert({'exceptionTime': seqno['invtDclTime'], 'seqno': seqno['seqno']})
                r = list(set(r).difference(set(old)))  # 新旧比较
                print(len(r))
                o = []
                unit = len(r) // 6  # 处理长度
                unit_0 = r[:unit]
                unit_1 = r[unit:unit * 2]
                unit_2 = r[unit * 2:unit * 3]
                unit_3 = r[unit * 3:unit * 4]
                unit_4 = r[unit * 4:unit * 5]
                unit_5 = r[unit * 5:]
                thread_0 = threading.Thread(target=save_data_h, args=(unit_0, sess, name))
                o.append(thread_0)
                thread_1 = threading.Thread(target=save_data_h, args=(unit_1, sess, name))
                o.append(thread_1)
                thread_2 = threading.Thread(target=save_data_h, args=(unit_2, sess, name))
                o.append(thread_2)
                thread_3 = threading.Thread(target=save_data_h, args=(unit_3, sess, name))
                o.append(thread_3)
                thread_4 = threading.Thread(target=save_data_h, args=(unit_4, sess, name))
                o.append(thread_4)
                thread_5 = threading.Thread(target=save_data_h, args=(unit_5, sess, name))
                o.append(thread_5)
                for k in o:
                    k.setDaemon(True)
                    k.start()
                    print('线程{}启动'.format(k))
                for kk in o:
                    kk.join()
                    print('线程{}执行收敛'.format(kk))
                '''-------------报关单------------'''

                try:
                    request_2 = sess.get(
                        url='https://swapp.singlewindow.cn/deskserver/sw/deskIndex?menu_id=dec001', headers=headers
                    )
                    print("进入到货物申报页面,准备拉取报关单")
                except:
                    print("进入货物申报页面失败")
                dclTrnRelFlag = ('2', '0')
                cusIEFlag = ('I', 'E')
                etpsCategory = ('A', 'B', 'C')
                invetodllist = []
                ndays = 6
                if list(invetfile.find({'account': name}).sort([('_id', -1)]).limit(1)) == []:
                    updateTime = '2019-01-01'
                    updateTimeEnd = (datetime.datetime.strptime(updateTime, '%Y-%m-%d') + datetime.timedelta(days=ndays)).__format__('%Y-%m-%d')
                    list_i = []
                    while datetime.datetime.now().__gt__(datetime.datetime.strptime(updateTime, '%Y-%m-%d') + datetime.timedelta(days=ndays)):
                        for dc in dclTrnRelFlag:
                            for cu in cusIEFlag:
                                for et in etpsCategory:

                                    cusUrl = "https://swapp.singlewindow.cn/decserver/sw/dec/merge/cusQuery?limit=200&offset=0&stName=updateTime&stOrder=desc&decStatusInfo=%25257B%252522cusCiqNoHidden%252522%3A%252522%252522%2C%252522dclTrnRelFlagHidden%252522%3A%252522%252522%2C%252522transPreNoHidden%252522%3A%252522%252522%2C%252522cusOrgCode%252522%3A%252522%252522%2C%252522dclTrnRelFlag%252522%3A%252522{}%252522%2C%252522cusDecStatus%252522%3A%252522%252522%2C%252522etpsCategory%252522%3A%252522{}%252522%2C%252522cusIEFlag%252522%3A%252522{}%252522%2C%252522entryId%252522%3A%252522%252522%2C%252522cusCiqNo%252522%3A%252522%252522%2C%252522cnsnTradeCode%252522%3A%252522%252522%2C%252522billNo%252522%3A%252522%252522%2C%252522isBillNoExactQuery%252522%3A%2525220%252522%2C%252522customMaster%252522%3A%252522%252522%2C%252522tableFlag%252522%3A%2525221%252522%2C%252522updateTime%252522%3A%252522{}%252522%2C%252522updateTimeEnd%252522%3A%252522{}%252522%2C%252522queryPage%252522%3A%252522cusBasicQuery%252522%2C%252522operType%252522%3A%2525220%252522%25257D&_={}".format(
                                        dc, et, cu, updateTime, updateTimeEnd, str(time.time()).split(".")[0])
                                    rs = sess.get(url=cusUrl, headers=headers)
                                    print(updateTime, updateTimeEnd, datetime.datetime.now(), dc, cu, et, json.loads(rs.content.decode())['total'])
                                    if int(json.loads(rs.content.decode())['total']) > 0:
                                        for cusciqno in json.loads(rs.content.decode())['rows']:
                                            list_i.append(cusciqno['cusCiqNo'])
                                    if int(json.loads(rs.content.decode())['total']) >= 200:
                                        cusUrl = "https://swapp.singlewindow.cn/decserver/sw/dec/merge/cusQuery?limit=200&offset=200&stName=updateTime&stOrder=desc&decStatusInfo=%25257B%252522cusCiqNoHidden%252522%3A%252522%252522%2C%252522dclTrnRelFlagHidden%252522%3A%252522%252522%2C%252522transPreNoHidden%252522%3A%252522%252522%2C%252522cusOrgCode%252522%3A%252522%252522%2C%252522dclTrnRelFlag%252522%3A%252522{}%252522%2C%252522cusDecStatus%252522%3A%252522%252522%2C%252522etpsCategory%252522%3A%252522{}%252522%2C%252522cusIEFlag%252522%3A%252522{}%252522%2C%252522entryId%252522%3A%252522%252522%2C%252522cusCiqNo%252522%3A%252522%252522%2C%252522cnsnTradeCode%252522%3A%252522%252522%2C%252522billNo%252522%3A%252522%252522%2C%252522isBillNoExactQuery%252522%3A%2525220%252522%2C%252522customMaster%252522%3A%252522%252522%2C%252522tableFlag%252522%3A%2525221%252522%2C%252522updateTime%252522%3A%252522{}%252522%2C%252522updateTimeEnd%252522%3A%252522{}%252522%2C%252522queryPage%252522%3A%252522cusBasicQuery%252522%2C%252522operType%252522%3A%2525220%252522%25257D&_={}".format(
                                            dc, et, cu, updateTime, updateTimeEnd, str(time.time()).split(".")[0])
                                        rs = sess.get(url=cusUrl, headers=headers)
                                        for cusciqno in json.loads(rs.content.decode())['rows']:
                                            list_i.append(cusciqno['cusCiqNo'])

                        updateTime = (datetime.datetime.strptime(updateTime, '%Y-%m-%d') + datetime.timedelta(days=ndays)).__format__('%Y-%m-%d')
                        updateTimeEnd = (datetime.datetime.strptime(updateTime, '%Y-%m-%d') + datetime.timedelta(days=ndays)).__format__('%Y-%m-%d')
                if list(invetfile.find({'account': name}).sort([('_id', -1)]).limit(1)) != []:
                    for old in invetfile.find({'account': name}):
                        invetodllist.append(old['cusCiqNo'])
                    updateTime = '2019-01-01'
                    updateTimeEnd = (datetime.datetime.strptime(updateTime, '%Y-%m-%d') + datetime.timedelta(days=ndays)).__format__('%Y-%m-%d')
                    list_i = []
                    while datetime.datetime.now().__gt__(datetime.datetime.strptime(updateTime, '%Y-%m-%d') + datetime.timedelta(days=ndays)):
                        for dc in dclTrnRelFlag:
                            for cu in cusIEFlag:
                                for et in etpsCategory:

                                    cusUrl = "https://swapp.singlewindow.cn/decserver/sw/dec/merge/cusQuery?limit=200&offset=0&stName=updateTime&stOrder=desc&decStatusInfo=%25257B%252522cusCiqNoHidden%252522%3A%252522%252522%2C%252522dclTrnRelFlagHidden%252522%3A%252522%252522%2C%252522transPreNoHidden%252522%3A%252522%252522%2C%252522cusOrgCode%252522%3A%252522%252522%2C%252522dclTrnRelFlag%252522%3A%252522{}%252522%2C%252522cusDecStatus%252522%3A%252522%252522%2C%252522etpsCategory%252522%3A%252522{}%252522%2C%252522cusIEFlag%252522%3A%252522{}%252522%2C%252522entryId%252522%3A%252522%252522%2C%252522cusCiqNo%252522%3A%252522%252522%2C%252522cnsnTradeCode%252522%3A%252522%252522%2C%252522billNo%252522%3A%252522%252522%2C%252522isBillNoExactQuery%252522%3A%2525220%252522%2C%252522customMaster%252522%3A%252522%252522%2C%252522tableFlag%252522%3A%2525221%252522%2C%252522updateTime%252522%3A%252522{}%252522%2C%252522updateTimeEnd%252522%3A%252522{}%252522%2C%252522queryPage%252522%3A%252522cusBasicQuery%252522%2C%252522operType%252522%3A%2525220%252522%25257D&_={}".format(
                                        dc, et, cu, updateTime, updateTimeEnd, str(time.time()).split(".")[0])
                                    rs = sess.get(url=cusUrl, headers=headers)
                                    print(updateTime, updateTimeEnd, datetime.datetime.now(), dc, cu, et, json.loads(rs.content.decode())['total'])
                                    if int(json.loads(rs.content.decode())['total']) > 0:
                                        for cusciqno in json.loads(rs.content.decode())['rows']:
                                            list_i.append(cusciqno['cusCiqNo'])
                                    if int(json.loads(rs.content.decode())['total']) >= 200:
                                        cusUrl = "https://swapp.singlewindow.cn/decserver/sw/dec/merge/cusQuery?limit=200&offset=200&stName=updateTime&stOrder=desc&decStatusInfo=%25257B%252522cusCiqNoHidden%252522%3A%252522%252522%2C%252522dclTrnRelFlagHidden%252522%3A%252522%252522%2C%252522transPreNoHidden%252522%3A%252522%252522%2C%252522cusOrgCode%252522%3A%252522%252522%2C%252522dclTrnRelFlag%252522%3A%252522{}%252522%2C%252522cusDecStatus%252522%3A%252522%252522%2C%252522etpsCategory%252522%3A%252522{}%252522%2C%252522cusIEFlag%252522%3A%252522{}%252522%2C%252522entryId%252522%3A%252522%252522%2C%252522cusCiqNo%252522%3A%252522%252522%2C%252522cnsnTradeCode%252522%3A%252522%252522%2C%252522billNo%252522%3A%252522%252522%2C%252522isBillNoExactQuery%252522%3A%2525220%252522%2C%252522customMaster%252522%3A%252522%252522%2C%252522tableFlag%252522%3A%2525221%252522%2C%252522updateTime%252522%3A%252522{}%252522%2C%252522updateTimeEnd%252522%3A%252522{}%252522%2C%252522queryPage%252522%3A%252522cusBasicQuery%252522%2C%252522operType%252522%3A%2525220%252522%25257D&_={}".format(
                                            dc, et, cu, updateTime, updateTimeEnd, str(time.time()).split(".")[0])
                                        rs = sess.get(url=cusUrl, headers=headers)
                                        for cusciqno in json.loads(rs.content.decode())['rows']:
                                            list_i.append(cusciqno['cusCiqNo'])

                        updateTime = (datetime.datetime.strptime(updateTime, '%Y-%m-%d') + datetime.timedelta(days=ndays)).__format__('%Y-%m-%d')
                        updateTimeEnd = (datetime.datetime.strptime(updateTime, '%Y-%m-%d') + datetime.timedelta(days=ndays)).__format__('%Y-%m-%d')
                list_i = list(set(list_i).difference(set(invetodllist)))
                # print(len(list_i))
                # j = set(list_i)
                # list_k = list(j)
                o = []
                unit = len(list_i) // 6  # 处理长度
                unit_0 = list_i[:unit]
                unit_1 = list_i[unit:unit * 2]
                unit_2 = list_i[unit * 2:unit * 3]
                unit_3 = list_i[unit * 3:unit * 4]
                unit_4 = list_i[unit * 4:unit * 5]
                unit_5 = list_i[unit * 5:]
                thread_0 = threading.Thread(target=save_data_b, args=(unit_0, sess, name))
                o.append(thread_0)
                thread_1 = threading.Thread(target=save_data_b, args=(unit_1, sess, name))
                o.append(thread_1)
                thread_2 = threading.Thread(target=save_data_b, args=(unit_2, sess, name))
                o.append(thread_2)
                thread_3 = threading.Thread(target=save_data_b, args=(unit_3, sess, name))
                o.append(thread_3)
                thread_4 = threading.Thread(target=save_data_b, args=(unit_4, sess, name))
                o.append(thread_4)
                thread_5 = threading.Thread(target=save_data_b, args=(unit_5, sess, name))
                o.append(thread_5)
                for k in o:
                    k.setDaemon(True)
                    k.start()
                    print('线程{}启动'.format(k))
                for kk in o:
                    kk.join()
                    print('线程{}执行收敛'.format(kk))

            elif serverlist == '0,1':
                try:
                    request_2 = sess.get(
                        url='https://swapp.singlewindow.cn/deskserver/sw/deskIndex?menu_id=dec001', headers=headers
                    )
                    print("进入到货物申报页面,准备拉取报关单")
                except:
                    print("进入货物申报页面失败")
                dclTrnRelFlag = ('2', '0')
                cusIEFlag = ('I', 'E')
                etpsCategory = ('A', 'B', 'C')
                invetodllist = []
                updateTime = '2019-01-01'
                ndays = 6
                if list(invetfile.find({'account': name}).sort([('_id', -1)]).limit(1)) == []:
                    updateTime = '2019-01-01'
                    updateTimeEnd = (datetime.datetime.strptime(updateTime, '%Y-%m-%d') + datetime.timedelta(days=ndays)).__format__('%Y-%m-%d')
                    list_i = []
                    while datetime.datetime.now().__gt__(datetime.datetime.strptime(updateTime, '%Y-%m-%d') + datetime.timedelta(days=ndays)):
                        for dc in dclTrnRelFlag:
                            for cu in cusIEFlag:
                                for et in etpsCategory:

                                    cusUrl = "https://swapp.singlewindow.cn/decserver/sw/dec/merge/cusQuery?limit=200&offset=0&stName=updateTime&stOrder=desc&decStatusInfo=%25257B%252522cusCiqNoHidden%252522%3A%252522%252522%2C%252522dclTrnRelFlagHidden%252522%3A%252522%252522%2C%252522transPreNoHidden%252522%3A%252522%252522%2C%252522cusOrgCode%252522%3A%252522%252522%2C%252522dclTrnRelFlag%252522%3A%252522{}%252522%2C%252522cusDecStatus%252522%3A%252522%252522%2C%252522etpsCategory%252522%3A%252522{}%252522%2C%252522cusIEFlag%252522%3A%252522{}%252522%2C%252522entryId%252522%3A%252522%252522%2C%252522cusCiqNo%252522%3A%252522%252522%2C%252522cnsnTradeCode%252522%3A%252522%252522%2C%252522billNo%252522%3A%252522%252522%2C%252522isBillNoExactQuery%252522%3A%2525220%252522%2C%252522customMaster%252522%3A%252522%252522%2C%252522tableFlag%252522%3A%2525221%252522%2C%252522updateTime%252522%3A%252522{}%252522%2C%252522updateTimeEnd%252522%3A%252522{}%252522%2C%252522queryPage%252522%3A%252522cusBasicQuery%252522%2C%252522operType%252522%3A%2525220%252522%25257D&_={}".format(
                                        dc, et, cu, updateTime, updateTimeEnd, str(time.time()).split(".")[0])
                                    rs = sess.get(url=cusUrl, headers=headers)
                                    print(updateTime, updateTimeEnd, datetime.datetime.now(), dc, cu, et, json.loads(rs.content.decode())['total'])
                                    if int(json.loads(rs.content.decode())['total']) > 0:
                                        for cusciqno in json.loads(rs.content.decode())['rows']:
                                            list_i.append(cusciqno['cusCiqNo'])
                                    if int(json.loads(rs.content.decode())['total']) >= 200:
                                        cusUrl = "https://swapp.singlewindow.cn/decserver/sw/dec/merge/cusQuery?limit=200&offset=200&stName=updateTime&stOrder=desc&decStatusInfo=%25257B%252522cusCiqNoHidden%252522%3A%252522%252522%2C%252522dclTrnRelFlagHidden%252522%3A%252522%252522%2C%252522transPreNoHidden%252522%3A%252522%252522%2C%252522cusOrgCode%252522%3A%252522%252522%2C%252522dclTrnRelFlag%252522%3A%252522{}%252522%2C%252522cusDecStatus%252522%3A%252522%252522%2C%252522etpsCategory%252522%3A%252522{}%252522%2C%252522cusIEFlag%252522%3A%252522{}%252522%2C%252522entryId%252522%3A%252522%252522%2C%252522cusCiqNo%252522%3A%252522%252522%2C%252522cnsnTradeCode%252522%3A%252522%252522%2C%252522billNo%252522%3A%252522%252522%2C%252522isBillNoExactQuery%252522%3A%2525220%252522%2C%252522customMaster%252522%3A%252522%252522%2C%252522tableFlag%252522%3A%2525221%252522%2C%252522updateTime%252522%3A%252522{}%252522%2C%252522updateTimeEnd%252522%3A%252522{}%252522%2C%252522queryPage%252522%3A%252522cusBasicQuery%252522%2C%252522operType%252522%3A%2525220%252522%25257D&_={}".format(
                                            dc, et, cu, updateTime, updateTimeEnd, str(time.time()).split(".")[0])
                                        rs = sess.get(url=cusUrl, headers=headers)
                                        for cusciqno in json.loads(rs.content.decode())['rows']:
                                            list_i.append(cusciqno['cusCiqNo'])

                        updateTime = (datetime.datetime.strptime(updateTime, '%Y-%m-%d') + datetime.timedelta(days=ndays)).__format__('%Y-%m-%d')
                        updateTimeEnd = (datetime.datetime.strptime(updateTime, '%Y-%m-%d') + datetime.timedelta(days=ndays)).__format__('%Y-%m-%d')

                if list(invetfile.find({'account': name}).sort([('_id', -1)]).limit(1)) != []:
                    for old in invetfile.find({'account': name}):
                        invetodllist.append(old['cusCiqNo'])
                    updateTime = '2019-01-01'
                    updateTimeEnd = (datetime.datetime.strptime(updateTime, '%Y-%m-%d') + datetime.timedelta(days=ndays)).__format__('%Y-%m-%d')
                    list_i = []
                    while datetime.datetime.now().__gt__(datetime.datetime.strptime(updateTime, '%Y-%m-%d') + datetime.timedelta(days=ndays)):
                        for dc in dclTrnRelFlag:
                            for cu in cusIEFlag:
                                for et in etpsCategory:

                                    cusUrl = "https://swapp.singlewindow.cn/decserver/sw/dec/merge/cusQuery?limit=200&offset=0&stName=updateTime&stOrder=desc&decStatusInfo=%25257B%252522cusCiqNoHidden%252522%3A%252522%252522%2C%252522dclTrnRelFlagHidden%252522%3A%252522%252522%2C%252522transPreNoHidden%252522%3A%252522%252522%2C%252522cusOrgCode%252522%3A%252522%252522%2C%252522dclTrnRelFlag%252522%3A%252522{}%252522%2C%252522cusDecStatus%252522%3A%252522%252522%2C%252522etpsCategory%252522%3A%252522{}%252522%2C%252522cusIEFlag%252522%3A%252522{}%252522%2C%252522entryId%252522%3A%252522%252522%2C%252522cusCiqNo%252522%3A%252522%252522%2C%252522cnsnTradeCode%252522%3A%252522%252522%2C%252522billNo%252522%3A%252522%252522%2C%252522isBillNoExactQuery%252522%3A%2525220%252522%2C%252522customMaster%252522%3A%252522%252522%2C%252522tableFlag%252522%3A%2525221%252522%2C%252522updateTime%252522%3A%252522{}%252522%2C%252522updateTimeEnd%252522%3A%252522{}%252522%2C%252522queryPage%252522%3A%252522cusBasicQuery%252522%2C%252522operType%252522%3A%2525220%252522%25257D&_={}".format(
                                        dc, et, cu, updateTime, updateTimeEnd, str(time.time()).split(".")[0])
                                    rs = sess.get(url=cusUrl, headers=headers)
                                    print(updateTime, updateTimeEnd, datetime.datetime.now(), dc, cu, et, json.loads(rs.content.decode())['total'])
                                    if int(json.loads(rs.content.decode())['total']) > 0:
                                        for cusciqno in json.loads(rs.content.decode())['rows']:
                                            list_i.append(cusciqno['cusCiqNo'])
                                    if int(json.loads(rs.content.decode())['total']) >= 200:
                                        cusUrl = "https://swapp.singlewindow.cn/decserver/sw/dec/merge/cusQuery?limit=200&offset=200&stName=updateTime&stOrder=desc&decStatusInfo=%25257B%252522cusCiqNoHidden%252522%3A%252522%252522%2C%252522dclTrnRelFlagHidden%252522%3A%252522%252522%2C%252522transPreNoHidden%252522%3A%252522%252522%2C%252522cusOrgCode%252522%3A%252522%252522%2C%252522dclTrnRelFlag%252522%3A%252522{}%252522%2C%252522cusDecStatus%252522%3A%252522%252522%2C%252522etpsCategory%252522%3A%252522{}%252522%2C%252522cusIEFlag%252522%3A%252522{}%252522%2C%252522entryId%252522%3A%252522%252522%2C%252522cusCiqNo%252522%3A%252522%252522%2C%252522cnsnTradeCode%252522%3A%252522%252522%2C%252522billNo%252522%3A%252522%252522%2C%252522isBillNoExactQuery%252522%3A%2525220%252522%2C%252522customMaster%252522%3A%252522%252522%2C%252522tableFlag%252522%3A%2525221%252522%2C%252522updateTime%252522%3A%252522{}%252522%2C%252522updateTimeEnd%252522%3A%252522{}%252522%2C%252522queryPage%252522%3A%252522cusBasicQuery%252522%2C%252522operType%252522%3A%2525220%252522%25257D&_={}".format(
                                            dc, et, cu, updateTime, updateTimeEnd, str(time.time()).split(".")[0])
                                        rs = sess.get(url=cusUrl, headers=headers)
                                        for cusciqno in json.loads(rs.content.decode())['rows']:
                                            list_i.append(cusciqno['cusCiqNo'])

                        updateTime = (datetime.datetime.strptime(updateTime, '%Y-%m-%d') + datetime.timedelta(days=ndays)).__format__('%Y-%m-%d')
                        updateTimeEnd = (datetime.datetime.strptime(updateTime, '%Y-%m-%d') + datetime.timedelta(days=ndays)).__format__('%Y-%m-%d')
                    list_i = list(set(list_i).difference(set(invetodllist)))
                    print('bnew:', len(list_i))
                o = []
                unit = len(list_i) // 6  # 处理长度
                unit_0 = list_i[:unit]
                unit_1 = list_i[unit:unit * 2]
                unit_2 = list_i[unit * 2:unit * 3]
                unit_3 = list_i[unit * 3:unit * 4]
                unit_4 = list_i[unit * 4:unit * 5]
                unit_5 = list_i[unit * 5:]
                thread_0 = threading.Thread(target=save_data_b, args=(unit_0, sess, name))
                o.append(thread_0)
                thread_1 = threading.Thread(target=save_data_b, args=(unit_1, sess, name))
                o.append(thread_1)
                thread_2 = threading.Thread(target=save_data_b, args=(unit_2, sess, name))
                o.append(thread_2)
                thread_3 = threading.Thread(target=save_data_b, args=(unit_3, sess, name))
                o.append(thread_3)
                thread_4 = threading.Thread(target=save_data_b, args=(unit_4, sess, name))
                o.append(thread_4)
                thread_5 = threading.Thread(target=save_data_b, args=(unit_5, sess, name))
                o.append(thread_5)
                for k in o:
                    k.setDaemon(True)
                    k.start()
                    print('线程{}启动'.format(k))
                for kk in o:
                    kk.join()
                    print('线程{}执行收敛'.format(kk))

            elif serverlist == '1,0':
                try:
                    request_1 = sess.get(
                        url='https://swapp.singlewindow.cn/deskserver/sw/deskIndex?menu_id=sas', headers=headers
                    )
                    print("进入到特殊监管区域页面,准备拉取核注清单")
                except:
                    print("进入特殊监管区域界面失败")
                io = {'I': '进口', 'E': '出口'}
                r = []
                old = []
                if list(sasdetails.find({'account': name}).sort([('_id', -1)]).limit(1)) == []:
                    for ie in io:
                        data_t['impExpMarkCd'] = ie
                        data_t['impExpMarkCdName'] = io[ie]
                        request_h = sess.post(url=hzqd_url, json=data_t, headers=headers)
                        if json.loads(request_h.content.decode())['code'] == 0:

                            print(len(json.loads(request_h.content.decode())['data']['resultList']))

                            for seqno in json.loads(request_h.content.decode())['data']['resultList']:
                                try:
                                    r.append(seqno['seqNo'])
                                except:
                                    log.insert({'exceptionTime': seqno['invtDclTime'], 'seqno': seqno['seqno']})
                if list(sasdetails.find({'account': name}).sort([('_id', -1)]).limit(1)) != []:
                    for oldlist in sasdetails.find({'account': name}):
                        old.append(oldlist['seqNo'])

                    for ie in io:
                        data_t['impExpMarkCd'] = ie
                        data_t['impExpMarkCdName'] = io[ie]
                        request_h = sess.post(url=hzqd_url, json=data_t, headers=headers)
                        if json.loads(request_h.content.decode())['code'] == 0:

                            print(len(json.loads(request_h.content.decode())['data']['resultList']))

                            for seqno in json.loads(request_h.content.decode())['data']['resultList']:
                                try:
                                    r.append(seqno['seqNo'])
                                except:
                                    log.insert({'exceptionTime': seqno['invtDclTime'], 'seqno': seqno['seqno']})
                r = list(set(r).difference(set(old)))
                print('new:', len(r))  # 新旧比较
                o = []
                unit = len(r) // 6  # 处理长度
                unit_0 = r[:unit]
                unit_1 = r[unit:unit * 2]
                unit_2 = r[unit * 2:unit * 3]
                unit_3 = r[unit * 3:unit * 4]
                unit_4 = r[unit * 4:unit * 5]
                unit_5 = r[unit * 5:]
                thread_0 = threading.Thread(target=save_data_h, args=(unit_0, sess, name))
                o.append(thread_0)
                thread_1 = threading.Thread(target=save_data_h, args=(unit_1, sess, name))
                o.append(thread_1)
                thread_2 = threading.Thread(target=save_data_h, args=(unit_2, sess, name))
                o.append(thread_2)
                thread_3 = threading.Thread(target=save_data_h, args=(unit_3, sess, name))
                o.append(thread_3)
                thread_4 = threading.Thread(target=save_data_h, args=(unit_4, sess, name))
                o.append(thread_4)
                thread_5 = threading.Thread(target=save_data_h, args=(unit_5, sess, name))
                o.append(thread_5)
                for k in o:
                    k.setDaemon(True)
                    k.start()
                    print('线程{}启动'.format(k))
                for kk in o:
                    kk.join()
                    print('线程{}执行收敛'.format(kk))

            # pool.map(print_test, r)
            # pool.close()
            # pool.join()

            break
        print("------------------------")
        print("登陆失败，继续登陆")
        time.sleep(2)
    #
    #     # return {'list': tuple(r)}
    return {'code': 0, 'message': '保存成功,开始获取当前数据'}


if __name__ == '__main__':
    warnings.filterwarnings("ignore")
    server.run(debug=True, host='127.0.0.1', port='12345')
