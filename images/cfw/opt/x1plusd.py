#!/opt/python/bin/python3
import os, dds
import copy
from functools import lru_cache 
from threading import Thread
import json
import subprocess
import traceback
import time

# probably this should be encapsulated in a DDS class, but...

dds_request_queue = None
dds_report_publisher = None

def dds_report(data):
    if dds_report_publisher:
        dds_report_publisher(json.dumps(data))

dds_handlers = {}

def dds_start():
    global dds_request_queue, dds_report_publisher
    
    dds_request_queue = dds.subscribe("device/x1plus/request")
    dds_report_publisher = dds.publisher("device/x1plus/report")
    print("x1plusd: waiting for DDS startup")
    time.sleep(2) # evade, don't solve, race conditions

def dds_loop():
    while True:
        req_raw = dds_request_queue.get() # blocks until a message arrives
        try:
            req = json.loads(req_raw)
            for k in dds_handlers:
                if k in req:
                    dds_handlers[k](req)
        except Exception as e:
            # TODO: log this
            print(f"x1plusd: exception while handling request {req_raw}")
            traceback.print_exc()


# TODO: actually write this later
# def ota_service():   
#     #TODO: check if we have OTA service enabled/disabled via settings

#     # Setup DDS
#     dds_rx_queue = dds.subscribe("device/x1plus/request")
#     dds_tx_pub = dds.publisher("device/x1plus/report")

#     #dds_tx_pub(json.dumps({ 'command': 'ota', 'test': True }))

#     print("X1Plus OTA started!")

#     # flush the input queue on launch, to play it safe.
#     # TODO: is this really needed?
#     while not dds_rx_queue.empty():
#         dds_rx_queue.get()

#     # Start our 'wait loop', aka daemon
#     while True:
#         try:
#             resp = dds_rx_queue.get() # We wait til we get a message
#             resp = json.loads(resp) # Try to load into json
#             if 
#         except:
#             # Keep going if we have an issue
#             pass


class SettingsService:
    """
    Our settings daemon service, used to set X1Plus settings.
    
    Input DDS: device/x1plus/request
    Output DDS: device/x1plus/report

    payload key: settings

    Set Examples:
    Request: {"settings": {"set": {"KEY": "VALUE"}} # sets a setting
    Response: {"settings": {"changes": {"KEY": "VALUE"}}}

    Request: {"settings": {"set": {"KEY": {"NESTED_KEY":"VALUE"}}}} # sets a nested setting
    Response: {"settings": {"changes": {"KEY": {"NESTED_KEY":"VALUE"}}}}

    Request: {"settings": {"set": "str" } # Incorrect set usage, requires a dict
    Response: {"settings": {"rejected_changes": "str"}}
    """
    DEFAULT_X1PLUS_SETTINGS = {
        "ota": {
            "enable_check": False
        },
        "quick_boot": False,
        "dump_emmc": False,
        "sdcard_syslog": False
    }

    def __init__(self):
        settings_dir = f"/mnt/sdcard/x1plus/printers/{_get_sn()}"
        self.filename = f"{settings_dir}/settings.json"
        os.makedirs(settings_dir, exist_ok = True)
    
        # Before we startup, do we have our settings file? Try to read, create if it doesn't exist.
        try:
            with open(self.filename, 'r') as fh:
                self.settings = json.load(fh)
        except FileNotFoundError as exc:
            # TODO: log to syslog
            print("Settings file does not exist, creating with defaults...")
            # TODO: Add logic here (call helper function) to check for flag files, 
            # and adjust our defaults to match
            self.settings = copy.deepcopy(SettingsService.DEFAULT_X1PLUS_SETTINGS)
            self._save()
            dds_report({'settings': {'changes': self.settings}})

        # register it...
        dds_handlers['settings'] = self._handle
        
    def _save(self):
        # XXX: atomically rename this
        
        with open(self.filename, 'w') as f:
            json.dump(self.settings, f, indent = 4)

    def _handle(self, req):
        # Parse what we were asked to do
        if "set" in req['settings']:
            settings_set = req['settings']['set']

            if not isinstance(settings_set, dict):
                # TODO: log this to the syslog
                print(f"x1p_settings: set request {req} is not a dictionary")
                return

            self.settings.update(settings_set)
            self._save()
            
            # TODO: log this to the syslog
            print(f"x1p_settings: updated {settings_set}")
            
            # Inform everyone else on the system, only *after* we have saved
            # and made it visible.  That way, anybody who wants to know
            # about this setting either will have read it from disk
            # initially, or will have heard about the update from us after
            # they read it.
            dds_report({'settings': {'changes': settings_set}})
        else:
            # TODO: log this to the syslog
            print(f"x1p_settings: settings request {req} was not a known opcode")

# TODO: hoist this into an x1plus package
@lru_cache(None)
def _get_sn():
    """
    Used to get the Serial Number for the Printer
    """
    try:
        return subprocess.check_output(["bbl_3dpsn"], stderr=subprocess.DEVNULL).decode('utf-8')
    except:
        print("_get_sn() failed to run bbl_3dpsn, and we are now dazed and confused. Exiting...")
        raise

if __name__ == "__main__":
    #TODO: check if we are already running
    try:
        dds_start()
        
        settings = SettingsService()
        dds_loop()
    except:
        dds.shutdown()
        raise
