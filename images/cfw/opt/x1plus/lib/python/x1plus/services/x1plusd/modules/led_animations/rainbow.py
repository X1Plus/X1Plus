"""
[X1PLUS_MODULE_INFO]
module:
  name: led_animation.rainbow
  default_enabled: true
[END_X1PLUS_MODULE_INFO]
"""

import asyncio
import colorsys

import logging

from x1plus.services.x1plusd.expansion.ledstrip import register_animation

logger = logging.getLogger(__name__)

@register_animation("rainbow")
class RainbowAnimation():
    def __init__(self, leds, config):
        self.leds = leds
        self.brightness = config.get('brightness', 0.3)
    
    def can_render(self):
        return True 
    
    async def task(self):
        ph = 0
        while True:
            ph = ph + 0.01
            arr = []
            for i in range(self.leds.n_leds):
                arr += colorsys.hsv_to_rgb((ph + i * 0.05) % 1, 1.0, 1.0)
            self.leds.put([int(a * self.brightness * 255) for a in arr])
            if ph > 1:
                ph -= 1
            await asyncio.sleep(0.05)
