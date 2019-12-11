#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time
import os
import sys
import codecs
import re
import glob
import traceback
import requests
import subprocess
import shutil
import datetime
import unicodedata
import json
import csv
import cssselect

import lxml.html
import lxml.etree

import csv

url_pat = re.compile('https://www.nicovideo.jp/watch/(.+)')
def nicoch_get_page(sess, chname, pagenum):
    path = 'https://ch.nicovideo.jp/%s/video' % chname
    # links = []
    waiting_time = 10
    while True:
        try:
            result = sess.get(path, params={'page': pagenum, 'sort': 'f', 'order': 'd'})
            # sort
            #  f: toukou
            #  v: saisei
            #  r: comment
            #  m: mylist
            #  n: comment ga atarasii
            #  l: saisei jikan
            # order 'a'scending or 'd'escending
            break
        except Exception as e:
            sys.stderr.write("[Exception] %s\n"%(e))
            sys.stderr.write("[info] waiting for %s secs\n" % waiting_time)
            time.sleep(waiting_time)
            waiting_time *= 2
            # pass

    # result = sess.get(path, params={'page': pagenum})
    result_text = result.text
    result_text = unicodedata.normalize('NFKC', result_text)
    niconico_html = lxml.html.fromstring(result_text)
    
    items_ary = niconico_html.find_class('items')
    if len(items_ary)==0:
        return
        # return links
    elif len(items_ary)!=1:
        sys.stderr.write("page=%s\n" % pagenum)
        raise Exception("unexpected")
    items = items_ary[0].find_class('item')
    # print len(items)
    for item in items:
        title_ary = item.find_class('title')
        if len(title_ary)!=1:
            # print len(title_ary)
            raise Exception("unexpected")
        
        # print lxml.html.tostring(title_ary[0])
        anchor_ary = title_ary[0].findall('./a')
        if len(anchor_ary)!=1:
            # print len(anchor_ary)
            raise Exception("unexpected")
        anchor = anchor_ary[0]
        href = anchor.get('href')
        title = anchor.get('title')
        purchase_type_ary = item.find_class('purchase_type')
        purchase_type = ""
        if len(purchase_type_ary)>1:
            raise Exception("unexpected")
        elif len(purchase_type_ary)==1:
            purchase_type = purchase_type_ary[0]
            if len(purchase_type.find_class('all_pay'))>0:
                purchase_type = 'all_pay'
            elif len(purchase_type.find_class('free_for_member'))>0:
                purchase_type = 'free_for_member'
            elif len(purchase_type.find_class('member_unlimited_access'))>0:
                purchase_type = 'member_unlimited_access'
            else:
                purchase_type = 'some_purchase_type'
        else:
            pass
        
        url_match = url_pat.match(href)
        watch_id = url_match.group(1)

        duration_str = item.find_class("badge br length")[0].text
        duration = duration_str
        # duration_split = duration_str.split(":")
        # duration = int(duration_split[0])*60 + int(duration_split[1])
        view_count = item.find_class("view")[0].findall('./var')[0].text
        comment_count = item.find_class("comment")[0].findall('./var')[0].text
        mylist_count = item.find_class("mylist")[0].findall('./a/var')[0].text
        upload_date = item.find_class("time")[0].findall('./time/var')[0].text.strip()

        yield {'href': href, 'watch_id': watch_id, 'title': title, 'purchase_type': purchase_type, 'duration': duration, 'view': view_count, 'comment': comment_count, 'mylist': mylist_count, 'upload_date': upload_date}

def nicoch_get(chname):
    sess = requests.session()
    page = 1
    while True:
        links = tuple(nicoch_get_page(sess, chname, page))
        for link in links:
            yield link
        if len(links)<20:
            break
        page += 1

def main():  
    
    f_csv = open("metadata.csv", "w", newline="", encoding="utf_8_sig")
    csv_writer = csv.writer(f_csv)

    nico_channel = sys.argv[1]

    csv_format = (
        "watch_id",
        "title",
        "purchase_type",
        "upload_date",
        "duration",
        "view",
        "comment",
        "mylist",
    )

    csv_writer.writerow(csv_format)

    for link in nicoch_get(nico_channel):

        row = tuple( link[item] for item in csv_format )
        csv_writer.writerow(row)
        sys.stderr.write("[info] %s\n"%repr(row))
        f_csv.flush()

    f_csv.close()

if __name__ == '__main__':
    main()