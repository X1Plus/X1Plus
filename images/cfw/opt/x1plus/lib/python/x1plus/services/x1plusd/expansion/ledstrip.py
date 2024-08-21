import os
import logging
import asyncio
import time

from collections import namedtuple

import pyftdi.spi

logger = logging.getLogger(__name__)

LedType = namedtuple('LedType', [ 'frequency', 'zero', 'one' ])

LED_TYPES = {
    'ws2812b': LedType(frequency = 6400000, zero = bytearray([0b11000000]), one = bytearray([0b11111100]))
}

class LedStripDriver():
    ANIMATIONS = {}
    DEFAULT_ANIMATIONS = [ 'running', 'finish', 'paused', 'failed', 'rainbow' ]

    def __init__(self, daemon, config, ftdi_path):
        self.daemon = daemon
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
        
        self.put(b'\x00\x00\x00' * 128) # clear out a long strip
        
        self.anim_task = None
        self.curanim = None

        # the 'animations' key is a list that looks like:
        #
        #   [ 'paused', { 'rainbow': { 'brightness': 0.5 } } ]
        self.anim_list = []
        for anim in self.config.get('animations', self.DEFAULT_ANIMATIONS):
            if type(anim) == str:
                self.anim_list.append(self.ANIMATIONS[anim](self, {}))
                continue
            elif type(anim) != dict or len(anim) != 1:
                raise ValueError("animation must be either string or dictionary with exactly one key")
            
            (animname, subconfig) = next(iter(anim.items()))
            self.anim_list.append(self.ANIMATIONS[animname](self, subconfig))

        self.last_gcode_state = None
        self.anim_watcher = asyncio.create_task(self.anim_watcher_task())
            
    def put(self, bs):
        obs = bytearray(b'').join([self.lut[b] for b in bs])
        self.spi.exchange(self.led.frequency, obs, readlen=0)
    
    def disconnect(self):
        if self.anim_task:
            self.anim_task.cancel()
            self.anim_task = None
        self.anim_watcher.cancel()
        self.spi.close()
    
    async def anim_watcher_task(self):
        with self.daemon.mqtt.report_messages() as report_queue:
            while True:
                msg = await report_queue.get()
                # we do not do anything with it, we just use this to
                # determine if the animation needs to be changed
                if self.daemon.mqtt.latest_print_status.get('gcode_state', None) is not None:
                    self.last_gcode_state = self.daemon.mqtt.latest_print_status['gcode_state']

                wantanim = None
                for anim in self.anim_list:
                    if anim.can_render():
                        wantanim = anim
                        break
                if wantanim != self.curanim:
                    logger.debug(f"switching to animation {wantanim} from {self.curanim}, print state is {self.daemon.mqtt.latest_print_status.get('gcode_state', None)}")
                    if self.anim_task:
                        self.anim_task.cancel()
                        self.anim_task = None
                    self.curanim = wantanim
                    if not wantanim:
                        self.put(b'\x00\x00\x00' * self.n_leds)
                    else:
                        self.anim_task = asyncio.create_task(anim.task())
    
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

###############

import colorsys
import math

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
        
LedStripDriver.ANIMATIONS['rainbow'] = RainbowAnimation


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
        
LedStripDriver.ANIMATIONS['paused'] = PausedAnimation


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
        
LedStripDriver.ANIMATIONS['failed'] = FailedAnimation


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
        
LedStripDriver.ANIMATIONS['finish'] = FinishAnimation


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
        
LedStripDriver.ANIMATIONS['running'] = RunningAnimation
