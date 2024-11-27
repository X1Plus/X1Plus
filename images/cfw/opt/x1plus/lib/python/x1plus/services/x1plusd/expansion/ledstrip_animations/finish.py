"""
[led-animation]
name=finish
class_name=FinishAnimation
[end]
"""
import asyncio
import time
import math

class FinishAnimation():
    def __init__(self, leds, config):
        self.leds = leds
        self.brightness = config.get('brightness', 0.4)
        self.timeout = config.get('timeout', 600) # success goes away after 10 minutes
        self.last_finish_trn = 0
        self.last_was_finish = False
    
    def can_render(self):
        finish = self.leds.last_gcode_state == 'FINISH'
        if not self.last_was_finish and finish:
            self.last_finish_trn = time.time()
        self.last_was_finish = finish
        return finish and (time.time() - self.last_finish_trn) < self.timeout
    
    async def task(self):
        ph = 0

        while True:
            ph += 0.05
            br = 0.6 + math.sin(ph) * 0.4
            self.leds.put([int(255 * br * self.brightness), 0, 0] * self.leds.n_leds)
            await asyncio.sleep(0.05)