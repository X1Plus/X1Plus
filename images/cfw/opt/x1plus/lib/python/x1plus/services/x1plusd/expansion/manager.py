import asyncio
from collections import namedtuple
import os
import logging
import time

import usb
import pyftdi.ftdi

from ..dbus import *

from .ft2232 import FtdiExpansionDevice
from .rp2040 import Rp2040ExpansionDevice

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
                    self.eeproms[port_name] = { 'model': model, 'revision': revision, 'serial': serial, 'raw': eeprom }
                    logger.info(f"{port_name}: detected {model} rev {revision}, serial #{serial}")
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
        await super().task()
    
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
            } if eeprom else None for port_name, eeprom in self.eeproms.items() },
        }
