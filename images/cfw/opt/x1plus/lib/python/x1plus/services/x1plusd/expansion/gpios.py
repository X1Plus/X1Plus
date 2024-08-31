from abc import ABC, abstractmethod

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

    def __init__(self):
        self.gpios = set()
    
    def find(self, **kwargs):
        return set(filter(lambda gpio: all(hasattr(gpio, k) and getattr(gpio, k) == v for k,v in items(kwargs)), self.gpios))
    
    def port_properties(self, port):
        # XXX
        return {
            "port": "a",
            "board_type": "X1P-005",
            "board_serial": "X1P-005-A02-0123",
        }

    def register(self, gpio):
        assert len(self.find(**gpio.attributes)) == 0
        assert gpio not in self.gpios
        self.gpios.add(gpio)
    
    def unregister(self, gpio):
        self.gpios.remove(gpio) # asserts if not registered
    
    # convenience wrappers around find and output/tristate/read
    def output(self, on, **kwargs):
        gpios = self.find(**kwargs)
        if len(gpios) == 0:
            raise KeyError
        for g in gpios:
            g.output(on)
    
    def tristate(self, **kwargs):
        gpios = self.find(**kwargs)
        if len(gpios) == 0:
            raise KeyError
        for g in gpios:
            g.tristate()
    
    def read(self, **kwargs):
        gpios = self.find(**kwargs)
        if len(gpios) != 1:
            raise KeyError
        return gpios.pop().read()
        
    # convenience wrappers around output
    def on(self, **kwargs):
        self.output(on = True, **kwargs)

    def off(self, **kwargs):
        self.output(on = False, **kwargs)
