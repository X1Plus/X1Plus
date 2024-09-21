# Always invoke this with python3 -m x1plus.services.gpiokeys.

import os
import re
import x1plus.dds
import json
import time 
from fcntl import ioctl
import logging
import struct 

MONITORED_PINS = {116: "KEY_POWER", 128: "KEY_STOP", 134: "KEY_OPEN"}
EVIOCGRAB = 0x40044590
EV_SYN = 0x00
EV_KEY = 0x01
LONG_PRESS_THRESHOLD = 0.850 # seconds
KEY_POWER = 116
KEY_STOP = 128
KEY_DOOR = 134

gpio_dds_publisher = x1plus.dds.publisher('device/x1plus')
gpio_log = logging.getLogger(__name__)

def send_dds(name, press_type):
    dds_payload = json.dumps({
        "gpio": {
            "button": name,
            "event": press_type
        }
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
        

buttons = [
    Button(scancode = KEY_POWER, name = "power"),
    Button(scancode = KEY_STOP,  name = "estop"),
    Button(scancode = KEY_DOOR,  name = "door"),
]


def main():
    while True:
        try:
            with open(gpio_device_path, 'rb') as dev:
                try:
                    ioctl(dev, EVIOCGRAB, 1)
                except Exception as e:
                    print(f"Error: {e}")
                while True:
                    try:
                        r, _, _ = select.select([dev], [], [], 1)
                        if dev in r:
                            event = dev.read(16)
                            if event:
                                try:
                                    (tv_sec, tv_usec, type, code, value) = struct.unpack('LLHHI', event)
                                    if type == EV_KEY and code in MONITORED_PINS:
                                        button = next((b for b in buttons if b.scancode == code), None)
                                        if button:
                                            if value == 1:
                                                button.press()
                                            elif value == 0:
                                                button.release()
                                except struct.error as e:
                                    print(e)
                    except Exception as e:
                        print(f"error: {str(e)}")
                        break
        except Exception as e:
            print(f"Error opening device: {str(e)}")
            time.sleep(5) #retry?
            
if __name__ == "__main__":
    import setproctitle
    setproctitle.setproctitle(__spec__.name)
    main()
