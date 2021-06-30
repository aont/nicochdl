#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import re
import glob
import subprocess
import datetime
import json
import shutil


soid_fn_pat = re.compile('(so\\d+)_(.+)_(.+).mp4')
def list_soid_files(dirpath):
    for item in os.listdir(dirpath):
        filepath = os.path.join(dirpath, item)
        if os.path.isfile(filepath):
            soid_fn_match = soid_fn_pat.match(item)
            if soid_fn_match:
                soid = soid_fn_match.group(1)
                title = soid_fn_match.group(2)
                quality = soid_fn_match.group(3)
                yield (item, soid, title, quality)
        else:
            continue

def list_soid_files_sort(dirpath):
    sys.stderr.write("[info] fetching file list\n")
    files = tuple(list_soid_files(dirpath))
    return sorted(files, key=lambda x: x[1], reverse=True)


info_pat = re.compile(b"\\[info\\]")
frame_pat = re.compile(b"\\[info\\] frame")
warning_pat = re.compile(b"\\[warning\\]")
error_pat = re.compile(b"\\[error\\]")
time_pat = re.compile(b"time=(.*?):(.*?):(.*?) ")
speed_pat = re.compile(b"speed=\\s*(.*?)x")
size_pat = re.compile(b"size=\\s*(.*?)\\s")
bitrate_pat = re.compile(b"bitrate=\\s*(.+?) ") 
def check_normality(target_path):
    ffmpeg_cmd = ( "ffmpeg",
        "-xerror",
        "-y", "-hide_banner",
        "-loglevel", "level+info",
        "-i", target_path, 
        "-c", "copy",
        "-f", "null",
        "NULL"
    )


    proc = subprocess.Popen(ffmpeg_cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    # proc = subprocess.Popen(ffmpeg_cmd, stderr=subprocess.PIPE)
    while True:
        line = proc.stderr.readline()
        if not line:
            break
        # line = line_raw.decode().rstrip("\r\n")
        line = line.rstrip(b"\r\n")
        for l in line.split(b"\r"):
            if error_pat.search(l):
                sys.stderr.buffer.write(l + b"\n")
                # sys.stderr.buffer.flush()
                proc.kill()
                # break
                # need_linebreak = True
            # elif frame_pat.match(l):
            #     # sys.stderr.buffer.write(l + b"\033[0K\r")
            #     sys.stderr.buffer.write(l + b"\n")
            #     # sys.stderr.buffer.flush()
    # sys.stderr.write("\n")

    # proc = subprocess.Popen(ffmpeg_cmd, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    # proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.DEVNULL)
    proc.wait()
    if proc.returncode != 0:
        return False
        # raise Exception("ffmpeg exited with code %d (0x%X)\ncmd:%s" % (proc.returncode, proc.returncode, ffmpeg_cmd))
    return True

def normality_test():

    if check_normality("somefile.mp4"):
        sys.stderr.write("normal\n")
    else:
        sys.stderr.write("abnormal\n")

# class DoOnExit:
#     def __init__(self, func, argv=()):
#         self.func = func
#         self.argv = argv
#     def __enter__(self):
#         return self
#     def __exit__(self, exc_type, exc_value, traceback):
#         self.func(*self.argv)

def main():
    normalityfn = "low_normality.json" # sys.argv[1]    
    if os.path.exists(normalityfn):
        with open(normalityfn, "rt", encoding="UTF-8") as f:
            normality_ary = json.load(f)
    else:
        normality_ary = []
        with open(normalityfn, "wt", encoding="UTF-8") as f:
            json.dump(normality_ary, f, ensure_ascii=False, indent=2)
    
    normality_backup_fn = normalityfn + ".bak"

    targetdir = "." # sys.argv[2]
    for target_fn, soid, title, quality in list_soid_files(targetdir):
        checked = False
        for checked_data in normality_ary:
            if checked_data["soid"] == soid:
                checked = True
                break
        if checked:
            sys.stderr.write("[info] skip %s\n" % soid)
            continue

        sys.stderr.write("[info] checking %s" % soid)
        sys.stderr.flush()
        target_path = os.path.join(targetdir, target_fn)
        normality = check_normality(target_path)
        if not normality:
            sys.stderr.write("\r\033[0K[warn] %s is abnormal\n" % soid)
            sys.stdout.write("%s\n" % soid)
        else:
            sys.stderr.write("\r\033[0K[info] %s is normal\n" % soid)

        normality_ary.append({
            "soid": soid,
            "filename": target_fn,
            "normal": normality,
        })

        shutil.move(normalityfn, normality_backup_fn)
        # complete_update = [False]
        # with DoOnExit(undo_move, (complete_update, normalityfn, normality_backup_fn)):
        with open(normalityfn, "wt", encoding="UTF-8") as f:
            json.dump(normality_ary, f, ensure_ascii=False, indent=2)
        # complete_update[0] = True

# def undo_move(complete_update, normalityfn, normality_backup_fn):
#     if not complete_update[0]:
#         shutil.move(normality_backup_fn, normalityfn)

if __name__ == '__main__':
    main()