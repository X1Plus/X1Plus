#!/usr/bin/env python3

import os
import re
import dds
import json
import time 
from evdev import InputDevice, categorize, ecodes

LONG_PRESS_THRESHOLD = 0.850 # seconds
KEY_POWER = 116
KEY_STOP = 128
#KEY_DOOR = 134 #DOOR SENSOR


gpio_dds_publisher = dds.publisher('device/request/print')

def send_dds(name, press_type):
	dds_payload = json.dumps({
		"command": "gpio_event",
		"button": name,
		"param": press_type,
		"sequence_id": "0"
	})
	gpio_dds_publisher(dds_payload)


class Button:
    def __init__(self, scancode, name):
        self.pressed = None
        self.scancode = scancode
        self.name = name
    def press(self):
        self.pressed = time.time()

    def release(self):
        elapsed_time = time.time() - self.pressed
        press_type = "shortPress" if elapsed_time < LONG_PRESS_THRESHOLD else "longPress"
        send_dds(self.name, press_type)
        self.pressed = None
        pass
        

buttons = [
    Button(scancode = KEY_POWER, name = "cfw_power"),
    Button(scancode = KEY_STOP,  name = "cfw_estop"),
]

device = InputDevice("/dev/input/by-path/platform-gpio-keys-event")
device.grab()

try:
    for event in device.read_loop():
        if event.type != ecodes.EV_KEY:
            continue
        
        data = categorize(event)
        for button in buttons:
            if button.scancode == data.scancode:
                if data.keystate:
                    button.press()
                else:
                    button.release()
except:
	dds.shutdown()
	raise

finally:
    device.ungrab()