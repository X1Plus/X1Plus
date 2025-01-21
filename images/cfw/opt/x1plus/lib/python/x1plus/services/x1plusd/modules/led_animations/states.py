"""
[X1PLUS_MODULE_INFO]
module:
  name: led_animation.states
  default_enabled: true
[END_X1PLUS_MODULE_INFO]
"""

import asyncio
import math
import time
import logging

from x1plus.services.x1plusd.expansion.ledstrip import register_animation

logger = logging.getLogger(__name__)

@register_animation("running")
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


@register_animation("paused")
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
 

@register_animation("finish")
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


@register_animation("failed")
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
