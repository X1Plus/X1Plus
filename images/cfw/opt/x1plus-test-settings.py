#!/opt/python/bin/python3
import os, dds
import copy
from functools import lru_cache 
from threading import Thread
import json
import subprocess
import traceback
import time

# probably this should be encapsulated in a DDS class, but...

pub = dds.publisher("device/x1plus/request")
resp = dds.subscribe("device/x1plus/report")

time.sleep(3) # this really should instead use pub_matched_cb to know when we're ready to roll, but that's not exposed from dds.py yet

pub(json.dumps({"settings": { "set": {"hax": "very"} }}))

try:
    while True:
        print(resp.get())
except:
    dds.shutdown()
