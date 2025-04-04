import logging
import asyncio
import time
import struct

from collections import namedtuple

from pyftdi.ftdi import Ftdi

from x1plus.services.x1plusd.gpios import Gpio
from ..ledstrip import BaseLedStripDriver

logger = logging.getLogger(__name__)

LedType = namedtuple('LedType', [ 'frequency', 'zero', 'one' ])

LED_TYPES = {
    'ws2812b': LedType(frequency = 6400000, zero = bytearray([0b11000000]), one = bytearray([0b11111100]))
}

class LedStripDriver(BaseLedStripDriver):
    def __init__(self, daemon, config, expansion, port, port_name):
        self.daemon = daemon
        self.ftdi_path = f"{expansion.ftdi_path}{port + 1}"
        self.config = config

        self.led = LED_TYPES[self.config.get('led_type', 'ws2812b')]
        
        self.ftdi = Ftdi()
        self.ftdi.open_mpsse_from_url(self.ftdi_path, frequency = self.led.frequency, direction = 0x03) # DO | SCK
        self.ftdi.enable_adaptive_clock(False)
        
        self.gpio_dir = 0x03
        self.gpio_out = 0
        self.gpio_last_read_time = 0
        self.gpio_last_read_data = None
        
        self.gpio_instances = []
        gpios = self.config.get('gpios', [])
        if type(gpios) != list:
            raise TypeError("gpios config item was not a list")
        for gpio_def in self.config.get('gpios', []):
            if type(gpio_def) != dict:
                raise TypeError("gpio configuration item was not an object")
            if 'pin' not in gpio_def or type(gpio_def['pin']) != int:
                raise TypeError("gpio configuration item did not have a pin defined, or pin was not an int")
            gpio_def = { **self.daemon.gpios.port_properties(port_name), **gpio_def }
            inst = LedStripGpio(self, 1 << gpio_def['pin'], gpio_def)
            self.daemon.gpios.register(inst)
            self.gpio_instances.append(inst)

        self.lut = {}
        for i in range(256):
            v = bytearray()
            for j in range(7, -1, -1):
                if ((i >> j) & 1) == 0:
                    v += self.led.zero
                else:
                    v += self.led.one
            self.lut[i] = v
        
        super().__init__()

    def update_gpio(self):
        self.ftdi.write_data(bytes([Ftdi.SET_BITS_LOW, self.gpio_out, self.gpio_dir]))
            
    def put(self, bs):
        obs = bytearray(b'').join([self.lut[b] for b in bs])
        obs = struct.pack('<BH', Ftdi.WRITE_BYTES_NVE_MSB, len(obs) - 1) + obs
        self.ftdi.write_data(obs)
    
    def disconnect(self):
        super().disconnect()

        for inst in self.gpio_instances:
            self.daemon.gpios.unregister(inst)
        self.ftdi.close()

    
###############

class LedStripGpio(Gpio):
    # do not actually submit a read more frequently than this: use the
    # cached result, if the system is polling multiple GPIOs in one polling
    # cycle
    READ_CACHE_INTERVAL_MS = 50

    def __init__(self, ledstrip, pin, attr):
        # pin: 1 << x
        self.ledstrip = ledstrip
        self.pin = pin
        self.attr = attr
        super().__init__()
    
    @property
    def attributes(self):
        return self.attr

    @property
    def polling(self):
        return True
    
    def output(self, val):
        self.ledstrip.gpio_dir |= self.pin
        if val:
            self.ledstrip.gpio_out |= self.pin
        else:
            self.ledstrip.gpio_out &= ~self.pin
        self.ledstrip.update_gpio()
    
    def tristate(self):
        self.ledstrip.gpio_dir &= ~self.pin
        self.ledstrip.update_gpio()
    
    def read(self):
        now = time.time()
        if (now - self.ledstrip.gpio_last_read_time) < (self.READ_CACHE_INTERVAL_MS / 1000.0):
            data = self.ledstrip.gpio_last_read_data
        else:
            self.ledstrip.ftdi.write_data(bytes([Ftdi.GET_BITS_LOW, Ftdi.SEND_IMMEDIATE]))
            data = self.ledstrip.ftdi.read_data_bytes(1, 4)
            if len(data) != 1:
                raise IOError('FTDI did not read bytes back')
            self.ledstrip.gpio_last_read_time = now
            self.ledstrip.gpio_last_read_data = data
        inverted = self.attr.get('inverted', False)
        return ((data[0] & self.pin) == self.pin) ^ inverted
