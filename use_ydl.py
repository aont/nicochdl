#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import sys
import requests
# import codecs
import re
import unicodedata
import lxml.html
import glob
import time 
import youtube_dl
import shutil
import datetime
import traceback

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
            break
        except Exception as e:
            sys.stderr.write("[Exception] %s\n"%(e))
            sys.stderr.write("[Info] waiting for %s secs\n" % waiting_time)
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
        raise
    items = items_ary[0].find_class('item')
    # print len(items)
    for item in items:
        title_ary = item.find_class('title')
        if len(title_ary)!=1:
            # print len(title_ary)
            raise

        # print lxml.html.tostring(title_ary[0])
        anchor_ary = title_ary[0].findall('./a')
        if len(anchor_ary)!=1:
            # print len(anchor_ary)
            raise
        anchor = anchor_ary[0]
        href = anchor.get('href')
        title = anchor.get('title')
        purchase_type_ary = item.find_class('purchase_type')
        purchase_type = ""
        if len(purchase_type_ary)>1:
            raise
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

        yield {'href': href, 'title': title, 'purchase_type': purchase_type}
        # links.append({'href': href, 'title': title, 'purchase_type': purchase_type})
    # return links
    

def nicoch_get(chname):
    sess = requests.session()
    # todo
    page = 1
    
    while True:
        links = list(nicoch_get_page(sess, chname, page))
        for link in links:
            yield link
            # print(link)
            # do something here
        
        # break     
        if len(links)<20:
            break
        page += 1
        # time.sleep(5)


def nico_batchdl(chname, username, password):
    ydl_opts = {'format': 'best', 'username': username, 'password': password, 'outtmpl': '%(id)s_%(format_id)s.mp4'}
    ydl = youtube_dl.YoutubeDL(ydl_opts)
    for link in nicoch_get(chname):
        # print(link)
        nico_download(ydl, link)

def valid_fn(fn):
    character_replace = {
        u'\\': u'＼',
        u'/': u'／',
        u':': u'：',
        u'?': u'？',
        u'\"': u'”',
        u'<': u'＜',
        u'>': u'＞',
        u'|': u'｜',
        u' ': u'_',
        u'*': u'＊',
        u'+': u'＋',
        u'~': u'～',
        u'!': u'！',
    }
    for key, value in character_replace.items():
        fn = fn.replace(key, value)
    return fn

def wait_noneco():
    datetime_now = datetime.datetime.now()
    if datetime_now.hour in range(0, 2):
        wake_time = datetime.datetime(year=datetime_now.year, month=datetime_now.month, day=datetime_now.day, hour=2)
        sleep_duration = (wake_time - datetime_now).total_seconds()
        sys.stderr.write("[info] sleep until %s\n" % wake_time)
        time.sleep(sleep_duration)
    elif (datetime_now.hour in range(18, 25) ) or (datetime_now.weekday() in [5,6] and datetime_now.hour in range(12, 18) ):
        wake_time = datetime.datetime(year=datetime_now.year, month=datetime_now.month, day=datetime_now.day, hour=2)
        wake_time += datetime.timedelta(days=1)
        sys.stderr.write("[info] sleep until %s\n" % wake_time)
        sleep_duration = (wake_time - datetime_now).total_seconds()
        time.sleep(sleep_duration)

def wait_eco():
    datetime_now = datetime.datetime.now()
    if (datetime_now.weekday() in range(0,5) and datetime_now.hour in range(2, 18) ):
        wake_time = datetime.datetime(year=datetime_now.year, month=datetime_now.month, day=datetime_now.day, hour=18)
        sleep_duration = (wake_time - datetime_now).total_seconds()
        sys.stderr.write("[info] sleep until %s\n" % wake_time)
        time.sleep(sleep_duration)
    elif (datetime_now.weekday() in [5,6] and datetime_now.hour in range(2, 12) ):
        wake_time = datetime.datetime(year=datetime_now.year, month=datetime_now.month, day=datetime_now.day, hour=12)
        sys.stderr.write("[info] sleep until %s\n" % wake_time)
        sleep_duration = (wake_time - datetime_now).total_seconds()
        time.sleep(sleep_duration)

h264_pat = re.compile("h264_(\\d+)p")
aac_pat = re.compile("aac_(\\d+)kbps")
url_pat = re.compile('https://www.nicovideo.jp/watch/(.+)')

