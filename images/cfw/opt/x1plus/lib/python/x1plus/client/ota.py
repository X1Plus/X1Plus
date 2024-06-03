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
