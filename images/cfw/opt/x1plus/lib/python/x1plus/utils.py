import subprocess
from functools import lru_cache
import os


@lru_cache(None)
def is_emulating():
    return not os.path.exists("/etc/bblap")

@lru_cache(None)
def serial_number():
    """
    Used to get the Serial Number for the Printer
    """
    if os.path.isfile("/oem/device/sn"):
        return open("/oem/device/sn", "r").read()
    else:
        if os.system("bbl_3dpsn 2>/dev/null > /tmp/.bambu_sn") != 0:
            return open("/tmp/.bambu_sn", "r").read() 
    
@lru_cache(None)
def access_code():
    """
    Returns LAN access code needed for MQTT
    """
    if os.path.isfile("/config/device/access_token"):
        return open("/config/device/access_token", "r").read()
    return None
