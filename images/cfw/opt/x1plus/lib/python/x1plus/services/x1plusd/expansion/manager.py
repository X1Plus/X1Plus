import asyncio
from collections import namedtuple
import os
import re
import logging
import time

import usb
import pyftdi.ftdi

from ..dbus import *

from .ft2232 import FtdiExpansionDevice
from .rp2040 import Rp2040ExpansionDevice
from .authenticate import authenticate

# workaround for missing ldconfig
def find_library(lib):
    p = f"/usr/lib/{lib}.so"
    if os.path.exists(p):
        return p
import usb.backend.libusb1
usb.backend.libusb1.get_backend(find_library=find_library)

logger = logging.getLogger(__name__)

EXPANSION_INTERFACE = "x1plus.expansion"
EXPANSION_PATH = "/x1plus/expansion"

# Sysfs USB hub port → Expander port label
USB_PORT_MAP = {
    "1-1.2": "a",
    "1-1.3": "b",
}
USB_POLL_INTERVAL = 5


def _get_usb_drives():
    drives = []
    seen = set()
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 2:
                    continue
                device, mount_point = parts[0], parts[1]
                if not mount_point.startswith("/media/usb"):
                    continue
                if mount_point in seen:
                    continue
                seen.add(mount_point)
                dev_name = re.sub(r'\d+$', '', os.path.basename(device))
                try:
                    sysfs = os.path.realpath(f"/sys/block/{dev_name}")
                    m = re.search(r'/(1-1\.\d+)/', sysfs)
                    usb_port = m.group(1) if m else None
                except Exception:
                    usb_port = None
                drives.append({"path": mount_point, "port": USB_PORT_MAP.get(usb_port)})
    except Exception as e:
        logger.error(f"error reading USB drives: {e}")
    return drives

class ExpansionManager(X1PlusDBusService):
    def __init__(self, daemon, **kwargs):
        self.daemon = daemon

        self.eeproms = {}
        self.drivers = {}
        self.last_configs = {}

        # We only have to look for an expansion board on boot, since it
        # can't be hot-installed.
        self.expansion = Rp2040ExpansionDevice.detect()
        if not self.expansion:
            self.expansion = FtdiExpansionDevice.detect()
        if not self.expansion:
            logger.info("no X1Plus expansion board detected")
            super().__init__(
                dbus_interface=EXPANSION_INTERFACE, dbus_path=EXPANSION_PATH, router=daemon.router, **kwargs
            )
            return
        
        logger.info(f"found X1Plus expansion board serial {self.expansion.serial}")
        
        for port in range(self.expansion.nports):
            port_name = f"port_{chr(0x61 + port)}"
            self.eeproms[port_name] = None
            eeprom = self.expansion.detect_eeprom(port)
            if eeprom:
                try:
                    model, revision = eeprom[:16].decode().strip().rsplit('-', 1)
                    serial = eeprom[16:24].decode()
                    is_authentic = authenticate(eeprom)
                    self.eeproms[port_name] = { 'model': model, 'revision': revision, 'serial': serial, 'is_authentic': is_authentic, 'raw': eeprom }
                    logger.info(f"{port_name}: detected {model} rev {revision}, serial #{serial}, signature valid {is_authentic}")
                except:
                    logger.error(f"error decoding EEPROM contents {eeprom} on {port_name}")
        
        for port in range(self.expansion.nports):
            self.daemon.settings.on(f"expansion.port_{chr(0x61 + port)}", lambda: self._update_drivers())

        self.last_configs = {}

        super().__init__(
            dbus_interface=EXPANSION_INTERFACE, dbus_path=EXPANSION_PATH, router=daemon.router, **kwargs
        )

    async def task(self):
        self._update_drivers()
        self._usb_drives = []
        asyncio.create_task(self._poll_usb())
        await super().task()

    async def _poll_usb(self):
        while True:
            drives = _get_usb_drives()
            if drives != self._usb_drives:
                self._usb_drives = drives
                logger.info(f"USB drives changed: {drives}")
                await self.emit_signal("UsbDrivesChanged", drives)
            await asyncio.sleep(USB_POLL_INTERVAL)

    async def dbus_GetUsbDrives(self, req):
        return _get_usb_drives()
    
    def _update_drivers(self):
        if not self.expansion:
            return

        # Workaround https://github.com/eblot/pyftdi/issues/261 by resetting
        # all drivers on the FTDI every time.
        did_change = False
        for port in range(self.expansion.nports):
            port_name = f"port_{chr(0x61 + port)}"
            config = self.daemon.settings.get(f"expansion.{port_name}", None)
            if self.daemon.settings.get(f"expansion.{port_name}", None) != self.last_configs.get(port_name, None):
                did_change = True
                break
        
        if did_change:
            # shut down all ports...
            for port in range(self.expansion.nports):
                port_name = f"port_{chr(0x61 + port)}"
                if port_name in self.drivers:
                    self.drivers[port_name].disconnect()
                    del self.drivers[port_name]
                
                if port_name in self.last_configs:
                    del self.last_configs[port_name]
            
            # reset the FTDI ...
            if self.expansion.needs_reset_to_reopen:
                self.expansion.reset()

        for port in range(self.expansion.nports):
            port_name = f"port_{chr(0x61 + port)}"
            config = self.daemon.settings.get(f"expansion.{port_name}", None)
            if not config:
                continue
            
            if self.last_configs.get(port_name, None) == config:
                # nothing has changed; do not reinitialize the port
                continue
            
            if type(config) != dict:
                logger.error(f"invalid configuration for {port_name}: configuration must be dictionary with exactly one key")
                continue
            
            # ignore a "meta" key, where a UI can stash information about
            # config state; otherwise, the remaining key is a driver
            ckey = set(config.keys()) - {'meta'}
            if len(ckey) != 1:
                logger.error(f"invalid configuration for {port_name}: configuration must be dictionary with exactly one key")
                continue
            
            if port_name in self.drivers:
                self.drivers[port_name].disconnect()
                del self.drivers[port_name]
            
            driver = ckey.pop()
            subconfig = config[driver]
            
            if driver not in self.expansion.DRIVERS:
                logger.error(f"{port_name} is assigned driver {driver}, which is not valid for this Expander")
                continue
            
            try:
                self.drivers[port_name] = self.expansion.DRIVERS[driver](expansion = self.expansion, port = port, port_name = port_name, config = subconfig, daemon = self.daemon)
                self.last_configs[port_name] = config
            except Exception as e:
                logger.error(f"{port_name} driver {driver} initialization failed: {e.__class__.__name__}: {e}")
            
    async def dbus_GetHardware(self, req):
        if not self.expansion:
            return None
            
        return {
            'expansion_revision': self.expansion.revision,
            'expansion_serial': self.expansion.serial,
            'ports': { port_name: {
                'model': eeprom['model'],
                'revision': eeprom['revision'],
                'serial': eeprom['serial'],
                'is_authentic': eeprom['is_authentic'],
            } if eeprom else None for port_name, eeprom in self.eeproms.items() },
            'is_authentic': self.expansion.is_authentic,
        }
