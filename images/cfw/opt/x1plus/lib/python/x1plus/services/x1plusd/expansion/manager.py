import asyncio
from collections import namedtuple
import os
import logging
import time

import usb
import pyftdi.ftdi

from ..dbus import *

from .i2c import I2cDriver
from .ledstrip import LedStripDriver
from .detect_eeprom import detect_eeprom

# workaround for missing ldconfig
def find_library(lib):
    p = f"/usr/lib/{lib}.so"
    if os.path.exists(p):
        return p
import usb.backend.libusb1
usb.backend.libusb1.get_backend(find_library=find_library)

logger = logging.getLogger(__name__)

ExpansionDevice = namedtuple('ExpansionDevice', [ 'revision', 'serial', 'ftdidev' ])

def _detect_x1p_002_b01():
    """
    Looks for a X1P-002-B01.
    
    If it finds one, returns an ExpansionDevice.
    """
    
    lan9514_eth = usb.core.find(idVendor = 0x0424, idProduct = 0xec00)
    if not lan9514_eth:
        return None
    
    if lan9514_eth.product == 'Expansion Board X1P-002-B01':
        revision = lan9514_eth.product.split(' ')[2]
        serial = lan9514_eth.serial_number
    else:
        # Maybe it hasn't been serialized; I guess we will limp along in the
        # mean time, and hope that we can find a sibling FTDI.
        logger.warning("found a LAN9514, but it does not appear to be an X1P-002-B01?")
        revision = 'Unknown'
        serial = 'Unknown'
    
    # Look for a sibling FTDI device.
    ftdidev = usb.core.find(custom_match = lambda d: d.parent == lan9514_eth.parent, idVendor = 0x0403)
    if not ftdidev:
        logger.warning("found a LAN9514, but no FTDI sibling")
        return None
    
    # At least on X1P-002-B01, the FT2232 seems to sometimes get confused
    # about frequency when reopened.  Resetting it seems to make it happier. 
    # XXX: what causes this -- would a driver reload trigger this too?
    ftdidev.reset()
    
    return ExpansionDevice(revision = revision, serial = serial, ftdidev = ftdidev)

EXPANSION_INTERFACE = "x1plus.expansion"
EXPANSION_PATH = "/x1plus/expansion"

class ExpansionManager(X1PlusDBusService):
    DRIVERS = { 'i2c': I2cDriver, 'ledstrip': LedStripDriver }

    def __init__(self, daemon, **kwargs):
        self.daemon = daemon

        self.eeproms = {}
        self.drivers = {}
        self.ftdi_nports = 0
        self.ftdi_path = None
        self.last_configs = {}

        # We only have to look for an expansion board on boot, since it
        # can't be hot-installed.
        self.expansion = _detect_x1p_002_b01()
        if not self.expansion:
            logger.info("no X1Plus expansion board detected")
            super().__init__(
                dbus_interface=EXPANSION_INTERFACE, dbus_path=EXPANSION_PATH, **kwargs
            )
            return
        
        logger.info(f"found X1Plus expansion board serial {self.expansion.serial}")
        
        self.ftdi_path = f"ftdi://::{self.expansion.ftdidev.bus:x}:{self.expansion.ftdidev.address:x}/"
        if self.expansion.ftdidev.idProduct == 0x6010: # FT2232H
            self.ftdi_nports = 2
        else:
            self.ftdi_nports = 2
            logger.warning(f"FTDI product ID {self.expansion.ftdidev.idProduct:x} unrecognized")

        for port in range(self.ftdi_nports):
            port_name = f"port_{chr(0x61 + port)}"
            self.eeproms[port_name] = None
            eeprom = detect_eeprom(f"{self.ftdi_path}{port + 1}")
            if eeprom:
                try:
                    model, revision = eeprom[:16].decode().strip().rsplit('-', 1)
                    serial = eeprom[16:24].decode()
                    self.eeproms[port_name] = { 'model': model, 'revision': revision, 'serial': serial, 'raw': eeprom }
                    logger.info(f"{port_name}: detected {model} rev {revision}, serial #{serial}")
                except:
                    logger.error(f"error decoding EEPROM contents {eeprom} on {port_name}")
        
        for port in range(self.ftdi_nports):
            self.daemon.settings.on(f"expansion.port_{chr(0x61 + port)}", lambda: self._update_drivers())

        self.last_configs = {}

        super().__init__(
            dbus_interface=EXPANSION_INTERFACE, dbus_path=EXPANSION_PATH, **kwargs
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
        for port in range(self.ftdi_nports):
            port_name = f"port_{chr(0x61 + port)}"
            config = self.daemon.settings.get(f"expansion.{port_name}", None)
            if self.daemon.settings.get(f"expansion.{port_name}", None) != self.last_configs.get(port_name, None):
                did_change = True
                break
        
        if did_change:
            # shut down all ports...
            for port in range(self.ftdi_nports):
                port_name = f"port_{chr(0x61 + port)}"
                if port_name in self.drivers:
                    self.drivers[port_name].disconnect()
                    del self.drivers[port_name]
                
                if port_name in self.last_configs:
                    del self.last_configs[port_name]
            
            # reset the FTDI ...
            self.expansion.ftdidev.reset()

        for port in range(self.ftdi_nports):
            port_name = f"port_{chr(0x61 + port)}"
            config = self.daemon.settings.get(f"expansion.{port_name}", None)
            if not config:
                continue
            
            if self.last_configs.get(port_name, None) == config:
                # nothing has changed; do not reinitialize the port
                continue
            
            if type(config) != dict or len(config) != 1:
                logger.error(f"invalid configuration for {port_name}: configuration must be dictionary with exactly one key")
                continue
            
            if port_name in self.drivers:
                self.drivers[port_name].disconnect()
                del self.drivers[port_name]
            
            (driver, subconfig) = next(iter(config.items()))
            
            if driver not in self.DRIVERS:
                logger.error(f"{port_name} is assigned driver {driver}, which is not registered")
                continue
            
            try:
                self.drivers[port_name] = self.DRIVERS[driver](ftdi_path = f"{self.ftdi_path}{port + 1}", port_name = port_name, config = subconfig, daemon = self.daemon)
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
