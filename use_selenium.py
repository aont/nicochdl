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

import lxml.html
import selenium
import selenium.webdriver.firefox.options
import selenium.webdriver

mode="low"

def str_abbreviate(str_in):
    len_str_in = len(str_in)
    if len_str_in > 128*2+10:
        return str_in[0:128] + " ... " + str_in[-128:]
    else:
        return str_in

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



def nico_login(driver, mailtel, password):
    driver.get("https://account.nicovideo.jp/login")

    mailtel_input = driver.find_element_by_id("input__mailtel")
    mailtel_input.send_keys(mailtel)
    password_input = driver.find_element_by_id("input__password")
    password_input.send_keys(password)

    login_button = driver.find_element_by_id("login__submit")
    login_button.click()

def click_control(driver):
    driver.execute_script("""
var jsapp = document.getElementById("js-app");
var player_container = jsapp.querySelector("div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer");
player_container.querySelector("div.ControllerBoxContainer > div.ControllerContainer > div > div:nth-child(3) > button.ActionButton.ControllerButton.PlayerOptionButton > div").click();
""")

def quality_menu(driver):
    driver.execute_script("""
var jsapp = document.getElementById("js-app");
var player_container = jsapp.querySelector("div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer");
player_container.querySelector("div.WheelStopper > div > div > div > div:nth-child(1) > div.PlayerOptionMenuItem.VideoQualityMenuItem > div.PlayerOptionMenuItem-content > div > a > span.PlayerOptionDropdown-toggleLabel").click();
""")

def list_quality_items(driver):
    elems = driver.find_elements_by_css_selector("#js-app > div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer > div.WheelStopper > div > div > div > div:nth-child(1) > div.PlayerOptionMenuItem.VideoQualityMenuItem > div.PlayerOptionMenuItem-content > div > div > div")
    for elem in elems:
       yield elem.text

def set_quality(driver, index):
    elems = driver.find_elements_by_css_selector("#js-app > div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer > div.WheelStopper > div > div > div > div:nth-child(1) > div.PlayerOptionMenuItem.VideoQualityMenuItem > div.PlayerOptionMenuItem-content > div > div > div")
    elems[index].click()

def get_quality(driver):
    return driver.execute_script("return document.querySelector(\".VideoQualityMenuItem > div:nth-child(2) > div:nth-child(1) > a:nth-child(1) > span:nth-child(1)\").innerText")

def system_message(driver):
    return driver.execute_script("""
var jsapp = document.getElementById("js-app");
var player_container = jsapp.querySelector("div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer");
var ev = document.createEvent('HTMLEvents');
ev.initEvent('contextmenu', true, false);
player_container.querySelector("div.InView.VideoContainer > div.VideoSymbolContainer > canvas").dispatchEvent(ev);
jsapp.querySelector("div > div.ContextMenu-wrapper > div > div > div:nth-child(1) > div:nth-child(3)").click();
return player_container.querySelector("div.InView.VideoContainer > div.SystemMessageContainer > div > div ").innerText;
""")

def get_duration(driver):
    return driver.find_element_by_css_selector(".PlayerPlayTime-duration").text


def init_driver():
    options = selenium.webdriver.firefox.options.Options()
    # options.binary_location = 'c:/Program Files/Mozilla Firefox/firefox.exe'
    options.headless = False
    driver = selenium.webdriver.Firefox(options=options)
    return driver


ffmpeg_path = os.environ["FFMPEG"]
info_pat = re.compile("\\[info\\]")
frame_pat = re.compile("\\[info\\] frame")
time_pat = re.compile("time=(.*?):(.*?):(.*?) ")
# http_pat = re.compile("\\[http ")
# hls_pat = re.compile("\\[hls ")

