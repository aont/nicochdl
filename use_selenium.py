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
import selenium
import selenium.webdriver.firefox.options
import selenium.webdriver


def get_screensize():
    import ctypes
    user32 = ctypes.windll.user32
    screensize = (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
    return screensize

def str_abbreviate(str_in):
    len_str_in = len(str_in)
    if len_str_in > 128*2+10:
        return str_in[0:128] + " ... " + str_in[-128:]
    else:
        return str_in

def valid_fn(fn):
    character_replace = { '\\': '＼', '/': '／', ':': '：', '?': '？', '\"': '”', '<': '＜', '>': '＞', '|': '｜', ' ': '_', '*': '＊', '+': '＋', '~': '～', '!': '！', }
    for key, value in character_replace.items():
        fn = fn.replace(key, value)
    return fn

def restore_cookie(driver, cookie_json_fn):
    if os.path.isfile(cookie_json_fn):
        # sys.stderr.write("[info] opening a page as a workaround for setting cookie\n")
        fp = open(cookie_json_fn, "r")
        cookies = json.load(fp)
        fp.close()
        driver.get("https://account.nicovideo.jp/login")
        for cookie in cookies:
            driver.add_cookie(cookie)

def nico_login(driver, mailtel, password):

    driver.get("https://account.nicovideo.jp/login")

    # login_anchor = driver.find_element_by_css_selector("#siteHeaderNotification > a")
    # login_anchor.click()

    mailtel_input = driver.find_element_by_id("input__mailtel")
    mailtel_input.send_keys(mailtel)
    password_input = driver.find_element_by_id("input__password")
    password_input.send_keys(password)

    login_button = driver.find_element_by_id("login__submit")
    login_button.click()

def save_cookie(cookie_json_fn):
    sys.stderr.write("[info] saveing cookies\n")
    fp = open(cookie_json_fn, "w")
    json.dump(driver.get_cookies() , fp)
    fp.close()

def check_need_login(driver):
    return "視聴するにはログインした後、動画を購入してください。" in driver.page_source

def check_login(driver):
    siteHeaderNotification = driver.find_element_by_id("siteHeaderNotification")
    return (siteHeaderNotification.text != "ログイン")

def pause_video(driver):
    # pause_button = driver.find_element_by_css_selector("#js-app > div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer > div.ControllerBoxContainer > div.ControllerContainer > div > div:nth-child(1) > button.ActionButton.ControllerButton.PlayerPauseButton")
    pause_button_ary = driver.find_elements_by_css_selector("#js-app > div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer > div.ControllerBoxContainer > div.ControllerContainer > div > div:nth-child(1) > button.ActionButton.ControllerButton.PlayerPauseButton")
    if len(pause_button_ary)==1:
        pause_button = pause_button_ary[0]
        pause_button.click()
    elif len(pause_button_ary)>1:
        raise Exception("Too many pause buttons found")

def click_control(driver):
    driver.find_element_by_css_selector("#js-app > div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer > div.ControllerBoxContainer > div.ControllerContainer > div > div:nth-child(3) > button.ActionButton.ControllerButton.PlayerOptionButton > div").click()

def quality_menu(driver):
    driver.find_element_by_css_selector("#js-app > div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer > div.VideoOverlayContainer > div > div.PlayerOptionContainer-wrapper > div > div > div > div:nth-child(1) > div.PlayerOptionMenuItem.VideoQualityMenuItem > div.PlayerOptionMenuItem-content > div > a > span.PlayerOptionDropdown-toggleArrow").click()

quality_item_css_selector = "#js-app > div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer > div.VideoOverlayContainer > div > div.PlayerOptionContainer-wrapper > div > div > div > div > div.PlayerOptionMenuItem.VideoQualityMenuItem > div.PlayerOptionMenuItem-content > div > div > div.PlayerOptionDropdownItem > div"
def list_quality_items(driver):
    elems = driver.find_elements_by_css_selector(quality_item_css_selector)
    # return elems
    # elems = driver.find_elements_by_css_selector("#js-app > div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer > div.WheelStopper > div > div > div > div:nth-child(1) > div.PlayerOptionMenuItem.VideoQualityMenuItem > div.PlayerOptionMenuItem-content > div > div > div")
    for elem in elems:
        yield elem.text

def set_quality(driver, index):
    elems = driver.find_elements_by_css_selector(quality_item_css_selector)
    # "#js-app > div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer > div.WheelStopper > div > div > div > div:nth-child(1) > div.PlayerOptionMenuItem.VideoQualityMenuItem > div.PlayerOptionMenuItem-content > div > div > div"
    elems[index].click()

def get_quality(driver, expected_quality = None):
    for t in range(10):
        quality_elem = driver.find_element_by_css_selector(".VideoQualityMenuItem > div:nth-child(2) > div:nth-child(1) > a:nth-child(1) > span:nth-child(1)")
        if not quality_elem:
            sys.stderr.write("[info] quality_elem is None. retrying\n")
            time.sleep(1)
            continue
        quality = quality_elem.text
        if ( not expected_quality and quality == "-" ) or ( expected_quality and quality != expected_quality ):
            sys.stderr.write("[info] quality is %s. retrying\n" % quality)
            time.sleep(1)
            continue
        else:
            return quality
    else:
        raise Exception("get_quality failed")

def system_message(driver):
    canvas = driver.find_element_by_css_selector("#js-app > div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer > div.InView.VideoContainer > div.VideoSymbolContainer > canvas")
    driver.execute_script("var ev = document.createEvent('HTMLEvents'); ev.initEvent('contextmenu', true, false); arguments[0].dispatchEvent(ev);", canvas)

    for menu_item in driver.find_elements_by_css_selector("#js-app > div > div.ContextMenu-wrapper > div > div > div:nth-child(1) > div"):
        if menu_item.text == "システムメッセージを開く":
            menu_item.click()
            break
    else:
        raise Exception("could not find menu item open-system-message")

    return driver.find_element_by_css_selector("#js-app > div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer > div.InView.VideoContainer > div.SystemMessageContainer > div > div").text

def get_videotitle(driver):
    return driver.find_element_by_css_selector(".VideoTitle").text

def get_duration(driver):
    return driver.find_element_by_css_selector(".PlayerPlayTime-duration").text

def get_description(driver):
    expand_button_ary = driver.find_elements_by_css_selector(".VideoDescriptionExpander-switchExpand")
    if len(expand_button_ary)==1:
        expand_button = expand_button_ary[0]
        expand_button.click()
    elif len(expand_button_ary)>1:
        raise Exception("Too many expand buttons")
    
    description_elems = driver.find_elements_by_css_selector(".VideoDescription-html")
    if len(description_elems)==0:
        return ""
    elif len(description_elems)==1:
        description_elem = description_elems[0]
        description_text = description_elem.text
        return description_text
    else:
        raise Exception("Too many description elements")


def get_nico_cookie_iter(cookies):
    for cookie in cookies:
        if cookie["domain"] == ".nicovideo.jp":
            yield "%s=%s" % (cookie["name"], cookie["value"])

def get_nico_cookie(cookies):
    return "; ".join(tuple(get_nico_cookie_iter(cookies)))

def init_driver():
    options = selenium.webdriver.firefox.options.Options()
    options.headless = False
    driver = selenium.webdriver.Firefox(options=options)
    screensize = get_screensize()
    winpos = (screensize[0] - 16, screensize[1] - 64)
    sys.stderr.write("[info] position=(%s,%s)\n" % winpos)
    driver.set_window_position(*winpos)
    return driver

tmpdir = "tmp"
curl_path = "curl.exe" # os.environ["CURL"]
def download_http(url, outfn, cookie, user_agent, http_referer, upload_date):
    tmpfn = os.path.join(tmpdir, "tmp_%s.mp4" % os.getpid())
    curl_cmd = [ curl_path,
        "-A", user_agent,
        "-H", 'Origin: https://www.nicovideo.jp',
        "-H", "Referer: %s" % http_referer,
        "-H", "Cookie: %s" % cookie,
        "--continue-at", "-",
        url, "-o", tmpfn
    ]

    while True:
        proc = subprocess.Popen(curl_cmd)
        proc.wait()
        if proc.returncode == 0: # OK
            break
        if proc.returncode == 18: # PARTIAL FILE
            continue
        else:
            raise Exception("curl exited with code %d (0x%X)\ncmd:%s" % (proc.returncode, proc.returncode, curl_cmd))

    time.sleep(5)
    shutil.move(tmpfn, outfn)
    upload_dt = datetime.datetime.strptime(upload_date, "%Y-%m-%d %H:%M")
    upload_ts = upload_dt.timestamp()
    os.utime(outfn, (upload_ts, upload_ts))


ffmpeg_path = "ffmpeg.exe" # os.environ["FFMPEG"]
info_pat = re.compile(b"\\[info\\]")
frame_pat = re.compile(b"\\[info\\] frame")
time_pat = re.compile(b"time=(.*?):(.*?):(.*?) ")
speed_pat = re.compile(b"speed=\\s*(.*?)x")
size_pat = re.compile(b"size=\\s*(.*?)\\s")
bitrate_pat = re.compile(b"bitrate=\\s*(.+?) ") 
# http_pat = re.compile("\\[http ")
# hls_pat = re.compile("\\[hls ")

def download_hls(url, outfn, videotitle, duration_sec, user_agent, http_referer, upload_date, description):
    tmpfn = os.path.join(tmpdir, "tmp_%s.mp4" % os.getpid())
    # "-f", "mpegts"
    ffmpeg_cmd = [ ffmpeg_path,
        "-user_agent", user_agent,
        "-headers", 'Origin: https://www.nicovideo.jp\r\n',
        "-headers", "Referer: %s\r\n" % http_referer,
        "-y", "-hide_banner", "-loglevel", "level+info",
        "-i", url, "-c:v", "copy", "-c:a", "copy",
        "-movflags", "faststart", "-bsf:a", "aac_adtstoasc",
        "-metadata", "title=%s" % videotitle,
        "-metadata", "creation_time=%s:00" % upload_date,
        "-metadata", "comment=%s" % description,
        tmpfn
    ]
    upload_dt = datetime.datetime.strptime(upload_date, "%Y-%m-%d %H:%M")
    upload_ts = upload_dt.timestamp()

    try:
        count = 0
        while True:
            proc = subprocess.Popen(ffmpeg_cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, stdin=subprocess.DEVNULL)

            need_linebreak = False
            
            duration_minsec = divmod(duration_sec, 60)
            # mes_len_prev = 0
            while True:
                line = proc.stderr.readline()
                if not line:
                    break
                # line = line_raw.decode().rstrip("\r\n")
                line = line.rstrip(b"\r\n")
                for l in line.split(b"\r"):
                    # sys.stderr.write("[info] %s\n"%repr(l))
                    if info_pat.search(l):
                        if info_pat.match(l):
                            if frame_pat.match(l):
                                # "frame=18660 fps=257 q=-1.0 Lsize=   38484kB time=00:10:22.01 bitrate= 506.8kbits/s speed=8.58x"
                                time_match = time_pat.search(l)
                                playtime_minsec = [int(time_match.group(1))*60+int(time_match.group(2)), float(time_match.group(3)) ]
                                playtime_sec = playtime_minsec[0]*60+playtime_minsec[1]

                                speed_match = speed_pat.search(l)
                                speed_str = speed_match.group(1).decode()
                                speed = float(speed_str)
                                if speed == 0:
                                    speed = 1e-5

                                size_match = size_pat.search(l)
                                size = size_match.group(1).decode()

                                bitrate_match = bitrate_pat.search(l)
                                bitrate_str = bitrate_match.group(1).decode()

                                remtime_sec = (duration_sec-playtime_sec)/speed
                                remtime_minsec = divmod(int(remtime_sec), 60)

                                mes = "[ffmpeg] " + " ".join(["progress=%0.1f%%"%((100*playtime_sec)/duration_sec), "time=%02d:%02.0f/%02d:%02d"%(*playtime_minsec,*duration_minsec), "size=%s"%size, "bitrate=%s"%bitrate_str, "speed=%sx"%speed_str, "remtime=%02d:%02d" % remtime_minsec])

                                # mes_len = len(mes)

                                # pad_len = mes_len_prev - mes_len
                                # mes_len_prev = mes_len

                                sys.stderr.write(mes + "\033[0K\r")
                                # if pad_len > 0:
                                #     sys.stderr.write(" "*pad_len)
                                # sys.stderr.write("\r")
                                
                                need_linebreak = True
                            else: # not progress info
                                if need_linebreak:
                                    sys.stderr.write("\n")
                                    need_linebreak = False
                                sys.stderr.buffer.write(b"[ffmpeg] " + l + b"\n")
                        else:
                            continue
                    else:
                        if need_linebreak:
                            sys.stderr.write("\n")
                            need_linebreak = False
                        sys.stderr.buffer.write(b"[ffmpeg] " + l + b"\n")
            if need_linebreak:
                sys.stderr.write("\n")
                need_linebreak = False
            proc.wait()
            if proc.returncode != 0:
                if count < 3:
                    sys.stderr.write("\n[warn] ffmpeg exited with code %d (0x%X). retrying\n" % (proc.returncode, proc.returncode))
                    time.sleep(10)
                    count += 1
                    continue
                else:
                    raise Exception("ffmpeg exited with code %d (0x%X)\ncmd:%s" % (proc.returncode, proc.returncode, ffmpeg_cmd))
            break

        time.sleep(5)
        shutil.move(tmpfn, outfn)
        os.utime(outfn, (upload_ts, upload_ts))

    except (Exception, KeyboardInterrupt) as e:
        if os.path.isfile(tmpfn):
            time.sleep(5)
            os.remove(tmpfn)
        raise e



res_pat=re.compile("(\\d+)p")
sysmes_url_pat = re.compile("動画の読み込みを開始しました。（(.+?)）")
sysmes_format_pat = re.compile("動画視聴セッションの作成に成功しました。（(.*?), archive_(.*?), archive_(.*?)）")
resrate_pat = re.compile("(\\d+)p \\| (.+?)M")
def get_download_url(driver, mode):

    # pause_video(driver)

    sleep_time = 5

    sys.stderr.write("[info] get_videotitle for sanity check\n")
    get_videotitle(driver)

    sys.stderr.write("[info] get_description\n")
    description_text = get_description(driver)
    sys.stderr.write("[info] description_text=%s\n" % str_abbreviate(repr(description_text)))

    sys.stderr.write("[info] click_control\n")
    click_control(driver)
    
    # sys.stderr.write("[info] sleep\n")
    # time.sleep(sleep_time)
    
    sys.stderr.write("[info] get_quality\n")
    quality_before = get_quality(driver)
    sys.stderr.write("[info] quality = %s\n" % quality_before)
    
    sys.stderr.write("[info] quality_menu\n")
    quality_menu(driver)
    
    sys.stderr.write("[info] list_quality_items\n")
    quality_items = tuple(list_quality_items(driver))
    sys.stderr.write("[info] quality=%s\n" % ",".join(quality_items))

    # sys.stderr.write("[info] sleep\n")
    # time.sleep(sleep_time)
    
    # sys.stderr.write("[info] list_quality_items\n")
    # quality_items = list(list_quality_items(driver))
    # sys.stderr.write("[info] quality=%s\n" % ",".join(quality_items))
    
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
            rate_min = 1e300
            for i in range(len(quality_items)):
                resrate_match = resrate_pat.match(quality_items[i])
                if not resrate_match:
                    continue
                rate = float(resrate_match.group(2))
                if rate < rate_min:
                    rate_min = rate
                    q_idx = i
    else:
        raise Exception("unknown mode %s" % mode)
    
    if q_idx == -1:
        quality_selected = quality_before
        # pass
    else:
        quality_selected = quality_items[q_idx]
        sys.stderr.write("[info] selected_quality = %s\n" % quality_selected)
        
        sys.stderr.write("[info] set_quality\n")
        set_quality(driver, q_idx)
        
        sys.stderr.write("[info] get_quality to confirm\n")
        sys.stderr.write("[info] quality = %s\n" % get_quality(driver, quality_selected))

    
    sys.stderr.write("[info] system_message\n")
    sysmes = system_message(driver)
    sys.stderr.write("[info] sysmes = %s\n" % str_abbreviate(repr(sysmes)))
    
    # sys.stderr.write("[info] url pattern match\n")
    url = tuple(sysmes_url_pat.finditer(sysmes))[-1].group(1)
    is_hls = ".m3u8" in url
    
    if is_hls:
        format_match_ary = tuple(sysmes_format_pat.finditer(sysmes))
        if len(format_match_ary) == 0:
            raise Exception("unexpected")
        format_match = format_match_ary[-1]
        format_id_video = format_match.group(2)
        format_id_audio = format_match.group(3)
        format_id = ("%s-%s" % (format_id_video, format_id_audio)).replace("_", "-")
    else:
        format_id = quality_selected
    
    if mode=="best" and "low" in format_id:
        raise Exception("low is selected unexpectedly: %s" % format_match.group(0))
    
    duration_str = get_duration(driver)
    duration = duration_str.split(":")
    duration_sec = int(duration[0])*60 + int(duration[1])

    # pause_video(driver)
    
    return {"is_hls": is_hls, "url": url, "format_id": format_id, "duration": duration_sec, "description": description_text}


def sleep_duration_noneco():
    datetime_now = datetime.datetime.now()
    if datetime_now.hour in range(0, 2):
        wake_time = datetime.datetime(year=datetime_now.year, month=datetime_now.month, day=datetime_now.day, hour=2)
        sleep_duration = (wake_time - datetime_now).total_seconds()
        return (sleep_duration, wake_time)
    elif (datetime_now.hour in range(18, 25) ) or (datetime_now.weekday() in [5,6] and datetime_now.hour in range(12, 18) ):
        wake_time = datetime.datetime(year=datetime_now.year, month=datetime_now.month, day=datetime_now.day, hour=2)
        wake_time += datetime.timedelta(days=1)
        sleep_duration = (wake_time - datetime_now).total_seconds()
        return (sleep_duration, wake_time)
    else:
        return (0, datetime_now)

def sleep_duration_eco():
    datetime_now = datetime.datetime.now()
    if (datetime_now.weekday() in range(0,5) and datetime_now.hour in range(2, 18) ):
        wake_time = datetime.datetime(year=datetime_now.year, month=datetime_now.month, day=datetime_now.day, hour=18)
        sleep_duration = (wake_time - datetime_now).total_seconds()
        return (sleep_duration, wake_time)
    elif (datetime_now.weekday() in [5,6] and datetime_now.hour in range(2, 12) ):
        wake_time = datetime.datetime(year=datetime_now.year, month=datetime_now.month, day=datetime_now.day, hour=12)
        sleep_duration = (wake_time - datetime_now).total_seconds()
        return (sleep_duration, wake_time)
    else:
        return (0, datetime_now)

def wait_noneco():
    sleep_duration, wake_time = sleep_duration_noneco()
    if sleep_duration > 0:
        sys.stderr.write("[info] sleep until %s\n" % wake_time)
        time.sleep(sleep_duration)

def wait_eco():
    sleep_duration, wake_time = sleep_duration_eco()
    if sleep_duration > 0:
        sys.stderr.write("[info] sleep until %s\n" % wake_time)
        time.sleep(sleep_duration)

url_pat = re.compile('https://www.nicovideo.jp/watch/(.+)')
def nicoch_get_page(sess, chname, pagenum):
    path = 'https://ch.nicovideo.jp/%s/video' % chname
    # links = []
    waiting_time = 60
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
            result.raise_for_status()
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
        mylist_count = item.find_class("mylist")[0].findall('.//var')[0].text
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

    nico_user = None # os.environ["NICO_USER"]
    nico_password = None # os.environ["NICO_PASSWORD"]
    nico_channel = sys.argv[1] # os.environ["NICO_CHANNEL"]
    mode = sys.argv[2]

    if mode not in ["best", "low"]:
        raise Exception("unexpected mode %s" % mode)

    outdir = mode

    os.makedirs(tmpdir, exist_ok=True)

    for link in nicoch_get(nico_channel):

        watch_id = link["watch_id"]

        purchase_type = link["purchase_type"]

        if purchase_type != "":
            sys.stderr.write("[info] skipping %s since purchase_type=%s\n" % (watch_id, purchase_type))
            continue

        # if not link["purchase_type"] in ['', 'free_for_member', 'member_unlimited_access']:
        #     sys.stderr.write("[info] skipping %s since purchase_type=%s\n" % (watch_id, purchase_type))
        #     continue

        glob_result = glob.glob("%s/%s_*_*.mp4" % (outdir, watch_id))
        if glob_result:
            sys.stderr.write("[info] skipping %s since it is downloaded before\n" % watch_id)
            continue

        sleep_time = 60
        while True:
            try:

                if mode=="best":
                    wait_noneco()
                if mode=="low":
                    wait_eco()
                    # pass

                sys.stderr.write("[info] init_driver\n")
                driver = init_driver()

                if nico_user:
                    sys.stderr.write("[info] nico_login\n")
                    nico_login(driver, nico_user, nico_password)

                fail_count = 0
                while True:
                    try:

                        if mode=="best":
                            if sleep_duration_noneco()[0]>0:
                                raise Exception("eco time")

                        sys.stderr.write("[info] opening %s\n" % watch_id)
                        driver.get(link["href"])

                        sys.stderr.write("[info] get_download_url %s\n" % watch_id)
                        url_info = get_download_url(driver, mode)
                        sys.stderr.write("[info] info: %s\n" % str_abbreviate(repr(url_info)))
                        format_id = url_info["format_id"]

                        pause_video(driver)

                        user_agent = driver.execute_script("return navigator.userAgent;")
                        save_path = os.path.join(outdir, "%s_%s_%s.mp4" % (watch_id, valid_fn(link["title"]), format_id))

                        if url_info["is_hls"]:
                            # sys.stderr.write("[debug] url_info=%s\n" % repr(url_info))
                            sys.stderr.write("[info] download_hls\n")
                            download_hls(url_info["url"], save_path, link["title"], url_info["duration"], user_agent, link["href"], link["upload_date"], url_info["description"])
                            break
                        else:
                            cookie = get_nico_cookie(driver.get_cookies())
                            sys.stderr.write("[info] download_http\n")
                            download_http(url_info["url"], save_path, cookie,user_agent, link["href"], link["upload_date"])
                            break
                    except KeyboardInterrupt as e:
                        raise e
                    except Exception as e:
                        fail_count += 1
                        if fail_count > 3:
                            raise e
                        sys.stderr.write(traceback.format_exc())

            except KeyboardInterrupt as e:
                raise e
            except Exception as e:
                exc_tb = traceback.format_exc()
                sys.stderr.write("[Exception]\n")
                sys.stderr.write(exc_tb)

                sys.stderr.write("[info] quiting driver\n")
                driver.close()
                driver.quit()

                sys.stderr.write("[info] retry after %ss sleep\n" % sleep_time)
                time.sleep(sleep_time)

                sleep_time *= 2
                if sleep_time > 60*10:
                    sleep_time = 60*10
                continue

            else:
                sys.stderr.write("[info] quiting driver\n")
                driver.close()
                driver.quit()
                break


    # driver.close()
    # driver.quit()


if __name__ == '__main__':
    main()