def nico_download(ydl, link):

    watch_id_match = url_pat.match(link['href'])
    if watch_id_match is None:
        raise Exception("unexpected url")
    watch_id = watch_id_match.group(1)

    purchase_type = link["purchase_type"]
    if not link["purchase_type"] in ['free_for_member', 'member_unlimited_access']:
        sys.stderr.write("[info] skipping %s since purchase_type=%s\n" % (watch_id, purchase_type))
        return

    glob_result = glob.glob("./%s_*_*.mp4" % (watch_id))
    if glob_result:
        sys.stderr.write("[Info] skipping %s since it is downloaded before\n" % watch_id)
        return
        # raise Exception("skip")

    waiting_time = 60

    video_title = link['title']
    
    # glob_result = glob.glob("./%s_*_*.mp4" % watch_id)
    # if glob_result:
    #     sys.stderr.write("[Info] skipping %s since it is downloaded before\n" % watch_id)
    #     return
    #     # raise Exception("skip")
    
    selected_format_id = None
    
    while True:
        try:
            if mode=="best":
                wait_noneco()
            elif mode=="low":
                wait_eco()

            time_before_dl = time.time()
            if selected_format_id is None:
                if ydl.params.get('format'):
                    ydl.params.update({"format": None})
                    del ydl.params['format']
                
                # todo
                sys.stderr.write("[info] now=%s\n" % time.strftime("%Y/%m/%d %H:%M:%S")) 
                

                meta = ydl.extract_info(link['href'], download=False)
                formats = meta.get('formats', [meta])

                formats_unpacked = []
                for f in formats:
                    format_id = f["format_id"]
                    h264_match = h264_pat.search(format_id)
                    if not h264_match:
                        raise Exception("h264 pattern does not match: %s" % format_id)
                    h264_res = int(h264_match.group(1))
                    aac_match = aac_pat.search(format_id)
                    if not aac_match:
                        raise Exception("aac pattern does not match: %s" % format_id)
                    aac_rate = int(aac_match.group(1))
                    formats_unpacked.append({ "format_id": format_id, "h264_res": h264_res, "aac_rate": aac_rate })
                    # for key, value in f.items():
                    #     sys.stderr.write("  %s: %s\n" % (key, value))
                # sys.stderr.write("[info] formats=%s\n" % formats_unpacked)

                selected_format_id = None
                if mode=="best":
                    selected_h264_res = 0
                    selected_aac_rate = 0
                    for f in formats_unpacked:
                        format_id = f["format_id"]
                        if "low" in format_id:
                            continue
                        # tbr = f.get("tbr")
                        # if tbr is None:
                        #     continue
                        h264_res = f["h264_res"]
                        aac_rate = f["aac_rate"]
                        if selected_h264_res <= h264_res and selected_aac_rate <= aac_rate:
                            selected_format_id = format_id
                            selected_h264_res = h264_res
                            selected_aac_rate = aac_rate


                elif mode=="low":
                    selected_aac_rate = 0
                    for f in formats_unpacked:
                        format_id = f["format_id"]
                        if not "low" in format_id:
                            continue
                        # h264_res = f["h264_res"]
                        aac_rate = f["aac_rate"]
                        if selected_aac_rate <= aac_rate:
                            selected_format_id = format_id
                            # selected_h264_res = h264_res
                            selected_aac_rate = aac_rate
                    
                else:
                    raise Exception("unexpected mode %s" % mode)
                
                if not selected_format_id:
                    raise Exception("format not selected")

                sys.stderr.write("[Info] selected: %s\n" % selected_format_id)

                # return

                waiting_time = 60
                # if selected_format_id=='normal':
                #     sys.stderr.write("[Info] skipping\n")
                #     break
                
            ydl.params.update({"format": selected_format_id})            
            
            # '%(id)s_%(title)s_%(format)s.%(ext)s'
            ydl.download([link['href']])
            ydl.params.update({"format": None})
            # del ydl.params['format']
            waiting_time = 60
            break
        except youtube_dl.utils.DownloadError as e:

            e_str = str(e)
            # essage=="ERROR: giving up after 0 retries":
                
            if e_str in ["ERROR: requested format not available"]:
                selected_format_id = None
                ydl.params.update({"format": None})
                # del ydl.params['format']
            elif e_str in ['ERROR: niconico reports error: invalid_v1', 'ERROR: unable to rename file: [Error 32] プロセスはファイルにアクセスできません。別のプロセスが使用中です。']:
                selected_format_id = None
                ydl.params.update({"format": None})
                # del ydl.params['format']
                sys.stderr.write("[Error] skipping\n")
                return
            else: # elif e_str in ['ERROR: unable to download video data: HTTP Error 403: Forbidden', 'ERROR: Unable to download webpage: HTTP Error 503: Service Unavailable (caused by HTTPError()); please report this issue on https://yt-dl.org/bug . Make sure you are using the latest version; see  https://yt-dl.org/update  on how to update. Be sure to call youtube-dl with the --verbose flag and include its complete output.', 'ERROR: giving up after 0 retries']:
                time_after_dl = time.time()
                sys.stderr.write("[DownloadError]\n")
                if (time_after_dl - time_before_dl) > 60:
                    waiting_time = 60
                else:
                    sys.stderr.write("[Info] waiting for %s secs\n" % waiting_time)
                    time.sleep(waiting_time)
                    waiting_time *= 2

        except Exception as e:
            tb = traceback.format_exc()
            sys.stderr.write("%s\n%s\n"%(tb, e))
            # sys.stderr.write("[Exception]\n")
            sys.stderr.write("[Info] waiting for %s secs\n" % waiting_time)
            time.sleep(waiting_time)
            waiting_time *= 2

    shutil.move("%s_%s.mp4" % (watch_id, selected_format_id), "%s_%s_%s.mp4"%(watch_id, valid_fn(video_title), selected_format_id))

mode = sys.argv[1]
# "low"
# "best"
if __name__ == '__main__':
    
    os.chdir(mode)
    username = os.environ['NICO_USER']
    password = os.environ['NICO_PASSWORD']
    channel = os.environ['NICO_CHANNEL']
    nico_batchdl(channel, username, password)
