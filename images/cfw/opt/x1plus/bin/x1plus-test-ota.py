#!/opt/python/bin/python3
import json
import os
import sys

import x1plus.client.ota as ota

print(ota.check_now())
print(ota.get_status())