def download_hls(url, outfn, duration_sec):
    tmpfn = "tmp.mkv"
    # todo: remove -t
    # "-t", "60", 
    # "-loglevel", "level+info", 
    # subprocess.run([ffmpeg_path, "-y", "-hide_banner", "-loglevel", "info", "-i", url, "-c:v", "copy", "-c:a", "copy", "-movflags", "faststart", "-bsf:a", "aac_adtstoasc", tmpfn], check=True)
    # subprocess.run([ffmpeg_path, "-y", "-hide_banner", "-loglevel", "level+info", "-i", url, "-c:v", "copy", "-c:a", "copy", tmpfn], check=True)
    proc = subprocess.Popen([ffmpeg_path, "-y", "-hide_banner", "-loglevel", "level+info", "-i", url, "-c:v", "copy", "-c:a", "copy", tmpfn], stderr=subprocess.PIPE)

    need_linebreak = False
    while True:
        line_raw = proc.stderr.readline()
        if not line_raw:
            break
        line = line_raw.decode().rstrip("\r\n")
        for l in line.split("\r"):
            # sys.stderr.write("[info] %s\n"%repr(l))
            if info_pat.search(l):
                if info_pat.match(l):
                    if frame_pat.match(l):
                        time_match = time_pat.search(l)
                        playtime_sec = (int(time_match.group(1))*60+int(time_match.group(2)))*60+float(time_match.group(3))
                        sys.stderr.write("[ffmpeg %0.1f%%] %s\r"%((100*playtime_sec)/duration_sec, l))
                        # todo: playtime / duration 
                        
                        need_linebreak = True
                    else:
                        if need_linebreak:
                            sys.stderr.write("\n")
                            need_linebreak = False
                        sys.stderr.write("[ffmpeg] %s\n"%l)
                else:
                    continue
            else:
                if need_linebreak:
                    sys.stderr.write("\n")
                    need_linebreak = False
                sys.stderr.write("[ffmpeg] %s\n"%l)
    proc.wait()

    time.sleep(5)
    ## todo
    shutil.move(tmpfn, outfn)


res_pat=re.compile("(\\d+)p")
sysmes_url_pat = re.compile("動画の読み込みを開始しました。（(.+?)）")
sysmes_format_pat = re.compile("動画視聴セッションの作成に成功しました。（(.*?), archive_(.*?), archive_(.*?)）")
def get_hls_url(driver, url):

    sys.stderr.write("[info] opening page\n")
    driver.get(url)

    sys.stderr.write("[info] click_control\n")
    click_control(driver)

    sys.stderr.write("[info] sleep\n")
    time.sleep(3)

    sys.stderr.write("[info] get_quality = %s\n" % get_quality(driver))

    sys.stderr.write("[info] quality_menu\n")
    quality_menu(driver)

    sys.stderr.write("[info] sleep\n")
    time.sleep(3)

    sys.stderr.write("[info] list_quality_items\n")
    quality_items = list(list_quality_items(driver))
    sys.stderr.write("[info] quality=%s\n" % ",".join(quality_items))


    if mode=="best":
        selected_res = 0
        q_idx = -1
        for i in range(len(quality_items)):
            quality_item = quality_items[i]
            res_match = res_pat.match(quality_item)
            if res_match:
                res = int(res_match.group(1))
                # sys.stderr.write("[info] res[%s]=%s\n" % (i, res) )
                if selected_res < res:
                    selected_res = res
                    q_idx = i

    elif mode=="low":
        q_idx = -1
        for i in range(len(quality_items)):
            if "低画質" == quality_items[i]:
                q_idx = i
                break

    if q_idx == -1:
        raise Exception("quality not selected")
    sys.stderr.write("[info] selected_quality = %s\n" % quality_items[q_idx])
    # todo: select quality

    sys.stderr.write("[info] set_quality\n")
    set_quality(driver, q_idx)

    sys.stderr.write("[info] sleep\n")
    time.sleep(3)

    sys.stderr.write("[info] get_quality = %s\n" % get_quality(driver))
    
    sys.stderr.write("[info] system_message\n")
    sysmes = system_message(driver)
    sys.stderr.write("[info] sysmes=%s\n" % str_abbreviate(repr(sysmes)))

    sys.stderr.write("[info] url pattern match\n")
    url = list(sysmes_url_pat.finditer(sysmes))[-1].group(1)
    format_match = list(sysmes_format_pat.finditer(sysmes))[-1]
    format_id_video = format_match.group(2)
    format_id_audio = format_match.group(3)

    if mode=="best" and "low" in format_id_video:
        raise Exception("low is selected unexpectedly: %s" % format_match.group(0))
    if mode=="low" and not "low" in format_id_video:
        raise Exception("low is not selected unexpectedly: %s" % format_match.group(0))

    duration = get_duration(driver).split(":")
    duration_sec = int(duration[0])*60 + int(duration[1])

    return {"url": url, "format_id_video": format_id_video, "format_id_audio": format_id_audio, "duration": duration_sec}


