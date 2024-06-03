from .base import call

from jeepney import DBusAddress

OTA_DBUS_ADDRESS = DBusAddress('/x1plus/ota', bus_name='x1plus.x1plusd', interface='x1plus.ota')

def check_now():
    return call(OTA_DBUS_ADDRESS, 'CheckNow')['status']

def check_files():
    call(OTA_DBUS_ADDRESS, 'CheckFiles')

def download(base_firmware = True):
    call(OTA_DBUS_ADDRESS, 'Download', { "base_firmware": base_firmware })

def update():
    call(OTA_DBUS_ADDRESS, 'Update')

def get_status():
    return call(OTA_DBUS_ADDRESS, 'GetStatus')

###

from datetime import datetime
import time

def _cmd_status(args = None):
    status = get_status()
    if not status['enabled']:
        print("Over-the-air update engine is disabled.")
        return
    
    status_map = {
        'IDLE': "idle",
        'CHECKING_OTA': "checking for updates",
        'DOWNLOADING_X1P': "downloading an X1Plus update",
        'DOWNLOADING_BASE': "downloading a base firmware",
    }
    print(f"Over-the-air update engine is {status_map.get(status['status'], status['status'])}.")
    print("")
    if status['last_checked'] is not None:
        print(f"Last successful check for updates {datetime.fromtimestamp(status['last_checked']).ctime()}.")
    else:
        print(f"No successful update checks since reboot.")
    if status['err_on_last_check']:
        print(f"Previous update check attempt failed.")
    else:
        print(f"Previous update check was successful.")

    print("")
    if not status['ota_available']:
        print(f"No updates are available.")
    else:
        print(f"An X1Plus update is available!")
        print(f"  New version: {status['ota_info']['cfwVersion']}, built {status['ota_info']['date']}")
        if status['ota_is_downloaded']:
            print(f"  X1Plus update is downloaded.")
        else:
            print(f"  X1Plus update file has NOT been downloaded.  Use `x1plus ota download` to download it.")
        if status['ota_base_is_downloaded']:
            print(f"  Base firmware is downloaded.")
        else:
            print(f"  Base firmware image has NOT been downloaded.  Use `x1plus ota download --base` to download it, or download from {status['ota_info']['base_update_url']} .")

    # ... download status ...

def _cmd_check(args):
    print("Triggering OTA check.")
    check_now()
    
    print("Waiting for check to complete...")
    while get_status()['status'] == 'CHECKING_OTA':
        time.sleep(0.5)
    print("")
    _cmd_status()

def add_subparser(subparsers):
    ota_parser = subparsers.add_parser('ota', help="manage Over-The-Air update engine")
    ota_subparsers = ota_parser.add_subparsers(title = 'subcommands', required = True)

    ota_status_parser = ota_subparsers.add_parser('status', help="print current OTA engine status")
    ota_status_parser.set_defaults(func=_cmd_status)

    ota_check_parser = ota_subparsers.add_parser('check', help="check for new over-the-air updates")
    ota_check_parser.set_defaults(func=_cmd_check)

    ota_download_parser = ota_subparsers.add_parser('download', help="start an update downloading, if one is available")
    ota_download_parser.add_argument('--base', action="store_true", help="download base firmware as well as X1Plus update, if needed")

    ota_update_parser = ota_subparsers.add_parser('update', help="immediately apply a pending update, if one is available")
