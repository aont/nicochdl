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


def click_control(driver):
    driver.find_element_by_css_selector("#js-app > div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer > div.ControllerBoxContainer > div.ControllerContainer > div > div:nth-child(3) > button.ActionButton.ControllerButton.PlayerOptionButton > div").click()

def quality_menu(driver):
    driver.find_element_by_css_selector("#js-app > div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer > div.WheelStopper > div > div > div > div:nth-child(1) > div.PlayerOptionMenuItem.VideoQualityMenuItem > div.PlayerOptionMenuItem-content > div > a > span.PlayerOptionDropdown-toggleLabel").click()

def list_quality_items(driver):
    elems = driver.find_elements_by_css_selector("#js-app > div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer > div.WheelStopper > div > div > div > div:nth-child(1) > div.PlayerOptionMenuItem.VideoQualityMenuItem > div.PlayerOptionMenuItem-content > div > div > div")
    for elem in elems:
        yield elem.text

def set_quality(driver, index):
    elems = driver.find_elements_by_css_selector("#js-app > div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer > div.WheelStopper > div > div > div > div:nth-child(1) > div.PlayerOptionMenuItem.VideoQualityMenuItem > div.PlayerOptionMenuItem-content > div > div > div")
    elems[index].click()

def get_quality(driver, expected_quality = None):
    while True:
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

def system_message(driver):
    canvas = driver.find_element_by_css_selector("#js-app > div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer > div.InView.VideoContainer > div.VideoSymbolContainer > canvas")
    driver.execute_script("var ev = document.createEvent('HTMLEvents'); ev.initEvent('contextmenu', true, false); arguments[0].dispatchEvent(ev);", canvas)
    driver.find_element_by_css_selector("#js-app > div > div.ContextMenu-wrapper > div > div > div:nth-child(1) > div:nth-child(3)").click()
    return driver.find_element_by_css_selector("#js-app > div > div.WatchAppContainer-main > div.MainContainer > div.MainContainer-player > div.PlayerContainer > div.InView.VideoContainer > div.SystemMessageContainer > div > div").text

def get_duration(driver):
    return driver.find_element_by_css_selector(".PlayerPlayTime-duration").text

# geckodriver_path = None
def init_driver():
    options = selenium.webdriver.firefox.options.Options()
    options.headless = False
    # executable_path=geckodriver_path,
    driver = selenium.webdriver.Firefox(options=options)
    screensize = get_screensize()
    winpos = (screensize[0] - 16, screensize[1] - 64)
    sys.stderr.write("[info] position=(%s,%s)\n" % winpos)
    driver.set_window_position(*winpos)
    # time.sleep(10)
    # sys.stderr.write("[info] %s\n" % driver.get_window_position())
    # sys.exit()
    return driver



def download_http(url, outfn, duration_sec, cookie, user_agent, http_referer):
    tmpfn = "tmp_%s.mp4" % os.getpid()
    # "-f", "mpegts"
    curl_cmd = [ "C:\\msys64\\usr\\bin\\curl.exe",
        "-A", user_agent,
        "-H", 'Origin: https://www.nicovideo.jp',
        "-H", "Referer: %s" % http_referer,
        "-H", "Cookie: %s" % cookie,
        "--continue-at", "-",
        url, "-o", tmpfn
    ]
    proc = subprocess.Popen(curl_cmd)
    proc.wait()
    if proc.returncode != 0:
        raise Exception("curl exited with code %d (0x%X)\ncmd:%s" % (proc.returncode, proc.returncode, curl_cmd))

    time.sleep(5)
    shutil.move(tmpfn, outfn)


