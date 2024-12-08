"""
[module]
enabled=true
[end]
"""
try:
    from x1plus.services.x1plusd.modules.expansion.ledstrip import register_animation
except ImportError:
    from ..expansion.ledstrip import register_animation

import asyncio
import colorsys

import logging

logger = logging.getLogger(__name__)
name = "rainbow"

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

@register_animation("rainbow")
def _animation_rainbow(handler):
    handler.ANIMATIONS.setdefault(name, RainbowAnimation)
