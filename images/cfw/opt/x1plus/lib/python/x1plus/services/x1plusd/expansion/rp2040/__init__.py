import time
import os
import logging
import struct

import usb

from ..device import ExpansionDevice
from ..smsc9514 import Smsc9514

from .rp2040boot import Rp2040Boot
from .ledstrip import LedStripDriver

logger = logging.getLogger(__name__)

class Rp2040ExpansionDevice(ExpansionDevice):
    PORTS = {
        0: { 0:  5, 1:  4, 2:  4, 3:  2, 4: 29, 5: 35, 6:  1, 7:  0 },
        1: { 0: 11, 1: 10, 2:  9, 3:  8, 4: 28, 5: 36, 6:  7, 7:  6 },
        2: { 0: 17, 1: 16, 2: 15, 3: 14, 4: 27, 5: 34, 6: 13, 7: 12 },
        3: { 0: 23, 1: 22, 2: 21, 3: 20, 4: 26, 5: 37, 6: 19, 7: 18 },
    }

    DRIVERS = { 'ledstrip': LedStripDriver }
    
    needs_reset_to_reopen = False

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
            logger.warning("found a LAN9514, but it does not appear to be an X1P-002-C, so we will not even try resetting an attached RP2040")
            return None
    
        smsc = Smsc9514()
    
        return Rp2040ExpansionDevice(revision = revision, serial = serial, smsc = smsc)
        
    def __init__(self, revision, serial, smsc):
        self.revision = revision
        self.serial = serial
        self.smsc = smsc
        self.nports = 0
        
        self.reset()

        super().__init__()

    def reset(self):
        self.rp2040 = None
        self.nports = 0
        self.gpio_last_read_time = 0
        self.gpio_last_read_data = 0

        # boot the RP2040...
        self.smsc.rp2040_reset()
        for attempt in range(5, -1, -1):
            try:
                boot = Rp2040Boot()
                boot.bootbin(os.path.join(os.path.dirname(__file__), "x1p_002_c_fw.bin"))
                break
            except Exception as e:
                logger.info(f"failed to boot RP2040: {e}")
                if attempt == 0:
                    logger.error(f"failed to boot RP2040 after 5 attempts: {e}")
                    # leave nports as 0, and give up
                    return
                time.sleep(0.2)
        
        # ...then attach to it
        def is_expander_rp2040(dev):
            try:
                return dev.idVendor == 0x2E8A and dev.idProduct == 0x000A and dev.manufacturer == "X1Plus" and dev.product == "X1Plus Expander GPIO controller"
            except:
                return False

        for attempt in range(5):
            self.rp2040 = usb.core.find(custom_match = is_expander_rp2040)
            if self.rp2040:
                break
            time.sleep(0.2)
        
        if not self.rp2040:
            logger.error("RP2040 never woke up into X1Plus firmware?")
            return

        self.rp2040.set_configuration()
        self.intf = self.rp2040[0][(0, 0)]
        self.ep_out = self.intf[0]
        self.ep_in  = self.intf[1]

        self.nports = len(self.PORTS)

    def _i2c_read(self, scl, sda, addr, dlen):
        self.ep_out.write(struct.pack('<BBB', 4, scl, sda))
        self.ep_out.write(struct.pack('<BBB', 1, addr, dlen))
        self.ep_out.write(struct.pack('<B', 0))
        
        buf = b""
        while len(buf) < (dlen + 1):
            buf += self.ep_in.read(0x100)
        if buf[0] != 0:
            raise IOError("I2C transaction failed")
        
        return buf[1:]

    def _i2c_write(self, scl, sda, addr, data):
        self.ep_out.write(struct.pack('<BBB', 4, scl, sda))
        self.ep_out.write(struct.pack('<BBB', 2, addr, len(data)) + data)
        self.ep_out.write(struct.pack('<B', 0))
        
        buf = b""
        while len(buf) < 1:
            buf += self.ep_in.read(0x100)
        if buf[0] != 0:
            raise IOError("I2C transaction failed")
    
    def _ws2812(self, pin, buf):
        self.ep_out.write(struct.pack('<BHB', 1, len(buf), pin))
        self.ep_out.write(buf)
    
    # do not actually submit a read more frequently than this: use the
    # cached result, if the system is polling multiple GPIOs in one polling
    # cycle
    READ_CACHE_INTERVAL_MS = 50

    def _gpio_read(self, pin):
        now = time.time()
        if (now - self.gpio_last_read_time) > (self.READ_CACHE_INTERVAL_MS / 1000.0):
            self.ep_out.write(b'\x05')
            buf = b""
            while len(buf) < 8:
                buf += self.ep_in.read(0x100)
            (self.gpio_last_read_data, ) = struct.unpack("<Q", buf)
        
        return ((self.gpio_last_read_data >> pin) & 1) == 1
    
    def _gpio_config(self, pin, pullup = False, pulldown = False, oe = False, data = False):
        cfg = ((1 if pullup else 0) |
               (2 if pulldown else 0) |
               (4 if oe else 0) |
               (8 if data else 0))
        self.ep_out.write(struct.pack('<BBB', 2, pin, cfg))

    def detect_eeprom(self, port):
        try:
            for i in range(8):
                self._gpio_config(self.PORTS[port][i], oe = False)
            i2c_params = (self.PORTS[port][7], self.PORTS[port][6], 0x50, )
            self._i2c_write(*i2c_params, b'\x00')
            eeprom_buf = self._i2c_read(*i2c_params, 0x80)
            eeprom_buf += self._i2c_read(*i2c_params, 0x80)
        except Exception as e:
            logger.warning(f"EEPROM detect on port {port} failed: {e}")
            return None
        return eeprom_buf
