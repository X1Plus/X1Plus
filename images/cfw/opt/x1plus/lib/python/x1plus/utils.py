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
    """Return the MAC address of the printer."""
    if is_emulating():
        return "CC:BD:D3:00:3B:D5"
    # Get the device id of the currently-active network device.
    devices = subprocess.Popen(["ip", "link"], stdout=subprocess.PIPE)
    # The active device _should_ be broadcasting.
    active = subprocess.run(
        ["grep", "BROADCAST"], stdin=devices.stdout, capture_output=True
    )
    identifier = active.stdout.decode().split(":")[1].strip()
    device = subprocess.Popen(["ip", "a", "s", identifier], stdout=subprocess.PIPE)
    # Should be "ether" even if it's a wireless device.
    ether = subprocess.run(["grep", "ether"], stdin=device.stdout, capture_output=True)
    return ether.stdout.decode().strip().split(" ")[1]


def get_IP() -> str:
    """Return the IP address of the printer."""
    if is_emulating():
        return "192.168.2.113"
    hostname = subprocess.run(["hostname", "-I"], capture_output=True)
    return hostname.stdout.decode().split(" ")[0]
