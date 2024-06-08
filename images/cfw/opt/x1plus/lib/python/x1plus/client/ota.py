from .base import call
from . import settings

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

def _cmd_download(args):
    status = get_status()

    if status['status'] != 'IDLE':
        print("OTA engine is not idle -- cannot start download.")
        return
    
    if not status['ota_available']:
        print("No updates are available.")
        return
    
    if status['ota_is_downloaded'] and (status['ota_base_is_downloaded'] or not args.base):
        print("Nothing to do: all requested firmware is already downloaded.")
        return
    
    print("Starting OTA download.")
    download(base_firmware = args.base)
    
    print("Waiting for download to complete...")
    while True:
        status = get_status()
        if status['status'] == 'IDLE':
            break
        print(f"Status: {status['status']}: {status['download']['bytes']}/{status['download']['bytes_total']} bytes...")
        time.sleep(0.5)

    # XXX: check status['download']['last_error']?    
    _cmd_status()

def _cmd_update(args):
    status = get_status()

    if status['status'] != 'IDLE':
        print("OTA engine is not idle -- cannot start update.")
        return
    
    if not status['ota_available']:
        print("No updates are available.")
        return
    
    if not (status['ota_is_downloaded'] and status['ota_base_is_downloaded']):
        print("Update is not fully downloaded -- cannot install.")
        return

    print(f"Rebooting to install X1Plus version {status['ota_info']['cfwVersion']} in 5 seconds -- press ctrl-C to abort!")
    time.sleep(5)
    
    update()

def _cmd_set_url(args):
    if args.url == "":
        args.url = None
    
    if args.url is None:
        print("Resetting ota.json URL to default.")
    else:
        print(f"Setting ota.json URL to \"{args.url}\".")
    
    settings.put("ota.json_url", args.url)

def add_subparser(subparsers):
    ota_parser = subparsers.add_parser('ota', help="manage Over-The-Air update engine")
    ota_subparsers = ota_parser.add_subparsers(title = 'subcommands', required = True)

    ota_status_parser = ota_subparsers.add_parser('status', help="print current OTA engine status")
    ota_status_parser.set_defaults(func=_cmd_status)

    ota_check_parser = ota_subparsers.add_parser('check', help="check for new over-the-air updates")
    ota_check_parser.set_defaults(func=_cmd_check)

    ota_download_parser = ota_subparsers.add_parser('download', help="start an update downloading, if one is available")
    ota_download_parser.add_argument('--base', action="store_true", help="download base firmware as well as X1Plus update, if needed")
    ota_download_parser.set_defaults(func=_cmd_download)

    ota_update_parser = ota_subparsers.add_parser('update', help="immediately apply a pending update, if one is available")
    ota_update_parser.set_defaults(func=_cmd_update)
    
    ota_set_url_parser = ota_subparsers.add_parser('set-url', help="change the URL to check for updates from")
    ota_set_url_parser.add_argument('url', action="store", nargs="?", help="URL for an ota.json; if not specified, returns to X1Plus defaults")
    ota_set_url_parser.set_defaults(func=_cmd_set_url)
