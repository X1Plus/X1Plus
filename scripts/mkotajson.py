#!/usr/bin/env python3

import sys
import os
import json
import hashlib
import zipfile

with zipfile.ZipFile(sys.argv[1], 'r') as zf:
    with zf.open('info.json') as f:
        info = json.load(f)

# MD5sum our OTA file
ota_md5 = hashlib.md5(open(sys.argv[1], 'rb').read()).hexdigest()

# Generate OTA file
json.dump(
    {
        "cfwVersion": info['cfwVersion'],
        "date": info['date'],
        "buildTimestamp": info['buildTimestamp'],
        "notes": info['notes'],
        "ota_url": f"https://github.com/X1Plus/X1Plus/releases/download/x1plus%2F{info['cfwVersion']}/{info['cfwVersion']}.x1p",
        "ota_md5": ota_md5,
        "base_update_url": info['base']['updateUrl'],
        "base_update_md5": info['base']['updateMd5'],
    },
    open(sys.argv[2], "w"),
    indent = 4,
)
