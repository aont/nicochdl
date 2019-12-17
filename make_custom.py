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
import lxml.html



def valid_fn(fn):
    character_replace = { '\\': '＼', '/': '／', ':': '：', '?': '？', '\"': '”', '<': '＜', '>': '＞', '|': '｜', ' ': '_', '*': '＊', '+': '＋', '~': '～', '!': '！', }
    for key, value in character_replace.items():
        fn = fn.replace(key, value)
    return fn


ffmpeg_path = os.environ["FFMPEG"]
info_pat = re.compile("\\[info\\]")
frame_pat = re.compile("\\[info\\] frame")
time_pat = re.compile("time=(.*?):(.*?):(.*?) ")
speed_pat = re.compile("speed=\\s*(.*?)x")
size_pat = re.compile("size=\\s*(.*?)\\s")
bitrate_pat = re.compile("bitrate=\\s*(.+?) ") 
# http_pat = re.compile("\\[http ")
# hls_pat = re.compile("\\[hls ")

def make_custom(best_fn, low_fn, outfn, upload_date):
    # tmpfn = "tmp_%s.mp4" % os.getpid()
    # "-f", "mpegts"
    ffmpeg_cmd = [ ffmpeg_path,
        "-y", "-hide_banner",
        # "-loglevel", "level+info",
        "-i", best_fn, "-i", low_fn,
        "-map", "1:v", "-map", "0:a",
        "-c:v", "copy", "-c:a", "copy",
        "-f", "mp4",
        "-movflags", "faststart", "-bsf:a", "aac_adtstoasc",
        "-metadata", "creation_time=%s:00" % upload_date,
        outfn
    ]
    proc = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.DEVNULL, stdin=subprocess.DEVNULL)

    proc.wait()
    if proc.returncode != 0:
        raise Exception("ffmpeg exited with code %d (0x%X)\ncmd:%s" % (proc.returncode, proc.returncode, ffmpeg_cmd))

    # time.sleep(5)
    # shutil.move(tmpfn, outfn)


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

    outdir = "custom"
    nico_channel = os.environ["NICO_CHANNEL"]

    for link in nicoch_get(nico_channel):


        watch_id = link["watch_id"]
        sys.stderr.write("[info] watch_id=%s\n" % watch_id)
        purchase_type = link["purchase_type"]

        if not link["purchase_type"] in ['free_for_member', 'member_unlimited_access']:
            sys.stderr.write("[info] skipping %s since purchase_type=%s\n" % (watch_id, purchase_type))
            continue

        low_glob_result = glob.glob("%s/%s_*_*.mp4" % ("low", watch_id))
        best_glob_result = glob.glob("%s/%s_*_*.mp4" % ("best", watch_id))

        if not (len(low_glob_result)==1 and len(best_glob_result)==1):
            raise Exception("file not found")

        best_fn = best_glob_result[0]
        low_fn = low_glob_result[0]
        # save_path = "NUL"
        save_path = os.path.join(outdir, "%s_%s_custom.mp4" % (watch_id, valid_fn(link["title"])))
        if os.path.exists(save_path):
            sys.stderr.write("[info] skip %s\n" % save_path)
            continue

        make_custom(best_fn, low_fn, save_path, link["upload_date"])



if __name__ == '__main__':
    main()