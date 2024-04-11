#!/opt/python/bin/python3
import os, dds
import copy
from functools import lru_cache 
from threading import Thread
import json
import subprocess


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


def x1p_settings():
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

    # Before we startup, do we have our settings file? Try to read, create if it doesn't exist.
    try:
        with open(f"/mnt/sdcard/x1plus/printers/{_get_sn()}/settings.json", 'r') as fh:
            settings = json.load(fh)
    except FileNotFoundError as exc:
        print("Settings file does not exist, creating with defaults...")
        # TODO: Add logic here (call helper function) to check for flag files, 
        # and adjust our defaults to match
        with open(f"/mnt/sdcard/x1plus/printers/{_get_sn()}/settings.json", 'w') as f:
            json.dump(DEFAULT_X1PLUS_SETTINGS, f)

    # Setup DDS
    dds_rx_queue = dds.subscribe("device/x1plus/request")
    dds_tx_pub = dds.publisher("device/x1plus/report")

    # flush the input queue on launch, to play it safe.
    # TODO: is this really needed?
    while not dds_rx_queue.empty():
        dds_rx_queue.get()

    print ("X1Plus Settings Started!")
    try:
        # Start our 'wait loop', aka daemon
        while True:
            try:
                resp = dds_rx_queue.get() # We wait til we get a message
                resp = json.loads(resp) # Try to load into json

                # Not for us? ignore and carry on
                if 'settings' not in resp:
                    pass
            except:
                # Keep going if we have an issue
                pass

            # If we are here, we have a valid settings request
            print(f"x1p_settings(): Request of {resp['settings']}")

            # Parse what we were asked to do
            if "set" in resp['settings']:
                setting_set = resp['settings']['set']
                # We can only handle a dict
                if not isinstance(setting_set, dict):
                    resp = {"rejected_changes": setting_set}
                else:
                    # Update settings and save
                    settings = copy.deepcopy(settings) | setting_set
                    with open(f"/mnt/sdcard/x1plus/printers/{_get_sn()}/settings.json", 'w') as f:
                        json.dump(settings, f)
                    resp = setting_set
            else:
                # Unknown request, reply with error
                resp = {"rejected_changes": setting_set}

            # Submit our response
            print(f"x1p_settings(): Replying with {resp}")
            dds_tx_pub(json.dumps({'settings': resp}))
    except Exception as e:
        print(f"x1p_settings(): FATAL, exception of main loop hit! Error of: {e}")
        raise

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


def startup():
    #TODO: check if we are already running

    # Define our threads
    settings = Thread(target=x1p_settings)

    # Start our threads
    settings.start()


if __name__ == "__main__":
    try:
        startup()
    except:
        dds.shutdown()
        raise