def wait_noneco():
    datetime_now = datetime.datetime.now()
    if datetime_now.hour in range(0, 3):
        wake_time = datetime.datetime(year=datetime_now.year, month=datetime_now.month, day=datetime_now.day, hour=3)
        sleep_duration = (wake_time - datetime_now).total_seconds()
        sys.stderr.write("[info] sleep until %s\n" % wake_time)
        time.sleep(sleep_duration)
    elif (datetime_now.hour in range(18, 25) ) or (datetime_now.weekday() in [5,6] and datetime_now.hour in range(12, 18) ):
        wake_time = datetime.datetime(year=datetime_now.year, month=datetime_now.month, day=datetime_now.day, hour=3)
        wake_time += datetime.timedelta(days=1)
        sys.stderr.write("[info] sleep until %s\n" % wake_time)
        sleep_duration = (wake_time - datetime_now).total_seconds()
        time.sleep(sleep_duration)

def wait_eco():
    datetime_now = datetime.datetime.now()
    if (datetime_now.weekday() in range(0,5) and datetime_now.hour in range(3, 18) ):
        wake_time = datetime.datetime(year=datetime_now.year, month=datetime_now.month, day=datetime_now.day, hour=18)
        sleep_duration = (wake_time - datetime_now).total_seconds()
        sys.stderr.write("[info] sleep until %s\n" % wake_time)
        time.sleep(sleep_duration)
    elif (datetime_now.weekday() in [5,6] and datetime_now.hour in range(3, 12) ):
        wake_time = datetime.datetime(year=datetime_now.year, month=datetime_now.month, day=datetime_now.day, hour=12)
        sys.stderr.write("[info] sleep until %s\n" % wake_time)
        sleep_duration = (wake_time - datetime_now).total_seconds()
        time.sleep(sleep_duration)

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

        yield {'href': href, 'title': title, 'purchase_type': purchase_type}

    

def nicoch_get(chname):
    sess = requests.session()
    page = 1    
    while True:
        links = list(nicoch_get_page(sess, chname, page))
        for link in links:
            yield link
        if len(links)<20:
            break
        page += 1

def main():

    nico_user = os.environ["NICO_USER"]
    nico_password = os.environ["NICO_PASSWORD"]
    nico_channel = os.environ["NICO_CHANNEL"]

    url_pat = re.compile('https://www.nicovideo.jp/watch/(.+)')

    sys.stderr.write("[info] init_driver\n")
    driver = init_driver()

    sys.stderr.write("[info] nico_login\n")
    nico_login(driver, nico_user, nico_password)

    # os.chdir(mode)
    os.chdir("test")
    for link in nicoch_get(nico_channel):

        if mode=="best":
            wait_noneco()
        if mode=="low":
            wait_eco()

        url_match = url_pat.match(link["href"])
        watch_id = url_match.group(1)

        purchase_type = link["purchase_type"]
        if not link["purchase_type"] in ['free_for_member', 'member_unlimited_access']:
            sys.stderr.write("[info] skipping %s since purchase_type=%s\n" % (watch_id, purchase_type))
            continue

        glob_result = glob.glob("./%s_*_*.mkv" % (watch_id))
        if glob_result:
            sys.stderr.write("[Info] skipping %s since it is downloaded before\n" % watch_id)
            continue

        sys.stderr.write("[info] get_hls_url %s\n" % watch_id)
        hls_url = get_hls_url(driver, link["href"])
        sys.stderr.write("[info] hls_url=%s\n" % hls_url)
        format_id = "%s_%s" % (hls_url["format_id_video"].replace("_","-"), hls_url["format_id_video"].replace("_", "-")) 

        sys.stderr.write("[info] download_hls\n")
        download_hls(hls_url["url"], "%s_%s_%s.mkv" % (watch_id, valid_fn(link["title"]), format_id), hls_url["duration"])
        # todo error handling

    # driver.close()
    # driver.quit()


if __name__ == '__main__':
    main()