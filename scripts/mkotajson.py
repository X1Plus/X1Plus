#!/usr/bin/env python3

import os
import json
import hashlib

ROOTPATH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Load info.json
try:
    INFO = json.load(open(f"{ROOTPATH}/installer/info.json", "r"))
except Exception as e:
    print(f"Error loading info.json, has mkinfojson.sh ran yet?! Error of: {e}")
    raise

# MD5sum our OTA file
try:
    OTA_MD5 = hashlib.md5(open(f"{ROOTPATH}/{INFO['cfwVersion']}.x1p",'rb').read()).hexdigest()
except Exception as e:
    print(f"Error loading {INFO.cfwVersion}.x1p, did the x1p build correctly?! Error of: {e}")
    raise

# Generate OTA file
json.dump(
    {
        "cfwVersion": INFO['cfwVersion'],
        "date": INFO['date'],
        "buildTimestamp": INFO['buildTimestamp'],
        "notes": INFO['notes'],
        "ota_url": f"https://github.com/X1Plus/X1Plus/releases/download/x1plus%2F{INFO['cfwVersion']}/{INFO['cfwVersion']}.x1p",
        "ota_md5": OTA_MD5,
        "base_update_url": INFO['base']['updateUrl'],
        "base_update_md5": INFO['base']['updateMd5'],
    },
    open(f"{ROOTPATH}/ota.json", "w"),
    indent = 4,
)
