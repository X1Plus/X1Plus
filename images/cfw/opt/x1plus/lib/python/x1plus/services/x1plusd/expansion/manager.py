import asyncio
from collections import namedtuple
import os
import re
import shutil
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

USB_POLL_INTERVAL = 2

# Get a raw mapping of all USB mounts.  Caller is responsible for demapping
# to marketing names.
def _get_usb_mounts():
    drives = []
    seen = set()

    with open("/proc/mounts") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue

            device, mount_point, fs = parts[0:3]
            if not mount_point.startswith("/media/usb"):
                continue
            if not device.startswith("/dev/"):
                continue
            if mount_point in seen:
                continue
            seen.add(mount_point)
            
            mount = {
                "mount_point": mount_point,
                "device": device,
                "filesystem": fs,
            }
            
            # see if we can look up what USB port it's on. 
            # /sys/class/block/x works for partitions also
            try:
                sysfs = os.path.realpath(f"/sys/class/block/{os.path.basename(device)}").split('/')
                
                # walk backwards in the path, finding the first thing
                # that looks like a USB function path.
                for sub in sysfs[::-1]:
                    if re.match(r'\d+-\d+(\.\d+)*:\d+.\d+', sub):
                        mount["usb_port"] = sub
                        break
            except Exception:
                # maybe it wasn't in sysfs after all
                pass
            
            # how much storage?
            try:
                usage = shutil.disk_usage(mount_point)
                mount['disk_size'] = usage.total
                mount['disk_used'] = usage.used
                mount['disk_free'] = usage.free
            except Exception:
                # maybe it's not mounted anymore
                pass
            
            drives.append(mount)

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
        self._usb = {"mounts": [], "devices": {}}
        asyncio.create_task(self._poll_usb())
        await super().task()

    async def _poll_usb(self):
        while True:
            mounts = _get_usb_mounts()
            
            # map drive USB ports (if present) to marketing names on
            # Expander
            if self.expansion:
                for drive in mounts:
                    if 'usb_port' in drive:
                        drive['usb_port'] = self.expansion.usb_port_id_to_name(drive['usb_port'].split(":")[0])

            # enumerate all USB devices connected to the Expander
            devices = {}
            if self.expansion:
                # first, mark all the ports in the port table -- even if
                # they're empty, they should show up in the UI as
                # unconnected
                for port,name in self.expansion.usb_port_map.items():
                    devices[name] = {}
                
                # now go looking for all USB devices.  if they are ports, or
                # children of ports, then put them in the device dictionary
                for dev in os.listdir("/sys/bus/usb/devices"):
                    if ':' in dev:
                        continue # this is a function, not a device
                    if not any(dev.startswith(port) for port in self.expansion.usb_port_map):
                        continue # this is a USB device that is not attached to Expander

                    name = self.expansion.usb_port_id_to_name(dev)
                    syspath = f"/sys/bus/usb/devices/{dev}"
                    devices[name] = {
                        "path": dev,
                        "vendor_id": open(f"{syspath}/idVendor", "r").read().strip(),
                        "product_id": open(f"{syspath}/idProduct", "r").read().strip(),
                        "manufacturer_string": open(f"{syspath}/manufacturer", "r").read().strip(),
                        "product_string": open(f"{syspath}/product", "r").read().strip(),
                    }
                    
                    # is there a configuration that we can read a driver from?
                    for subpath in os.listdir(syspath):
                        if os.path.exists(f"{syspath}/{subpath}/driver"):
                            devices[name]['driver'] = os.path.basename(os.path.realpath(f"{syspath}/{subpath}/driver"))
                    
            usb = { "mounts": mounts, "devices": devices }
            if usb != self._usb:
                self._usb = usb
                logger.info(f"USB status changed: {usb}")
                await self.emit_signal("UsbChanged", usb)
            
            await asyncio.sleep(USB_POLL_INTERVAL)

    async def dbus_GetUsb(self, req):
        return self._usb
    
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
