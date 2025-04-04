"""
[X1PLUS_MODULE_INFO]
module:
  name: i2c.tca8418
  default_enabled: true
[END_X1PLUS_MODULE_INFO]
"""

import logging
import asyncio
import time

from x1plus.services.x1plusd.expansion.i2c import register_driver
from x1plus.services.x1plusd.gpios import Gpio

logger = logging.getLogger(__name__)
name = "tca8418"

@register_driver(name)
class Tca8418Driver():
    """
    TCA8418 offers up to 8 rows x 10 columns for an up to 80 buttons keypad matrix

    Driver implementation assums user will be starting pinouts at R0, C0, going in order.

    Should a user have a custom or uneven matrix, they should configure the largest number
    for row/column (as if it's a AxB matrix) and ignore missing row x col combinations.

    Key are numbered 1-80 (inclusive). Row and Col are 1 indexed.

    Actions are performed on key-press down when set to rising.
    
    MQTT is updated with states of all configured buttons as either `pressed` or `released`

    Configuration Sample:

    // expansion.port_b json
    // Address is usually 0x34
    { 
        "tca8418": { 
            "name": "keypad", // acts as path in gpios actions
            "rows": 4, 
            "columns": 4,
            "publish_to_mqtt": true, // If true, publishes all states over MQTT on change
            "gpios": [  // Define which buttons (by row x col) will be registered as GPIOS
                {"row": 1, "col": 1, "inverted": true},
                {"row": 1, "col": 2},
                ...
                {"row": 2, "col": 3},
                ...
            ]
        }
    }

    // gpio.actions json
    [
        {
            "gpio": {
                "type": "i2c",
                "path": "keypad", // matches name from i2c config if present. Otherwise, full address path.
                "row": 1,
                "col": 1
            },
            "event": "rising",  // if inverted = True, Rising is on button release.
            "action": { // standard GPIO Actions format
                "gcode": "G91\nG0 Z2.5"
            }
        },
        {
            "gpio": {
                "type": "i2c",
                "path": "keypad",
                "row": 1,
                "col": 2
            },
            "event": "rising",
            "action": {
                "gcode": "G91\nG0 Z-2.5"
            }
        }
    ]
    """

    REG_CFG = 0x01
    REG_INT_STAT = 0x02

    REG_KEY_LCK_EC = 0x03
    REG_KEY_EVENT_A = 0x04  # FIFO (up to 10 events: A-J, 10 bit)

    REG_KP_GPIO1 = 0x1D
    REG_KP_GPIO2 = 0x1E
    REG_KP_GPIO3 = 0x1F

    REG_DEBOUNCE_DIS1 = 0x29
    REG_DEBOUNCE_DIS2 = 0x2A
    REG_DEBOUNCE_DIS3 = 0x2B
    REG_GPIO_DIR1 = 0x23
    REG_GPIO_DIR2 = 0x24
    REG_GPIO_DIR3 = 0x25

    INT_STAT_GPI_INT = 0x02
    INT_STAT_K_INT = 0x01


    def __init__(self, address, i2c_driver, config):

        self.daemon = i2c_driver.daemon
        self.sensors = self.daemon.sensors
        self.actions = self.daemon.actions
        self.config = config
        
        self.tca8418 = i2c_driver.i2c.get_port(address)        

        self.rows = self.config.get("rows", 0)
        self.cols = self.config.get("columns", 0)

        logger.info(f"probed {name.upper()} sensor at 0x{address:2x}")

        if not self.rows or not self.cols or self.rows > 8 or self.cols > 10:
            raise Exception(f"{name.upper()} invalid button row/columns configuration")

        self.currently_pressed = set()

        self.initialize_keypad()

        self.name = self.config.get('name', f"{i2c_driver.i2c_path}/i2c/0x{address:02x}/{name}")

        logger.info(f"{name.upper()} detected button keypad: {self.rows}x{self.cols} ({self.rows*self.cols}) buttons")

        self.gpio_instances = []
        self.gpio_last_read_time = 0
        self.gpio_last_read_data = {}

        publish_to_mqtt = self.config.get("publish_to_mqtt", False)
        self.publish_to_mqtt = publish_to_mqtt and str(publish_to_mqtt).lower().strip() != "false"

        gpios = self.config.get('gpios', [])
        if type(gpios) != list:
            raise TypeError("gpios config item was not a list")
        for gpio_def in gpios:
            if type(gpio_def) != dict:
                raise TypeError("gpio configuration item was not an object")

            # One-Indexed
            if 'row' not in gpio_def or type(gpio_def['row']) != int or not 0 < gpio_def['row'] <= 8:
                raise TypeError("gpio configuration item did not have a row defined, or row was not an int between 1 and 8")
            if 'col' not in gpio_def or type(gpio_def['col']) != int or not 0 < gpio_def['col'] <= 10:
                raise TypeError("gpio configuration item did not have a col defined, or col was not an int between 1 and 10")

            gpio_def = { "path": self.name, "type": "i2c", **gpio_def }
            # Add the current known name/path and type to definition

            button_id = ((gpio_def['row'] - 1) * self.cols) + (gpio_def['col'] -1) + 1
            inst = Tca8418Gpio(self, button_id, gpio_def)
            self.daemon.gpios.register(inst)
            self.gpio_instances.append(inst)

        # Init MQTT structure
        self.publish()



    def disconnect(self):
        for inst in self.gpio_instances:
            self.daemon.gpios.unregister(inst)
    

    def write_register(self, reg, value):
        self.tca8418.write(bytes([reg, value]))


    def read_register(self, reg, length=1):
        self.tca8418.write(bytes([reg]))
        return self.tca8418.read(length)


    def initialize_keypad(self):
        # Configure GPIO rows and columns as keypad inputs/outputs
        
        # Set all active, regardless of configuration
        self.write_register(self.REG_KP_GPIO1, 0xFF)  # Rows R0-R7, all
        self.write_register(self.REG_KP_GPIO2, 0xFF)  # Columns C0-C7, all
        self.write_register(self.REG_KP_GPIO3, 0x03)  # Columns C8-C9, all

        # Set as inputs
        self.write_register(self.REG_GPIO_DIR1, 0x00)
        self.write_register(self.REG_GPIO_DIR2, 0x00)
        self.write_register(self.REG_GPIO_DIR3, 0x00)

        # Enable keypad scanning mode
        self.write_register(self.REG_CFG, 0x01)

        # Enable Debounce
        self.write_register(self.REG_DEBOUNCE_DIS1, 0x00)
        self.write_register(self.REG_DEBOUNCE_DIS2, 0x00)
        self.write_register(self.REG_DEBOUNCE_DIS3, 0x00)

        # Clear interrupts
        self.write_register(self.REG_INT_STAT, 0xFF)


    def get_states(self):
        buttons = {}
        for x in range(1, (self.rows * self.cols) + 1, 1):
            buttons[f"btn_{x}"] = "pressed" if x in self.currently_pressed else "released"
        return buttons

    
    def publish(self):
        if not self.publish_to_mqtt:
            return
        data = self.get_states()
        payload = {
            "type": name,
            "rows": self.rows,
            "columns": self.cols,
        }
        asyncio.create_task(self.sensors.publish(self.name, **payload, **data))


    def read_states(self):

        try:
            updated = False
            int_stat = self.read_register(self.REG_INT_STAT)[0]
            
            if int_stat not in [self.INT_STAT_GPI_INT, self.INT_STAT_K_INT]:
                # No events in FIFO are key events
                self.write_register(self.REG_INT_STAT, 0xFF)
                return

            events_count = self.read_register(self.REG_KEY_LCK_EC)[0] & 0x0F

            for _ in range(events_count):
                event_data = self.read_register(self.REG_KEY_EVENT_A, 1)[0]

                is_release = event_data & 0x80 == 0

                # Key always comes back as (row * 10) + column, row being 0 indexed, column 1 indexed in formula
                # I.E., Key 39 = Row 4, Column 9. Key 40 = Row 4, Column 10. Key 41 = Row 5, Column 1
                key = int(event_data & 0x7F)
                row = (key - 1) // 10
                col = (key - 1) % 10
                key = (row * self.cols) + col + 1

                if key < 1 or key > 80 or key > (self.rows * self.cols):
                    continue

                if is_release:
                    logger.debug(f"{name.upper()} key: {key} was released")
                    self.currently_pressed.discard(key)
                else:
                    if key not in self.currently_pressed:
                        logger.debug(f"{name.upper()} key: {key} was pressed")
                        self.currently_pressed.add(key)
                updated = True
                
            self.write_register(self.REG_INT_STAT, 0xFF)
            if updated:
                self.publish()

        except Exception as e:
            logger.error(f"Error reading {name.upper()} buttons: {e.__class__.__name__}: {e}")


class Tca8418Gpio(Gpio):
    READ_CACHE_INTERVAL_MS = 50

    def __init__(self, driver, button_id, attr):
        self.attr = attr
        self.button_id = button_id
        self.driver = driver
        super().__init__()
    
    @property
    def attributes(self):
        return self.attr

    @property
    def polling(self):
        return True
    
    def output(self, val):
        pass
    
    def tristate(self):
        pass
    
    def read(self):
        now = time.time()
        if (now - self.driver.gpio_last_read_time) < (self.READ_CACHE_INTERVAL_MS / 1000.0):
            data = self.driver.gpio_last_read_data
        else:
            old_state = self.driver.gpio_last_read_data.get(f"btn_{self.button_id}", None)
            self.driver.read_states()
            data = self.driver.get_states()
            if not data:
                raise IOError('TCA8418 did not read button states back')
            self.driver.gpio_last_read_time = now
            self.driver.gpio_last_read_data = data
            new_state = self.driver.gpio_last_read_data.get(f"btn_{self.button_id}", None)
        
        inverted = self.attr.get('inverted', False)
        return (data.get(f"btn_{self.button_id}", None) == "pressed") ^ inverted
