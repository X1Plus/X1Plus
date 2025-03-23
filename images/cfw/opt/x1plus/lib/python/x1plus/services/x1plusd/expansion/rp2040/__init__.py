import time
import os
import logging
import struct

import usb

from ..device import ExpansionDevice
from ..smsc9514 import Smsc9514

from .rp2040boot import Rp2040Boot

logger = logging.getLogger(__name__)

class Rp2040ExpansionDevice(ExpansionDevice):
    PORTS = {
        0: { 0:  5, 1:  4, 2:  4, 3:  2, 4: 29, 5: 35, 6:  1, 7:  0 },
        1: { 0: 11, 1: 10, 2:  9, 3:  8, 4: 28, 5: 36, 6:  7, 7:  6 },
        2: { 0: 17, 1: 16, 2: 15, 3: 14, 4: 27, 5: 34, 6: 13, 7: 12 },
        3: { 0: 23, 1: 22, 2: 21, 3: 20, 4: 26, 5: 37, 6: 19, 7: 18 },
    }

    DRIVERS = { }
    
    needs_reset_to_reopen = False

    @classmethod
    def detect(cls):
        """
        Looks for a X1P-002-C.
    
        If it finds one, returns an ExpansionDevice.
        """
    
        # XXX: hoist this out to a find-and-verify-eeprom routine
        lan9514_eth = usb.core.find(idVendor = 0x0424, idProduct = 0xec00)
        if not lan9514_eth:
            return None
    
        if lan9514_eth.product.startswith('Expansion Board X1P-002-C'):
            revision = lan9514_eth.product.split(' ')[2]
            serial = lan9514_eth.serial_number
        else:
            logger.warning("found a LAN9514, but it does not appear to be an X1P-002-C, so we will not even try resetting an attached RP2040")
            return None
    
        smsc = Smsc9514()
    
        return Rp2040ExpansionDevice(revision = revision, serial = serial, smsc = smsc)
        
    def __init__(self, revision, serial, smsc):
        self.revision = revision
        self.serial = serial
        self.smsc = smsc
        self.nports = 0
        
        self.reset()

        super().__init__()

    def reset(self):
        self.rp2040 = None
        self.nports = 0

        # boot the RP2040...
        self.smsc.rp2040_reset()
        for attempt in range(5, -1, -1):
            try:
                boot = Rp2040Boot()
                boot.bootbin(os.path.join(os.path.dirname(__file__), "x1p_002_c_fw.bin"))
                break
            except Exception as e:
                logger.info(f"failed to boot RP2040: {e}")
                if attempt == 0:
                    logger.error(f"failed to boot RP2040 after 5 attempts: {e}")
                    # leave nports as 0, and give up
                    return
                time.sleep(0.2)
        
        # ...then attach to it
        def is_expander_rp2040(dev):
            try:
                return dev.idVendor == 0x2E8A and dev.idProduct == 0x000A and dev.manufacturer == "X1Plus" and dev.product == "X1Plus Expander GPIO controller"
            except:
                return False

        for attempt in range(5):
            self.rp2040 = usb.core.find(custom_match = is_expander_rp2040)
            if self.rp2040:
                break
            time.sleep(0.2)
        
        if not self.rp2040:
            logger.error("RP2040 never woke up into X1Plus firmware?")
            return

        self.rp2040.set_configuration()
        self.intf = self.rp2040[0][(0, 0)]
        self.ep_out = self.intf[0]
        self.ep_in  = self.intf[1]

        self.nports = len(self.PORTS)

    def _i2c_read(self, scl, sda, addr, dlen):
        self.ep_out.write(struct.pack('<BBB', 4, scl, sda))
        self.ep_out.write(struct.pack('<BBB', 1, addr, dlen))
        self.ep_out.write(struct.pack('<B', 0))
        
        buf = b""
        while len(buf) < (dlen + 1):
            buf += self.ep_in.read(0x100)
        if buf[0] != 0:
            raise IOError("I2C transaction failed")
        
        return buf[1:]

    def _i2c_write(self, scl, sda, addr, data):
        self.ep_out.write(struct.pack('<BBB', 4, scl, sda))
        self.ep_out.write(struct.pack('<BBB', 2, addr, len(data)) + data)
        self.ep_out.write(struct.pack('<B', 0))
        
        buf = b""
        while len(buf) < 1:
            buf += self.ep_in.read(0x100)
        if buf[0] != 0:
            raise IOError("I2C transaction failed")
    
    def _ws2812(self, pin, buf):
        self.ep_out.write(struct.pack('<BHB', 1, len(buf), pin))
        self.ep_out.write(buf)

    def detect_eeprom(self, port):
        try:
            i2c_params = (self.PORTS[port][7], self.PORTS[port][6], 0x50, )
            self._i2c_write(*i2c_params, b'\x00')
            eeprom_buf = self._i2c_read(*i2c_params, 0x80)
            eeprom_buf += self._i2c_read(*i2c_params, 0x80)
        except Exception as e:
            logger.warning(f"EEPROM detect on port {port} failed: {e}")
            return None
        return eeprom_buf

#####

import asyncio

from ..ledstrip import ANIMATIONS, DEFAULT_ANIMATIONS

class LedStripDriver():
    def __init__(self, daemon, config, expansion, port, port_name):
        self.daemon = daemon
        self.config = config
        self.expansion = expansion
        self.port = port

        # self.led = LED_TYPES[self.config.get('led_type', 'ws2812b')]
        self.n_leds = int(self.config['leds'])
        
        # XXX: implement GPIOs on top of this

        self.put(b'\x00\x00\x00' * 128) # clear out a long strip
        
        self.anim_task = None
        self.curanim = None
        
        # the 'animations' key is a list that looks like:
        #
        #   [ 'paused', { 'rainbow': { 'brightness': 0.5 } } ]
        self.anim_list = []   
        self.last_gcode_state = None
        self.anim_watcher = None

        for anim in self.config.get('animations', DEFAULT_ANIMATIONS):
            if type(anim) == str and ANIMATIONS.get(anim, None):
                self.anim_list.append(ANIMATIONS[anim](self, {}))
                continue
            elif type(anim) != dict or len(anim) != 1:
                raise ValueError("animation must be either string or dictionary with exactly one key")
            
            (animname, subconfig) = next(iter(anim.items()))
            if ANIMATIONS.get(animname, None):
                self.anim_list.append(ANIMATIONS[animname](self, subconfig))

        self.anim_watcher = asyncio.create_task(self.anim_watcher_task())

    def put(self, bs):
        self.expansion._ws2812(self.expansion.PORTS[self.port][1], bs)
    
    def disconnect(self):
        #for inst in self.gpio_instances:
        #    self.daemon.gpios.unregister(inst)
        if self.anim_task:
            self.anim_task.cancel()
            self.anim_task = None
        self.anim_watcher.cancel()
    
    async def anim_watcher_task(self):
        # XXX: hoist this into a superclass, I guess
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

Rp2040ExpansionDevice.DRIVERS["ledstrip"] = LedStripDriver
