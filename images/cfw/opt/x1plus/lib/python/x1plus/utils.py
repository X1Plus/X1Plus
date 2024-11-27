import subprocess
from functools import lru_cache
import os
import re
import importlib
import logging, logging.handlers

logger = logging.getLogger(__name__)

@lru_cache(None)
def is_emulating():
    return not os.path.exists("/etc/bblap")


@lru_cache(None)
def serial_number():
    """
    Used to get the Serial Number for the Printer
    """
    if is_emulating():
        return "A00000000000"

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


def module_loader(filepath, package_name):
    """Return imported module from provided package and filepath, or None"""
    module_name = os.path.splitext(os.path.basename(filepath))[0]
    try:
        module = importlib.import_module(f"{package_name}.{module_name}")
    except Exception as e:
        return None, None
    return module, module_name

def module_docstring_parser(filepath: str, loader_type: str) -> dict:
    """Return dict for docstring values matching in a pre-defined block"""
    content = None
    config = {}
    try:
        with open(filepath, 'r') as file:
            content = file.read()
    except Exception as e:
        logger.warn(f"Could not load {filepath} in {loader_type} loader. {e.__class__.__name__}: {e}")
        return config
    
    docstring_match = re.match(r"^([\"']{3})(.*?)\1", content, re.DOTALL)
    if not docstring_match:
        logger.debug(f"No docstring found for {filepath} for {loader_type} loader")
        return config
    
    docstring = docstring_match.group(2).strip()
    definition_block_match = re.search(rf"\[{re.escape(loader_type)}\](.*?)\[end\]", docstring, re.DOTALL)
    if not definition_block_match:
        logger.debug(f"Could not find module definition in docstring for {filepath} for {loader_type} loader")
        return config

    definition_block = definition_block_match.group(1).strip()
    for line in definition_block.splitlines():
        if "=" in line:
            key, val = map(str.strip, line.split("=", 1))
            config[key] = val
    return config