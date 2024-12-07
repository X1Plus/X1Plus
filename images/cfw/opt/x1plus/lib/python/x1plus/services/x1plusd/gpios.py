from abc import ABC, abstractmethod
import asyncio
import contextlib
import logging
import time

from . import actions

logger = logging.getLogger(__name__)

class Gpio(ABC):
    def __init__(self):
        super().__init__()
        self.on_change = None
        self.press_time = None
    
    @property
    @abstractmethod
    def polling(self):
        """
        Whether the GpioManager must poll this Gpio to get interrupts (true
        causes GpioManager to poll and call the on_change on its own, false
        means that the GpioManager assumes that the GPIO driver will handle
        this in a more optimized way).
        """
        pass
    
    @property
    @abstractmethod
    def attributes(self):
        pass
    
    def matches(self, attributes):
        myattrs = self.attributes
        return all(k in myattrs and myattrs[k] == v for k,v in attributes.items())
    
    @abstractmethod
    def output(self, on):
        pass
    
    @abstractmethod
    def tristate(self):
        pass
    
    @abstractmethod
    def read(self):
        pass
    
    def __str__(self):
        return f"{self.__class__.__name__}({self.attributes})"

class MockGpio(Gpio):
    def __init__(self, id, attrs):
        super().__init__()
        self._attrs = attrs
        self._id = id
        self._on = False
    
    @property
    def polling(self):
        return False
    
    @property
    def attributes(self):
        return self._attrs
    
    def output(self, on):
        logger.info(f"mock GPIO {self._id}: output({on})")
        self._on = on
        if self.on_change:
            self.on_change(on)
    
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
    
    POLLING_INTERVAL_MS = 50
    LONG_PRESS_THRESHOLD_MS = 850

    def __init__(self, daemon):
        self.daemon = daemon
        self.gpios = set()
        self.gpio_poll_state = {}
        self.polling_gpios = set()
        self.poll_task = None
        self.action_task = None
        self.event_handlers = []
        
        if self.daemon.settings.get("gpio.mock", False):
            self.register(MockGpio("mock_1", { "type": "mock", "gpio": "1", "function": "buzzer" }))
            self.register(MockGpio("mock_2", { "type": "mock", "gpio": "2", "function": "shutter" }))
            self.register(MockGpio("mock_3", { "type": "mock", "gpio": "3" }))
            self.register(MockGpio("mock_4", { "type": "mock", "gpio": "4" }))
            self.on_event({"function": "button"}, lambda gpio, value: logger.info(f"gpio {gpio} changed to value {value}!"))
        
        self.daemon.settings.on("gpio.actions", self._update_action_settings)
        self._update_action_settings()
    
    def find(self, **kwargs):
        return set(filter(lambda gpio: gpio.matches(kwargs), self.gpios))
    
    def port_properties(self, port_name):
        if self.daemon.expansion.eeproms.get(port_name, None) is None:
            return {
                "port": port_name.split('_')[-1],
            }

        return {
            "port": port_name.split('_')[-1],
            "board_type": self.daemon.expansion.eeproms[port_name]['model'],
            "board_serial": '-'.join(self.daemon.expansion.eeproms[port_name][k] for k in ['model', 'revision', 'serial']),
        }

    async def _poll(self):
        while True:
            for gpio in self.polling_gpios:
                oldstate = self.gpio_poll_state[gpio]
                newstate = gpio.read()
                if newstate != oldstate:
                    if gpio.on_change:
                        gpio.on_change(newstate)
                    self.gpio_poll_state[gpio] = newstate
            await asyncio.sleep(self.POLLING_INTERVAL_MS / 1000) # we may get cancelled here, that is fine
    
    def _update_poll_task(self):
        # we only want to bother to poll GPIOs that anybody is actually
        # listening for events on!
        self.polling_gpios.clear()
        for gpio in self.gpios:
            if gpio.polling and any(gpio.matches(m) for m,_ in self.event_handlers):
                self.polling_gpios.add(gpio)
        if len(self.polling_gpios) == 0 and self.poll_task:
            # nobody cares anymore, shut down the polling task
            self.poll_task.cancel()
            self.poll_task = None
        elif len(self.polling_gpios) != 0 and not self.poll_task:
            # someone begins to care, so we need to start it up
            self.poll_task = asyncio.create_task(self._poll())

    def register(self, gpio):
        assert len(self.find(**gpio.attributes)) == 0
        assert gpio not in self.gpios
        self.gpios.add(gpio)
        logger.info(f"registered GPIO with attributes {gpio.attributes}")
        
        if 'default' in gpio.attributes:
            if gpio.attributes['default'] == 1 or gpio.attributes['default'] == True:
                gpio.output(1)
            elif gpio.attributes['default'] == 0 or gpio.attributes['default'] == False:
                gpio.output(0)
            else:
                gpio.tristate()
        
        def _on_change(newstate):
            if newstate:
                gpio.press_time = time.time()
            for (match, callback) in self.event_handlers:
                if gpio.matches(match):
                    callback(gpio, newstate)
        gpio.on_change = _on_change

        if gpio.polling:
            self.gpio_poll_state[gpio] = None # last state
        self._update_poll_task()

    def unregister(self, gpio):
        gpio.on_change = None
        self.gpios.remove(gpio) # asserts if not registered
        if gpio in self.gpio_poll_state:
            del self.gpio_poll_state[gpio]
        self._update_poll_task()
    
    def on_event(self, match, callback):
        """
        Register a callback for events on GPIOs matching `match`.  The
        callback takes two parameters: the GPIO that changed, and the new
        state.
        
        For convenience, returns a context manager, for event matches that
        need to last only a short while.  If no callback is specified, the
        context manager returns a queue with events that the callback would
        be called with (similar to mqtt.request_messages /
        mqtt.report_messages).
        """
        
        q = None
        if callback == None:
            q = asyncio.Queue()
            def _handle(gpio, st):
                q.put_nowait((gpio, st, ))
            callback = _handle

        handler_entry = (match, callback, )
        self.event_handlers.append(handler_entry)
        self._update_poll_task()
        
        @contextlib.contextmanager
        def _mkctx():
            try:
                yield q
            finally:
                self.event_handlers.remove(handler_entry)
                self._update_poll_task()
        return _mkctx()

    def _update_action_settings(self):
        actions = self.daemon.settings.get("gpio.actions", [])
        if type(actions) != list:
            logger.error("gpio.actions was not a list?")
            return
        
        # If a gpio.action is in progress, it will also be canceled!
        if self.action_task:
            self.action_task.cancel()
            self.action_task = None
        
        if len(actions) == 0: 
            # no actions, nothing to do
            return
        
        async def _action_worker():
            with contextlib.ExitStack() as stack:
                action_queue = asyncio.Queue()
                
                # set up all the things that could push actions into the Queue
                for gpio_action in actions:
                    # callback for each individual gpio action in the
                    # setting list, dispatches by 'event' type
                    def _handle(gpio, newvalue,gpio_action=gpio_action):
                        should_trigger = False
                        if gpio_action.get('event', 'change') == 'change': # if not otherwise specified
                            should_trigger = True
                        elif gpio_action['event'] == 'rising':
                            if newvalue:
                                should_trigger = True
                        elif gpio_action['event'] == 'falling':
                            if not newvalue:
                                should_trigger = True
                        elif gpio_action['event'] == 'short_press' or gpio_action['event'] == 'long_press':
                            if not newvalue and gpio.press_time:
                                press_duration = time.time() - gpio.press_time
                                if gpio_action['event'] == 'short_press' and press_duration < self.LONG_PRESS_THRESHOLD_MS / 1000:
                                    should_trigger = True
                                elif gpio_action['event'] == 'long_press' and press_duration > self.LONG_PRESS_THRESHOLD_MS / 1000:
                                    should_trigger = True
                        else:
                            logger.error(f"gpio.action {gpio_action} has unknown event type!")
                        
                        if should_trigger:
                            logger.info(f"gpio.actions {gpio_action} fired on gpio {gpio} with value {newvalue}")
                            action_queue.put_nowait(gpio_action['action'])
                    
                    # tear down all callbacks when the action worker is canceled
                    stack.enter_context(self.on_event(gpio_action['gpio'], _handle))
                
                # now execute actions as they come
                while True:
                    action = await action_queue.get()
                    await self.daemon.actions.execute(action)
        
        self.action_task = asyncio.create_task(_action_worker())
    
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

    elif subconfig['action'] == 'wait':
        # maybe it is already in the state that we hoped for?
        try:
            if handler.daemon.gpios.read(**subconfig['gpio']) == subconfig['value']:
                return
        except KeyError:
            # could be that there was no 'value'; could be that there were
            # too many gpios that matched; either of those is ok, and now we
            # just wait for the event
            pass
        
        ev = asyncio.Event()
        def _callback(gpio, newvalue):
            if newvalue == subconfig.get('value', newvalue):
                ev.set()
        with handler.daemon.gpios.on_event(subconfig['gpio'], _callback):
            try:
                await asyncio.wait_for(ev.wait(), subconfig.get('timeout', None))
            except TimeoutError:
                logger.info(f"action timed out waiting for gpio {subconfig['gpio']}")

    else:
        raise ValueError(f"unknown gpio action {subconfig['action']}")
