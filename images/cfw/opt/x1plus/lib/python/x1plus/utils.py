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
    return subprocess.check_output(["bbl_3dpsn"], stderr=subprocess.DEVNULL).decode(
        "utf-8"
    )


def get_MAC() -> str:
    """Return the MAC address of the wireless interface."""
    if is_emulating():
        return "CC:BD:D3:00:3B:D5"
    with open(f'/sys/class/net/wlan0/address', 'r') as file:
        mac_address = file.read().strip()
    return mac_address


def get_IP() -> str:
    """Return the IP address of the printer. This is currently on hold."""
    pass
    # if is_emulating():
    #     return "192.168.2.113"
    # hostname = subprocess.run(["hostname", "-I"], capture_output=True)
    # return hostname.stdout.decode().split(" ")[0]
