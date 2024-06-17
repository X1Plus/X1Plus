import os
import asyncio

import x1plus.utils
from .dbus import *

import os
def find_library(lib):
    p = f"/usr/lib/{lib}.so"
    if os.path.exists(p):
        return p
import usb.backend.libusb1
usb.backend.libusb1.get_backend(find_library=find_library)

import pyftdi.i2c

CMD_MEASURE_HIGH_PRECISION = 0xFD
CMD_SERIAL_NUMBER = 0x89

import binascii

logger = logging.getLogger(__name__)

I2C_INTERFACE = "x1plus.i2c"
I2C_PATH = "/x1plus/i2c"

class I2cService(X1PlusDBusService):
    def __init__(self, settings, **kwargs):
        self.x1psettings = settings
        
        # reset the FTDI -- it gets confused
        from usb.core import find as finddev
        dev = finddev(idVendor=0x0403, idProduct=0x6010)
        dev.reset()
        
        self.i2c = pyftdi.i2c.I2cController()
        self.i2c.configure('ftdi://ftdi:2232h/2', frequency=50000)
        self.sht41 = self.i2c.get_port(0x44)
        
        super().__init__(
            dbus_interface=I2C_INTERFACE, dbus_path=I2C_PATH, **kwargs
        )

    async def task(self):
        await super().task()
    

    async def dbus_GetSht41(self, req):
        self.sht41.write((CMD_SERIAL_NUMBER, ))
        sn = self.sht41.read(readlen = 6)
        sn = binascii.hexlify(sn[0:2] + sn[3:5])

        self.sht41.write((CMD_MEASURE_HIGH_PRECISION, ))
        da = self.sht41.read(readlen = 6)
        t_raw = int.from_bytes(da[0:2], "big")
        rh_raw = int.from_bytes(da[3:5], "big")

        t_C = -45 + 175 * t_raw / 65535
        rh_pct = -6 + 125 * rh_raw/65535

        return { "t": t_C, "rh": rh_pct, "serial": sn.decode() }
