"""
[led-animation]
name=failed
class_name=FailedAnimation
[end]
"""
import asyncio
import time

class FailedAnimation():
    def __init__(self, leds, config):
        self.leds = leds
        self.brightness = config.get('brightness', 0.25)
        self.timeout = config.get('timeout', 120) # failure goes away after 2 minutes
        self.last_failed_trn = 0
        self.last_was_failed = False
    
    def can_render(self):
        failed = self.leds.last_gcode_state == 'FAILED'
        if not self.last_was_failed and failed:
            self.last_failed_trn = time.time()
        self.last_was_failed = failed
        return failed and (time.time() - self.last_failed_trn) < self.timeout
    
    async def task(self):
        BLINK_PATTERN = [(750, 350), (750, 350), (750, 3000)]
        while True:
            for on,off in BLINK_PATTERN:
                arr = []
                for i in range(self.leds.n_leds):
                    arr += (0.0, self.brightness * 1.0, 0.0,)
                self.leds.put([int(a * 255) for a in arr])
                await asyncio.sleep(on / 1000.0)
                
                arr = []
                for i in range(self.leds.n_leds):
                    arr += (0.0, 1/255, 0.0,)
                self.leds.put([int(a * 255) for a in arr])
                await asyncio.sleep(off / 1000.0)