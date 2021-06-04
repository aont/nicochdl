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


ffmpeg_path = "ffmpeg"
def make_custom(best_fn, low_fn, outfn):
    # tmpfn = "tmp_%s.mp4" % os.getpid()
    # "-f", "mpegts"
    ffmpeg_cmd = [ ffmpeg_path,
        "-y", "-hide_banner",
        # "-loglevel", "level+info",
        "-i", best_fn, "-i", low_fn,
        "-map", "1:v", "-map", "0:a",
        "-c:v", "copy", "-c:a", "copy",
        "-map_metadata", "0",
        # "-map_metadata:s:v", "1:s:v",
        # "-map_metadata:s:a", "0:s:a",
        "-f", "mp4",
        "-movflags", "faststart", "-bsf:a", "aac_adtstoasc",
        outfn
    ]
    proc = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.DEVNULL, stdin=subprocess.DEVNULL)

    proc.wait()
    if proc.returncode != 0:
        raise Exception("ffmpeg exited with code %d (0x%X)\ncmd:%s" % (proc.returncode, proc.returncode, ffmpeg_cmd))

    # time.sleep(5)
    # shutil.move(tmpfn, outfn)

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


def fixmtime(filepath):
    ffmpeg_cmd = ("ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", filepath)
    proc = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)
    json_text = proc.stdout.read()
    proc.wait()
    if proc.returncode != 0:
        raise Exception("ffmpeg exited with code %d (0x%X)\ncmd:%s" % (proc.returncode, proc.returncode, ffmpeg_cmd))

    metadata = json.loads(json_text)
    creation_time = metadata["format"]["tags"]["creation_time"]
    ts = datetime.datetime.strptime(creation_time, "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()
    # sys.stderr.write("%s %s %s\n" % (soid, creation_time, repr(ts)))
    os.utime(filepath, (ts, ts))

def main():
    basedir = "."
    best = "best"
    low = "low"
    custom = "custom"
    tmp_path = os.path.join(basedir, "tmp", "tmp_%s.mp4" % os.getpid())

    for best_fn, soid, title, quality in list_soid_files_sort(os.path.join(basedir, best)):
        best_path = os.path.join(basedir, best, best_fn)

        custom_glob_result = glob.glob(os.path.join(basedir, custom, "%s_*_*.mp4" % soid))
        if len(custom_glob_result)==1:
            sys.stderr.write("[info] skip %s (custom version found)\n" % soid)
            continue
        elif len(custom_glob_result)>1:
            raise Exception("%s: multiple custom version found" % soid)
        custom_path = os.path.join(basedir, custom, "%s_%s_custom.mp4" % (soid, title))

        low_glob_result = glob.glob(os.path.join(basedir, low, "%s_*_*.mp4" % soid))
        if len(low_glob_result)==0:
            sys.stderr.write("[warn] skip %s (low version not found)\n" % soid)
            continue
        elif len(low_glob_result)>1:
            raise Exception("%s: multiple low version found" % soid)
        
        low_path = low_glob_result[0]


        sys.stderr.write("[info] ffmpeg %s\n" % soid)
        make_custom(best_path, low_path, tmp_path)
        sys.stderr.write("[info] fixmtime %s\n" % soid)
        fixmtime(tmp_path)
        sys.stderr.write("[info] tmp to custom %s\n" % soid)
        shutil.move(tmp_path, custom_path)

if __name__ == '__main__':
    main()