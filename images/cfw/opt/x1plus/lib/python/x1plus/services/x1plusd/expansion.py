import os
import logging

from collections import namedtuple
import usb

# workaround for missing ldconfig
def find_library(lib):
    p = f"/usr/lib/{lib}.so"
    if os.path.exists(p):
        return p
import usb.backend.libusb1
usb.backend.libusb1.get_backend(find_library=find_library)

logger = logging.getLogger(__name__)

ExpansionDevice = namedtuple('ExpansionDevice', [ 'revision', 'serial', 'ftdidev' ])

def detect_x1p_002_b01():
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
    
    return ExpansionDevice(revision = revision, serial = serial, ftdidev = ftdidev)

class ExpansionManager():
    def __init__(self, settings, **kwargs):
        # We only have to look for an expansion board on boot, since it
        # can't be hot-installed.
        self.expansion = detect_x1p_002_b01()
        if not self.expansion:
            logger.info("no X1Plus expansion board detected")
            return
        
        logger.info(f"found X1Plus expansion board serial {self.expansion.serial}")
        
        self.ftdi_path = f"ftdi://::{self.expansion.ftdidev.bus:x}:{self.expansion.ftdidev.address:x}/"
        if self.expansion.ftdidev.idProduct == 0x6010: # FT2232H
            self.ftdi_nports = 2
        else:
            self.ftdi_nports = 2
            logger.warning(f"FTDI product ID {self.expansion.ftdidev.idProduct:x} unrecognized")

        # later: detect each port on the FTDI to determine if it has an
        # attached eeprom
        
        self.x1psettings = settings
        for port in range(self.ftdi_nports):
            self.x1psettings.on(f"expansion.port_{chr(0x61 + port)}", lambda: self._update_drivers())

        self.last_configs = {}
        self.drivers = {}
        self._update_drivers()
    
    def _update_drivers(self):
        for port in range(self.ftdi_nports):
            port_name = f"port_{chr(0x61 + port)}"
            config = self.x1psettings.get(f"expansion.{port_name}", None)
            if not config:
                continue
            
            if self.last_configs.get(port_name, None) == config:
                # nothing has changed; do not reinitialize the port
                continue
            
            if type(config) != dict or len(config) != 1:
                logger.error(f"invalid configuration for port {port_name}: configuration must be dictionary with exactly one key")
                continue
            
            if port_name in self.drivers:
                self.drivers[port_name].disconnect()
                del self.drivers[port_name]
            
            (driver, subconfig) = next(iter(config.items()))
            logger.info(f"would connect driver {driver} to {port_name}")
            