res_pat=re.compile("(\\d+)p")
sysmes_url_pat = re.compile("動画の読み込みを開始しました。（(.+?)）")
sysmes_format_pat = re.compile("動画視聴セッションの作成に成功しました。（(.*?), archive_(.*?), archive_(.*?)）")
resrate_pat = re.compile("(\\d+)p \\| (.+?)M")
def get_video_url(driver, mode):
    sleep_time = 5

    sys.stderr.write("[info] click_control\n")
    click_control(driver)

    # sys.stderr.write("[info] sleep\n")
    # time.sleep(sleep_time)

    sys.stderr.write("[info] get_quality\n")
    sys.stderr.write("[info] quality = %s\n" % get_quality(driver))

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
        raise Exception("quality not selected")
    quality_selected = quality_items[q_idx]
    sys.stderr.write("[info] selected_quality = %s\n" % quality_selected)

    sys.stderr.write("[info] set_quality\n")
    set_quality(driver, q_idx)

    # sys.stderr.write("[info] sleep\n")
    # time.sleep(sleep_time)

    sys.stderr.write("[info] get_quality to confirm\n")
    sys.stderr.write("[info] quality = %s\n" % get_quality(driver, quality_selected))
    
    sys.stderr.write("[info] system_message\n")
    sysmes = system_message(driver)
    sys.stderr.write("[info] sysmes = %s\n" % str_abbreviate(repr(sysmes)))

    sys.stderr.write("[info] url pattern match\n")
    url = tuple(sysmes_url_pat.finditer(sysmes))[-1].group(1)
    format_match_ary = tuple(sysmes_format_pat.finditer(sysmes))
    if len(format_match_ary) > 0:
        return None
    format_id = quality_selected

    duration_str = get_duration(driver)
    duration = duration_str.split(":")
    duration_sec = int(duration[0])*60 + int(duration[1])

    return {"type": "http", "url": url, "format_id": format_id, "duration_str": duration_str, "duration_sec": duration_sec}

def get_nico_cookie_iter(cookies):
    for cookie in cookies:
        if cookie["domain"] == ".nicovideo.jp":
            yield "%s=%s" % (cookie["name"], cookie["value"])

def get_nico_cookie(cookies):
    return "; ".join(tuple(get_nico_cookie_iter(cookies)))

def main():
    
    mode = sys.argv[1]
    nico_user = os.environ["NICO_USER"]
    nico_password = os.environ["NICO_PASSWORD"]
    nico_channel = os.environ["NICO_CHANNEL"]

    url_pat = re.compile('https://www.nicovideo.jp/watch/(.+)')

    if mode not in ["best", "low"]:
        raise Exception("unexpected mode %s" % mode)

    outdir = "test_nonhls" # "hls_"+mode

    for link in [{"href": "https://www.nicovideo.jp/watch/1429212560"}]:

        url_match = url_pat.match(link["href"])
        watch_id = url_match.group(1)


        sleep_time = 60
        while True:
            try:

                sys.stderr.write("[info] init_driver\n")
                driver = init_driver()

                # sys.stderr.write("[info] nico_login\n")
                # nico_login(driver, nico_user, nico_password)

                sys.stderr.write("[info] opening %s\n" % watch_id)
                driver.get(link["href"])
        

                sys.stderr.write("[info] get_video_url %s\n" % watch_id)
                hls_url = get_video_url(driver, mode)
                sys.stderr.write("[info] url=%s\n" % hls_url)
                format_id = hls_url["format_id"]

                user_agent = driver.execute_script("return navigator.userAgent;")
                save_path = os.path.join(outdir, "%s_%s_%s.mp4" % (watch_id, "あなたの潜在能力を引き出す、意外な方法とは？", format_id))
                # sys.stderr.write("[info] cookie=%s\n" % json.dumps(driver.get_cookies(), indent=1, ensure_ascii=False))
                cookie = get_nico_cookie(driver.get_cookies())
                sys.stderr.write("[info] cookie=%s\n" % cookie)

                sys.stderr.write("[info] download_hls\n")
                download_http(hls_url["url"], save_path, hls_url["duration_sec"], cookie, user_agent, link["href"])

                sys.stderr.write("[info] quiting driver\n")
                # driver.close()
                # driver.quit()

                break

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
                # time.sleep(sleep_time)

                sleep_time *= 2
                continue


    # driver.close()
    # driver.quit()


if __name__ == '__main__':
    main()