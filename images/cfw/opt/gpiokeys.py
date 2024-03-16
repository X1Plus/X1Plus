#!/usr/bin/env python3

import os, subprocess, re
import json
import time
from evdev import InputDevice, categorize, ecodes

KEY_POWER = 116
KEY_STOP = 128
LONG_PRESS_THRESHOLD = 0.850 # seconds
CFG_FILE = "/config/screen/printer.json"

# Ensure that these stay in sync with HardwarePage.qml!
ACTION_REBOOT = 0
ACTION_SET_TEMP = 1
ACTION_PAUSE_PRINT = 2
ACTION_ABORT_PRINT = 3
ACTION_TOGGLE_SCREENSAVER = 4
ACTION_NOZZLE_IMAGE = 5
ACTION_MACRO = 6

def get_printer_setting(key, default_value):
    try:
        with open(CFG_FILE, "r") as file:
            data = json.load(file)
            return data.get(key, default_value)
    except Exception as e:
        print(f"error loading key {key} from {CFG_FILE}: {e}")
        return default_value

# The following routines are sort of hokey -- it would be nice to do this
# over DDS later, but we don't have a particularly stable Python DDS
# implementation right now, so this is certainly better than locking up the
# printer.
def qml_action(param):
    with open("/tmp/button_action", "w") as file:
        file.write(param)

def mqtt_pub(message):
    j = json.dumps(message)
    print(f"mqtt_pub: {j}")
    command = f"source /usr/bin/mqtt_access.sh; mqtt_pub '{message}'"
    try:
        subprocess.run(command, shell=True, check=True, executable="/bin/bash")
    except subprocess.CalledProcessError as e:
        print(f"{e}")

def send_gcode(file_path):
    if not os.path.isfile(file_path):
        print(f"file {file_path} does not exist")

    with open(file_path, "r") as file:
        gcode_lines = file.read().lstrip("\n").splitlines()
        gcode_processed = [re.sub(r"([\\\"])", r"\\\1", line) for line in gcode_lines]
        gcode_content = json.dumps("\n".join(gcode_processed)).strip('"')

    mqtt_pub({"print": {"command": "gcode_line", "sequence_id": "1", "param": gcode_content}})

def send_gcode_line(gcodeline):
    mqtt_pub(json.dumps({"print": {"command": "gcode_line", "sequence_id": "1", "param": gcodeline}}))

def setTemp(target, temp):
    if target == "nozzle":
        if temp > 300:
            temp = 200
        print(f"setting nozzle temp {temp}")
        send_gcode_line(f"M109 S{temp}")
    elif target == "bed":
        if temp > 120:
            temp = 35
        print(f"setting bed temp {temp}")
        send_gcode_line(f"M140 S{temp}")
    else:
        print(f"setTemp: unknown target {target}")

#Do we want to keep this function in here for some reason? I initially added it as an LCD toggle function..
#however it kills touch input to the screen which has no functional purpose? leaving for now just in case
# def lcd_toggle():
#     try:
#         pid = subprocess.check_output(["pidof", "bbl_screen"]).decode().strip()
#     except subprocess.CalledProcessError:
#         print("bbl_screen process not running.")
#         return
# 
#     state = open(f"/proc/{pid}/stat").split(' ')[2]
#     
#     # Note that we are not the only ones with this bizarre idea.  This is
#     # how the platform natively does it!  See /usr/bin/power_control.sh.
#     if state == 'T' or state == 't':
#         print("Resuming bbl_screen...")
#         with open("/sys/devices/platform/display-subsystem/suspend", "w") as file:
#             file.write("0")
#         os.kill(int(pid), signal.SIGCONT)
#     else:
#         print("Suspending bbl_screen...")
#         os.kill(int(pid), signal.SIGSTOP)
#         with open("/sys/devices/platform/display-subsystem/suspend", "w") as file:
#             file.write("1")


def key_action(action):
    if isinstance(action, int):
        params = []
    elif isinstance(action, str) and " " in action:
        params = action.split(" ")
        action = int(params[0])
    else:
        action = ACTION_TOGGLE_SCREENSAVER
        print("Error parsing setting")

    print(action)
    print(params)

    if action == ACTION_REBOOT:
        print("Reboot")
        os.system("reboot")
    elif action == ACTION_SET_TEMP:
        print("Set Temp")
        setTemp(params[1], int(params[2]))
    elif action == ACTION_PAUSE_PRINT:
        print("Pause print")
        qml_action("2")
    elif action == ACTION_ABORT_PRINT:
        print("Abort print")
        qml_action("1")
    elif action == ACTION_TOGGLE_SCREENSAVER:
        print("Toggle screensaver")
        qml_action("0")
    elif action == ACTION_NOZZLE_IMAGE:
        print("Nozzle Image")
        qml_action("3")
    elif action == ACTION_MACRO:  # json key ex: "6 /mnt/sdcard/macro.py" or "6 /mnt/sdcard/macro.gcode"
        print("Macro")
        if params[1].endswith(".py"):
            os.system(f"/opt/python/bin/python3 {params[1]}")
            print(f"Run python script:{params[1]}")
        elif params[1].endswith(".gcode"):
            print(f"Run gcode {params[1]}")
            send_gcode(params[1])

class Button:
    #DEBOUNCE_DELAY = 30/1000 #will mess with this at a later date..
    def __init__(self, scancode, name, default_short, default_long):
        self.pressed = None
        self.scancode = scancode
        self.name = name
        self.default_short = default_short
        self.default_long = default_long
    
    def press(self):
        self.pressed = time.time()
    
    def release(self):
        if time.time() - self.pressed < LONG_PRESS_THRESHOLD:
            key_action(get_printer_setting(f"cfw_{self.name}_short", self.default_short))
        else:
            key_action(get_printer_setting(f"cfw_{self.name}_long" , self.default_long))
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
finally:
    device.ungrab()