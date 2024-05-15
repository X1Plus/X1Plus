#!/usr/bin/env python3

import os
import json
import subprocess
import datetime

ROOTPATH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

BASE = json.load(open(f"{ROOTPATH}/installer/base.json", "r"))

timestamp = datetime.datetime.now().timestamp()

try:
    rv = subprocess.run(["git", "describe", "--tags", "--match", "x1plus/*", "--abbrev=7", "--dirty"], capture_output=True, check=True, cwd=ROOTPATH)
    describe = rv.stdout.decode().strip().split('-')

    rv = subprocess.run(["git", "tag", "-l", describe[0], "--format=%(contents)"], capture_output=True, check=True, cwd=ROOTPATH)
    tagnotes = rv.stdout.decode().strip()
except subprocess.CalledProcessError as e:
    print(f"CalledProcessError had stdout {e.stdout}, stderr {e.stderr}, rv {e.returncode}")
    raise

if describe[-1] == 'dirty':
    # Dirty Build
    cfwVersion = f"{describe[-2]}-dirty" # This is not even a real version.  Who knows what this is.
    tagnotes = "Local testing build." 
    cfwdate = datetime.datetime.now().strftime("%Y-%m-%d")
elif len(describe) == 3:
    # Branch Build
    cfwVersion = f"{describe[0].split('/')[1]}-{describe[1]}+{describe[2]}"
    # date of the commit
    cfwdate = subprocess.run(["git", "log", "-1", describe[2][1:], "--format=%as"], capture_output=True, check=True, cwd=ROOTPATH).stdout.decode().strip()
else:
    # Tagged Build
    cfwVersion = describe[0].split('/')[1] 
    # date of the tag
    cfwdate = subprocess.run(["git", "tag", "-l", describe[0], "--format=%(taggerdate:format:%Y-%m-%d)"], capture_output=True, check=True, cwd=ROOTPATH).stdout.decode().strip()

# Dump installer json for x1p
json.dump(
    {
        "cfwVersion": cfwVersion,
        "date": cfwdate,
        "buildTimestamp": timestamp,
        "notes": tagnotes,
        "base": BASE
    },
    open(f"{ROOTPATH}/installer/info.json", "w"), indent = 4)
