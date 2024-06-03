from .base import call

from jeepney import DBusAddress

SETTINGS_DBUS_ADDRESS = DBusAddress('/x1plus/settings', bus_name='x1plus.x1plusd', interface='x1plus.settings')

_settings = None

def get_settings(force = False):
    global _settings
    if _settings == None or force:
        _settings = call(SETTINGS_DBUS_ADDRESS, 'GetSettings')
    return _settings

def get():
    return get_settings().get(*args)

def put_multiple(keys):
    return call(SETTINGS_DBUS_ADDRESS, 'PutSettings', keys)

def put(key, value):
    put_multiple({ key: value })
