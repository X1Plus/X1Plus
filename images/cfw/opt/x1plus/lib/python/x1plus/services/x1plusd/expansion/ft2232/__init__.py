import logging

import usb
import pyftdi.ftdi

from ..device import ExpansionDevice

from .i2c import I2cDriver
from .ledstrip import LedStripDriver
from .detect_eeprom import detect_eeprom

logger = logging.getLogger(__name__)

class FtdiExpansionDevice(ExpansionDevice):
    DRIVERS = { "i2c": I2cDriver, 'ledstrip': LedStripDriver }
    
    needs_reset_to_reopen = True

    @classmethod
    def detect(cls):
        """
        Looks for a X1P-002-B01.
    
        If it finds one, returns an ExpansionDevice.
        """
    
        # XXX: hoist this out to a find-and-verify-eeprom routine
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
    
        return FtdiExpansionDevice(revision = revision, serial = serial, ftdidev = ftdidev)
        
    def __init__(self, revision, serial, ftdidev):
        self.revision = revision
        self.serial = serial
        self.ftdidev = ftdidev
        self.is_authentic = False # X1P-002-A/B are non-supported devices

        # At least on X1P-002-B01, the FT2232 seems to sometimes get confused
        # about frequency when reopened.  Resetting it seems to make it happier. 
        # XXX: what causes this -- would a driver reload trigger this too?
        ftdidev.reset()
        
        self.ftdi_path = f"ftdi://::{ftdidev.bus:x}:{ftdidev.address:x}/"
        if ftdidev.idProduct == 0x6010: # FT2232H
            self.nports = 2
        else:
            self.nports = 2
            logger.warning(f"FTDI product ID {self.expansion.ftdidev.idProduct:x} unrecognized")
        super().__init__()

    def detect_eeprom(self, port):
        return detect_eeprom(f"{self.ftdi_path}{port + 1}")

    def reset(self):
        self.ftdidev.reset()
