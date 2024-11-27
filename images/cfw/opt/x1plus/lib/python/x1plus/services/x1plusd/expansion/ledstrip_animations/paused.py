"""
[led-animation]
name=paused
class_name=PausedAnimation
[end]
"""
import asyncio

class PausedAnimation():
    def __init__(self, leds, config):
        self.leds = leds
        self.brightness = config.get('brightness', 0.25)
    
    def can_render(self):
        return self.leds.last_gcode_state == 'PAUSE'
    
    async def task(self):
        BLINK_PATTERN = [(160, 250), (140, 700), (160, 250), (140, 700), (160, 250), (140, 3000)]
        while True:
            for on,off in BLINK_PATTERN:
                arr = []
                for i in range(self.leds.n_leds):
                    arr += (self.brightness * 0.7, self.brightness * 1.0, 0.0,)
                self.leds.put([int(a * 255) for a in arr])
                await asyncio.sleep(on / 1000.0)
                
                self.leds.put(b'\x00\x00\x00' * self.leds.n_leds)
                await asyncio.sleep(off / 1000.0)