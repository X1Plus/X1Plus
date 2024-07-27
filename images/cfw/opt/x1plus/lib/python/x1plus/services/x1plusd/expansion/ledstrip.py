import os
import logging
import asyncio

from collections import namedtuple

import pyftdi.spi

logger = logging.getLogger(__name__)

LedType = namedtuple('LedType', [ 'frequency', 'zero', 'one' ])

LED_TYPES = {
    'ws2812b': LedType(frequency = 6400000, zero = bytearray([0b11000000]), one = bytearray([0b11111100]))
}

class LedStripDriver():
    def __init__(self, daemon, config, ftdi_path):
        self.ftdi_path = ftdi_path
        self.config = config

        self.led = LED_TYPES[self.config.get('led_type', 'ws2812b')]
        self.n_leds = int(self.config['leds'])
        
        self.spi = pyftdi.spi.SpiController()
        self.spi.configure(ftdi_path, frequency = self.led.frequency)

        self.lut = {}
        for i in range(256):
            v = bytearray()
            for j in range(7, -1, -1):
                if ((i >> j) & 1) == 0:
                    v += self.led.zero
                else:
                    v += self.led.one
            self.lut[i] = v
        
        self.put(b'\x00\x00\x00' * self.n_leds)
        
        self.anim = asyncio.create_task(self.led_anim())

    def put(self, bs):
        obs = bytearray(b'').join([self.lut[b] for b in bs])
        self.spi.exchange(self.led.frequency, obs, readlen=0)
    
    def disconnect(self):
        self.anim.cancel()
        self.spi.close()
    
    async def led_anim(self):
        import colorsys
        ph = 0
        while True:
            ph = ph + 0.01
            arr = []
            for i in range(self.n_leds):
                arr += colorsys.hsv_to_rgb((ph + i * 0.05) % 1, 1.0, 1.0)
            self.put([int(a * 0.8 * 255) for a in arr])
            if ph > 1:
                ph -= 1
            await asyncio.sleep(0.05)
