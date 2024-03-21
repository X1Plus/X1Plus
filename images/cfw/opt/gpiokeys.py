#!/usr/bin/env python3

import os, subprocess, re, time, json, dds
from evdev import InputDevice, categorize, ecodes

KEY_POWER = 116
KEY_STOP = 128
#KEY_DOOR = 134 #DOOR SENSOR

LONG_PRESS_THRESHOLD = 0.850 # seconds
CFG_FILE = "/mnt/sdcard/x1plus/buttons.json"

# Ensure that these stay in sync with HardwarePage.qml!
ACTION_REBOOT = 0
ACTION_SET_TEMP = 1
ACTION_PAUSE_PRINT = 2
ACTION_ABORT_PRINT = 3
ACTION_TOGGLE_SCREENSAVER = 4
ACTION_MACRO = 5
<<<<<<< Updated upstream

gpio_dds_publisher = dds.publisher('device/request/print')
=======
>>>>>>> Stashed changes

gpio_dds_publisher = dds.publisher('device/request/print')

def get_button_action(button_name, press_type, default_value):  
    try:
        if os.path.exists(CFG_FILE):
            with open(CFG_FILE, "r") as file:
                data = json.load(file)
                button_config = data.get(button_name, {})
                action_setting = button_config.get(press_type, default_value)
                return action_setting
    except Exception as e:
        print(f"Error loading setting for {button_name} {press_type} from {CFG_FILE}: {e}")
        return default_value
<<<<<<< Updated upstream

=======
    else:
        return default_value     	
>>>>>>> Stashed changes
def send_gcode(file_path):
    if not os.path.isfile(file_path):
        print(f"file {file_path} does not exist")

    with open(file_path, "r") as file:
        gcode_lines = file.read().lstrip("\n").splitlines()
        gcode_processed = [re.sub(r"([\\\"])", r"\\\1", line) for line in gcode_lines]
        gcode_content = json.dumps("\n".join(gcode_processed)).strip('"')
        gpio_dds_publisher(json.dumps({"command": "gcode_line", "sequence_id": "1", "param": gcode_content}))

def event_handler(action_setting):
    if isinstance(action_setting, int):
        action_code = action_setting
        params = {}

    elif isinstance(action_setting, dict):
<<<<<<< Updated upstream
        action_code = action_setting.get("action_code", ACTION_TOGGLE_SCREENSAVER)
        params = action_setting.get("param", {}) if isinstance(action_setting.get("param"), dict) else {}
=======
        action_code = action_setting.get("action", ACTION_TOGGLE_SCREENSAVER)
        params = action_setting.get("parameters", {}) if isinstance(action_setting.get("param"), dict) else {}
>>>>>>> Stashed changes
    else:
        print("Error: Invalid action setting")
        return
    if action_code == ACTION_REBOOT:
        os.system("reboot")
    elif action_code in [ACTION_PAUSE_PRINT,ACTION_ABORT_PRINT,ACTION_TOGGLE_SCREENSAVER,ACTION_SET_TEMP]:
        dds_payload =  json.dumps({"command": "gpio_action", "action_code": action_code, "param": params, "sequence_id":"0"})
        print(dds_payload)
        gpio_dds_publisher(dds_payload)
    elif action_code == ACTION_MACRO:
        file_path = params.get("file_path", "")
<<<<<<< Updated upstream
        if file_path.endswith(".py"):
            os.system(f"/opt/python/bin/python3 {file_path}")
            print(f"Run python script:{file_path}")
=======
        args = params.get("arguments","")
        if file_path.endswith(".py"):
            os.system(f"/opt/python/bin/python3 {file_path} {args}")
            print(f"Run python script:{file_path} {args}")
>>>>>>> Stashed changes
        elif file_path.endswith(".gcode"):
            print(f"Run gcode {file_path}")
            send_gcode(file_path)

class Button:
    def __init__(self, scancode, name, default_short, default_long):
        self.pressed = None
        self.scancode = scancode
        self.name = name
        self.default_short = {"action": default_short, "parameters": {}}
        self.default_long = {"action": default_long, "parameters": {}}

    def press(self):
        self.pressed = time.time()

    def release(self):
<<<<<<< Updated upstream
    	action = get_printer_setting(f"cfw_gpio_{self.name}")
        if time.time() - self.pressed < LONG_PRESS_THRESHOLD:
        	
            event_handler(get_printer_setting(action["short"], self.default_short))
        else:
            event_handler(get_printer_setting(action["long"], self.default_long))
=======
        elapsed_time = time.time() - self.pressed
        press_type = "shortPress" if elapsed_time < LONG_PRESS_THRESHOLD else "longPress"
        action_setting = get_button_action(f"cfw_{self.name}", press_type,
                                           self.default_short if press_type == "shortPress" else self.default_long)
        event_handler(action_setting)
>>>>>>> Stashed changes
        self.pressed = None
        pass
        

buttons = [
    Button(scancode = KEY_POWER, name = "power", default_short = ACTION_TOGGLE_SCREENSAVER, default_long = ACTION_REBOOT),
    Button(scancode = KEY_STOP,  name = "estop", default_short = ACTION_PAUSE_PRINT, default_long = ACTION_ABORT_PRINT),
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