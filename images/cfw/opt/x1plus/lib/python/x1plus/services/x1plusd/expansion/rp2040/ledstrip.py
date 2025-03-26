import logging

from x1plus.services.x1plusd.gpios import Gpio
from ..ledstrip import BaseLedStripDriver

logger = logging.getLogger(__name__)

class LedStripDriver(BaseLedStripDriver):
    def __init__(self, daemon, config, expansion, port, port_name):
        self.daemon = daemon
        self.config = config
        self.expansion = expansion
        self.port = port

        # for now, RP2040 only supports ws2812b LED timings
        # self.led = LED_TYPES[self.config.get('led_type', 'ws2812b')]
        
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
            inst = LedStripGpio(self, self.expansion.PORTS[self.port][gpio_def['pin']], gpio_def)
            self.daemon.gpios.register(inst)
            self.gpio_instances.append(inst)

        super().__init__()

    def put(self, bs):
        self.expansion._ws2812(self.expansion.PORTS[self.port][1], bs)
    
    def disconnect(self):
        for inst in self.gpio_instances:
            self.daemon.gpios.unregister(inst)
        super().disconnect()

class LedStripGpio(Gpio):
    def __init__(self, ledstrip, pin, attr):
        self.ledstrip = ledstrip
        self.pin = pin
        self.attr = attr
        super().__init__()
    
    @property
    def attributes(self):
        return self.attr

    @property
    def polling(self):
        # XXX: some day, rp2040 will push interrupt-driven GPIOs, but for now, we poll
        return True
    
    def output(self, val):
        self.ledstrip.expansion._gpio_config(self.pin, oe = True, data = val)
    
    def tristate(self):
        self.ledstrip.expansion._gpio_config(self.pin, oe = False)
    
    def read(self):
        # this is cached by the Expansion driver
        return self.ledstrip.expansion._gpio_read(self.pin) ^ self.attr.get('inverted', False)
