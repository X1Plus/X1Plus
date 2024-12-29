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

logger = logging.getLogger(__name__)
name = "tca8418"

@register_driver(name)
class Tca8418Driver():
    """
    TCA8418 offers up to 8 rows x 10 columns for an up to 80 buttons keypad matrix

    Driver implementation assums user will be starting pinouts at R0, C0, going in order.

    Should a user have a custom or uneven matrix, they should configure the largest number
    for row/column (as if it's a AxB matrix) and ignore missing key numbers for action-setting.

    Key are numbered 1-80 (inclusive).

    Actions are performed on key-press. MQTT is updated with states of all configured buttons as either `pressed` or `released`

    Configuration Sample:

    { 
        "tca8418": { 
            "name": "keypad", 
            "interval_ms": 100, 
            "rows": 4, 
            "columns": 4, 
            "actions": [
                {
                    "key": 1,
                    "action": {...}
                },
                {
                    "key": 2,
                    "action": {...}
                }
                ...
            ]
        }
    }
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

        self.sensors = i2c_driver.daemon.sensors
        self.actions = i2c_driver.daemon.actions
        self.tca8418 = i2c_driver.i2c.get_port(address)        

        self.rows = config.get("rows", 0)
        self.cols = config.get("columns", 0)

        logger.info(f"probed {name.upper()} sensor at 0x{address:2x}")

        if not self.rows or not self.cols or self.rows > 8 or self.cols > 10:
            raise Exception(f"{name.upper()} invalid button row/columns configuration")

        self.currently_pressed = set()

        self.initialize_keypad()

        self.interval_ms = int(config.get('interval_ms', 100))
        self.name = config.get('name', f"{i2c_driver.ftdi_path}/i2c/0x{address:02x}/{name}")

        mapping = config.get("actions", []) # Keys are 1 indexed
        self.mapped_actions = {}
        for key_map in mapping:
            if 0 <= int(key_map.get("key", -1)) <= 80 and key_map.get("action", None):
                self.mapped_actions[str(key_map.get("key"))] = key_map.get("action")

        logger.info(f"{name.upper()} detected button keypad: {self.rows}x{self.cols} ({self.rows*self.cols}) buttons")
        self.task = asyncio.create_task(self._task())


    def disconnect(self):
        if self.task:
            self.task.cancel()
            self.task = None
    

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


    async def _task(self):
       
        # Init MQTT structure
        await self.sensors.publish(self.name, type = name, rows = self.rows, columns = self.cols, **self.get_states() )

        while True:
            updated = False
            try:

                int_stat = self.read_register(self.REG_INT_STAT)[0]
                
                if int_stat not in [self.INT_STAT_GPI_INT, self.INT_STAT_K_INT]:
                    # No events in FIFO are key events
                    self.write_register(self.REG_INT_STAT, 0xFF)
                    await asyncio.sleep(self.interval_ms / 1000.0)
                    continue

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
                        if action := self.mapped_actions.get(str(key), None):
                            try: 
                                await self.actions.execute(action)
                            except Exception as e:
                                logger.error(f"Error performing {name.upper()} key-press action for key: {key}, action {action}: {e.__class__.__name__}: {e}")
                                await self.sensors.publish(self.name, type = name, inop = { 'exception': f"{e.__class__.__name__}: {e}" })   
                    updated = True
                  
                self.write_register(self.REG_INT_STAT, 0xFF)          
 
            except Exception as e:
                logger.error(f"Error reading {name.upper()} buttons: {e.__class__.__name__}: {e}")
                await self.sensors.publish(self.name, type = name, inop = { 'exception': f"{e.__class__.__name__}: {e}" })
                # In case of recurring error, do not spam log/system. Sleep 5s
                await asyncio.sleep(5)
            
            if updated:
                # Should we send state of all buttons, or only ones that have changed?
                await self.sensors.publish(self.name, type = name, rows = self.rows, columns = self.cols, **self.get_states() )
            await asyncio.sleep(self.interval_ms / 1000.0)
