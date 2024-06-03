#!/opt/python/bin/python3
import json
import os
import sys

import x1plus.client.settings as settings

upd = {}
for arg in sys.argv[1:]:
    k,v = arg.split('=', 1)
    if v == 'None':
        v = None
    upd[k] = v

print(settings.put_multiple(upd))
print(settings.get_settings(force = True))
