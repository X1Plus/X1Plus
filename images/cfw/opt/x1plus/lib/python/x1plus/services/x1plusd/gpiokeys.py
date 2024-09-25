import asyncio
import logging
import struct
import time
from .gpios import Gpio
from . import actions

logger = logging.getLogger(__name__)

EV_KEY = 0x01
LONG_PRESS_THRESHOLD = 0.850  # seconds
MONITORED_PINS = {116: "KEY_POWER", 128: "KEY_STOP", 134: "KEY_OPEN"}

#temporary config
conf = {
    "gpiokeys": {
        "116": {
            "name": "power",
            "type": "push_button",
            "actions": {
                "shortPress": {
                    "action": "button_press",
                    "button": "power",
                    "pressType": "short"
                },
                "longPress": {
                    "action": "button_press",
                    "button": "power",
                    "pressType": "long"
                }
            }
        },
        "128": {
            "name": "estop",
            "type": "push_button",
            "actions": {
                "shortPress": {
                    "action": "button_press",
                    "button": "estop",
                    "pressType": "short"
                },
                "longPress": {
                    "action": "button_press",
                    "button": "estop",
                    "pressType": "long"
                }
            }
        },
        "134": {
            "name": "door",
            "type": "door_sensor",
            "actions": {
                "open": {
                    "action": "door_action",
                    "door": "main",
                    "state": "open"
                },
                "close": {
                    "action": "door_action",
                    "door": "main",
                    "state": "closed"
                }
            }
        }
    }
}

class GpiokeysHandler:
    def __init__(self, daemon):
        self.daemon = daemon
        self.input_gpios = {}
        self.event_file = None
        self.loop = None
        self._running = asyncio.Event()
        self.config = conf['gpiokeys']
        
        for code, name in MONITORED_PINS.items():
            gpio = GpiokeysGpio(f"input_{name}", {
                "type": "input",
                "gpio": str(code),
                "function": "button",
                "name": name
            })
            self.input_gpios[code] = gpio
            #self.daemon.gpio.register(gpio)

    async def setup(self):
        try:
            self.event_file = open("/dev/input/event4", 'rb')
            self.loop = asyncio.get_running_loop()
            self.loop.add_reader(self.event_file.fileno(), self.event_callback)
            logger.info("gpiokeys setup complete")
            self._running.set()
        except IOError as e:
            logger.error(f"Failed to open event file: {e}")
            raise

    def event_callback(self):
        try:
            event = self.event_file.read(16)
            if event:
                (tv_sec, tv_usec, type, code, value) = struct.unpack('llHHI', event)
                if type == EV_KEY and code in self.input_gpios:
                    gpio = self.input_gpios[code]
                    config = self.config[str(code)]
                    
                    event_data = {
                        "gpio": gpio,
                        "value": value,
                        "timestamp": time.time(),
                        "config": config
                    }
                    
                    asyncio.create_task(self.daemon.actions.execute({config['action']: event_data}))
        except struct.error as e:
            logger.error(f"Struct unpack error: {e}")
        except Exception as e:
            logger.error(f"Error reading event: {e}")

    async def task(self):
        await self.setup()
        try:
            logger.info("gpiokeys task started")
            while self._running.is_set():
                await asyncio.sleep(1)  
        except asyncio.CancelledError:
            logger.info("gpiokeys task cancelled")
        finally:
            self.cleanup()

    def cleanup(self):
        if self.event_file:
            if self.loop:
                self.loop.remove_reader(self.event_file.fileno())
            self.event_file.close()
        logger.info("gpiokeys cleaned up")
        
        
class GpiokeysGpio(Gpio):
    def __init__(self, id, attributes):
        self._id = id
        self._attributes = attributes
        self.pressed = False
        self.last_press_time = 0

    @property
    def attributes(self):
        return self._attributes

    def output(self, on):
        logger.info(f"but there is no output")

    def tristate(self):
        logger.info(f"tristate on input GPIO {self._id}")

    def read(self):
        return self.pressed
        
        
@actions.register_action("button_event")
async def _action_button_event(handler, event_data):
    gpio = event_data['gpio']
    value = event_data['value']
    timestamp = event_data['timestamp']
    config = event_data['config']

    if value == 1:  # Press
        gpio.pressed = True
        gpio.last_press_time = timestamp
        logger.info(f"{gpio.attributes['name']} button pressed")
    elif value == 0:  # Release
        gpio.pressed = False
        press_duration = timestamp - gpio.last_press_time
        press_type = "shortPress" if press_duration < LONG_PRESS_THRESHOLD else "longPress"
        logger.info(f"{gpio.attributes['name']} button {press_type}, duration: {press_duration:.3f} seconds")
        
        if press_type in config['actions']:
            action_config = config['actions'][press_type]
            action_config['duration'] = press_duration
            
            # get action config
        else:
            logger.warning(f"No action configured for {press_type} on {gpio.attributes['name']} button")


@actions.register_action("door_event")
async def _action_door_event(handler, event_data):
    gpio = event_data['gpio']
    value = event_data['value']

    state = "open" if value == 1 else "closed"
    logger.info(f"Door {state}")
    
    if state == "open":
        # Door open action
        pass
    else:
        # Door close action
        pass