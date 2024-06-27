# workaround for missing ldconfig
import os
def find_library(lib):
    p = f"/usr/lib/{lib}.so"
    if os.path.exists(p):
        return p
import usb.backend.libusb1
usb.backend.libusb1.get_backend(find_library=find_library)

import pyftdi.spi
import struct
import colorsys
import time

spi = pyftdi.spi.SpiController()

_ZERO = bytearray([0b11100000])
_ONE  = bytearray([0b11111000])

bytelut = {}
for i in range(256):
    v = bytearray()
    for j in range(7, -1, -1):
        if ((i >> j) & 1) == 0:
            v += _ZERO
        else:
            v += _ONE
    bytelut[i] = v

def put(bs):
    obs = bytearray(b'').join([bytelut[b] for b in bs])
    spi.exchange(6000000, obs, readlen=0)

def write_neopixel(pxls):
    buf = [0x0E, 0x04, 0x00, 0x00] # write to buf offset 0
    for pxl in pxls:
        buf.append(int(pxl * 255))
    slv.write(buf)
    slv.write((0x0E, 0x05)) # show

import os
import asyncio

import math
import x1plus.utils
from .dbus import *

logger = logging.getLogger(__name__)

NPXL_INTERFACE = "x1plus.npxl"
NPXL_PATH = "/x1plus/npxl"

N_LEDS = 10

async def colorcycle():
    # GRB
    ph = 0
    while True:
        ph = ph + 0.01
        arr = []
        for i in range(N_LEDS):
            arr += colorsys.hsv_to_rgb((ph + i * 0.05) % 1, 1.0, 1.0)
        put([int(a * 0.2 * 255) for a in arr])
        if ph > 1:
            ph -= 1
        await asyncio.sleep(0.03)

async def print_progress():
    def put_print_progress(pct):
        npct = pct * N_LEDS
        arr = []
        for i in range(N_LEDS):
            if i == math.floor(npct):
                arr += [0.2 * (npct - i), 0, 0]
            elif i < npct:
                arr += [0.2, 0, 0]
            else:
                arr += [0, 0, 0]
        put([int(a * 255) for a in arr])
    
    for i in range(501):
        pct = i/500
        put_print_progress(pct)
        if i == 300:
            for j in range(3):
                put([0, 0, 0] * N_LEDS)
                await asyncio.sleep(1)
                
                put([40, 50, 0] * N_LEDS)
                await asyncio.sleep(0.5)
                put([0, 0, 0] * N_LEDS)
                await asyncio.sleep(0.5)
                
                put([40, 50, 0] * N_LEDS)
                await asyncio.sleep(0.7)
                put([0, 0, 0] * N_LEDS)
                await asyncio.sleep(0.2)
                
                await asyncio.sleep(0.5)
                
        await asyncio.sleep(0.03)

async def white():
    put([50, 50, 50] * N_LEDS)

async def blank():
    put([0 for a in range(N_LEDS * 3)])

class NpxlService(X1PlusDBusService):
    def __init__(self, settings, **kwargs):
        self.cur_anim = None
        spi.configure('ftdi://ftdi:2232h/1', frequency=6000000)
        
        super().__init__(
            dbus_interface=NPXL_INTERFACE, dbus_path=NPXL_PATH, **kwargs
        )

    async def task(self):
        await super().task()
        
    async def dbus_Stop(self, req):
        if self.cur_anim:
            self.cur_anim.cancel()
            try:
                await self.cur_anim
            except asyncio.CancelledError:
                pass
            except Exception as e:
                import traceback
                traceback.print_exception(e)
            self.cur_anim = None
    
    async def dbus_Colorcycle(self, req):
        await self.dbus_Stop(req)
        self.cur_anim = asyncio.create_task(colorcycle())

    async def dbus_PrintProgress(self, req):
        await self.dbus_Stop(req)
        self.cur_anim = asyncio.create_task(print_progress())

    async def dbus_White(self, req):
        await self.dbus_Stop(req)
        await white()
    
    async def dbus_Blank(self, req):
        await self.dbus_Stop(req)
        await blank()


