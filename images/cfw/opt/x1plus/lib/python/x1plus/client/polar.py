from .base import call
from . import settings

from jeepney import DBusAddress

POLAR_DBUS_ADDRESS = DBusAddress('/x1plus/polar', bus_name='x1plus.x1plusd', interface='x1plus.polar')

def login(username, pin):
    call(POLAR_DBUS_ADDRESS, 'Login', { "username": username, "pin": pin })

def logout():
    call(POLAR_DBUS_ADDRESS, 'Logout')

def get_status():
    return call(POLAR_DBUS_ADDRESS, 'GetStatus')

###

from datetime import datetime
import time

def _cmd_status(args = None):
    print(get_status())

def _cmd_login(args):
    print("Logging in to Polar Cloud.")
    login(args.username[0], args.pin[0])
    _cmd_status()

def _cmd_logout(arg):
    print("Logging out of Polar Cloud.")
    logout()
    _cmd_status()

def add_subparser(subparsers):
    polar_parser = subparsers.add_parser('polar', help="manage Polar Cloud connection")
    polar_subparsers = polar_parser.add_subparsers(title = 'subcommands', required = True)

    polar_status_parser = polar_subparsers.add_parser('status', help="print current Polar Cloud status")
    polar_status_parser.set_defaults(func=_cmd_status)

    polar_login_parser = polar_subparsers.add_parser('login', help="log in to Polar Cloud")
    polar_login_parser.add_argument('username', nargs=1, type=str, help="username to log in with")
    polar_login_parser.add_argument('pin', nargs=1, type=str, help="PIN to log in with")
    polar_login_parser.set_defaults(func=_cmd_login)

    polar_logout_parser = polar_subparsers.add_parser('logout', help="log out from Polar Cloud")
    polar_logout_parser.set_defaults(func=_cmd_logout)
