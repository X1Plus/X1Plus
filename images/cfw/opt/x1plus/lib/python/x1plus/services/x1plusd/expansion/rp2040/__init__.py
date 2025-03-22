import logging

import usb

from ..device import ExpansionDevice
from ..smsc9514 import Smsc9514

logger = logging.getLogger(__name__)

class Rp2040ExpansionDevice(ExpansionDevice):
    DRIVERS = { }

    @classmethod
    def detect(cls):
        """
        Looks for a X1P-002-C.
    
        If it finds one, returns an ExpansionDevice.
        """
    
        # XXX: hoist this out to a find-and-verify-eeprom routine
        lan9514_eth = usb.core.find(idVendor = 0x0424, idProduct = 0xec00)
        if not lan9514_eth:
            return None
    
        if lan9514_eth.product.startswith('Expansion Board X1P-002-C'):
            revision = lan9514_eth.product.split(' ')[2]
            serial = lan9514_eth.serial_number
        else:
            # Maybe it hasn't been serialized; I guess we will limp along in the
            # mean time, and hope that we can find a sibling FTDI.
            logger.warning("found a LAN9514, but it does not appear to be an X1P-002-C, so we will not even try resetting an attached RP2040")
            return None
    
        logger.warning("found an RP2040, but we don't know how to drive it yet")
        
        smsc = Smsc9514()
    
        return Rp2040ExpansionDevice(revision = revision, serial = serial, smsc = smsc)
        
    def __init__(self, revision, serial, smsc):
        self.revision = revision
        self.serial = serial
        self.smsc = smsc
        self.nports = 0
        
        self.reset()

        super().__init__()

    def detect_eeprom(self, port):
        return None

    def reset(self):
        self.smsc.rp2040_reset()
