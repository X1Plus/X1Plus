from abc import ABC, abstractmethod
import asyncio
import logging

from . import actions

logger = logging.getLogger(__name__)

class Gpio(ABC):
    @property
    @abstractmethod
    def attributes(self):
        pass
    
    @abstractmethod
    def output(self, on):
        pass
    
    @abstractmethod
    def tristate(self):
        pass
    
    @abstractmethod
    def read(self):
        pass

class MockGpio(Gpio):
    def __init__(self, id, attrs):
        self._attrs = attrs
        self._id = id
        self._on = False
    
    @property
    def attributes(self):
        return self._attrs
    
    def output(self, on):
        logger.info(f"mock GPIO {self._id}: output({on})")
        self._on = on
    
    def tristate(self):
        logger.info(f"mock GPIO {self._id}: tristate()")
    
    def read(self):
        logger.info(f"mock GPIO {self._id}: read() -> {self._on}")
        return self._on

class GpioManager:
    """
    Abstraction for expansion board (and other) GPIOs.

    The GpioManager holds an abstraction to GPIOs that can be outputs or
    inputs.  Because GPIOs sometimes are shared with other FTDI ports (or
    might even be expanded on I2C GPIO expanders?), they are provided
    through individual drivers that register them and actually operate on
    them (this is implemented by an instance of a "class Gpio", which
    presumably has to reach into a parent object to change some state on the
    FTDI port).
    
    GPIOs are specified in a dictionary of attributes, and you can look up
    GPIOs as combinations of these.  For instance, a GPIO might have a
    function ("shutter", "buzzer"; "button"); it might have a board that it
    is part of ("X1P-004"); it might have a location ("left", "right"); it
    has a pin number (0, 1, 2); and it has a port ("a", "b", "c", "d"). 
    Putting it together, the button on an Andon board has the following
    attributes:
    
      {
        "function": "button",
        "position": "left",
        "board_type": "X1P-005",
        "board_serial": "X1P-005-A02-0143"
        "pin": 6,
        "port": "a",
      }
    
    Setting or resetting a GPIO acts on all specified ports at the same
    time; for instance, you may wish to turn on all GPIOs that function as
    camera shutters, or you may wish to refine this further to turn on only
    the camera shutters on pin 0 or port A.  However, ports must be uniquely
    specified in order to query them.
    
    Some GPIOs may have their functionality inverted (for instance, some
    buzzers may be active-low).  This is expected to be handled by the
    "class Gpio", if specified in the driver's GPIO configuration.
    """

    def __init__(self, daemon):
        self.daemon = daemon
        self.gpios = set()
        
        if self.daemon.settings.get("gpio.mock", False):
            self.register(MockGpio("mock_1", { "type": "mock", "gpio": "1", "function": "buzzer" }))
            self.register(MockGpio("mock_2", { "type": "mock", "gpio": "2", "function": "shutter" }))
            self.register(MockGpio("mock_3", { "type": "mock", "gpio": "3" }))
            self.register(MockGpio("mock_4", { "type": "mock", "gpio": "4" }))
    
    def find(self, **kwargs):
        return set(filter(lambda gpio: all(k in gpio.attributes and gpio.attributes[k] == v for k,v in kwargs.items()), self.gpios))
    
    def port_properties(self, port_name):
        if port_name not in self.daemon.expansion.eeproms:
            return {
                "port": "unknown"
            }

        return {
            "port": port_name.split('_')[-1],
            "board_type": self.daemon.expansion.eeproms[port_name]['model'],
            "board_serial": '-'.join(self.daemon.expansion.eeproms[port_name][k] for k in ['model', 'revision', 'serial']),
        }

    def register(self, gpio):
        assert len(self.find(**gpio.attributes)) == 0
        assert gpio not in self.gpios
        self.gpios.add(gpio)
        logger.info(f"registered GPIO with attributes {gpio.attributes}")
    
    def unregister(self, gpio):
        self.gpios.remove(gpio) # asserts if not registered
    
    # convenience wrappers around find and output/tristate/read
    def output(self, on, **kwargs):
        gpios = self.find(**kwargs)
        if len(gpios) == 0:
            raise KeyError(kwargs)
        for g in gpios:
            g.output(on)
    
    def tristate(self, **kwargs):
        gpios = self.find(**kwargs)
        if len(gpios) == 0:
            raise KeyError(kwargs)
        for g in gpios:
            g.tristate()
    
    def read(self, **kwargs):
        gpios = self.find(**kwargs)
        if len(gpios) != 1:
            raise KeyError(kwargs)
        return gpios.pop().read()
        
    # convenience wrappers around output
    def on(self, **kwargs):
        self.output(on = True, **kwargs)

    def off(self, **kwargs):
        self.output(on = False, **kwargs)


@actions.register_action("gpio")
async def _action_gpio(handler, subconfig):
    if type(subconfig) != dict:
        raise TypeError(f"gpio parameter {subconfig} was not dict")
    if 'action' not in subconfig:
        raise ValueError(f"gpio parameter did not have action key")
    if 'gpio' not in subconfig or type(subconfig['gpio']) != dict:
        raise ValueError(f"gpio parameter did not have gpio key or key was not dict")
    if subconfig['action'] == 'on':
        handler.daemon.gpios.on(**subconfig['gpio'])
    elif subconfig['action'] == 'off':
        handler.daemon.gpios.off(**subconfig['gpio'])
    elif subconfig['action'] == 'tristate':
        handler.daemon.gpios.tristate(**subconfig['gpio'])
    elif subconfig['action'] == 'pulse':
        duration = float(subconfig['duration'])
        handler.daemon.gpios.on(**subconfig['gpio'])
        await asyncio.sleep(duration)
        handler.daemon.gpios.off(**subconfig['gpio'])
    else:
        raise ValueError(f"unknown gpio action {subconfig['action']}")
    # to implement: action: wait
