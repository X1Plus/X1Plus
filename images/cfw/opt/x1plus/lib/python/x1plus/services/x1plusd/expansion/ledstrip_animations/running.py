"""
[led-animation]
name=running
class_name=RunningAnimation
[end]
"""
import asyncio
import math

class RunningAnimation():
    def __init__(self, leds, config):
        self.leds = leds
        self.brightness = config.get('brightness', 0.4)
        self.testmode = config.get('testmode', False)
    
    def can_render(self):
        return self.testmode or self.leds.last_gcode_state == 'RUNNING'
    
    async def task(self):
        ph = 0

        def put_print_progress(pct):
            nonlocal ph

            ph += 0.15
            pct += math.sin(ph) / (self.leds.n_leds * 6)

            npct = pct * self.leds.n_leds
            arr = []
            for i in range(self.leds.n_leds):
                if i == math.floor(npct):
                    arr += [self.brightness * (npct - i), 0, 1/255]
                elif i < npct:
                    arr += [self.brightness, 0, 1/255]
                else:
                    arr += [0, 0, 1/255]
            self.leds.put([int(a * 255) for a in arr])
    
        if self.testmode:
            for i in range(501):
                pct = i/500
                put_print_progress(pct)
                await asyncio.sleep(0.05)
        else:
            while True:
                put_print_progress(self.leds.daemon.mqtt.latest_print_status.get('mc_percent', 0) / 100)
                await asyncio.sleep(0.05)