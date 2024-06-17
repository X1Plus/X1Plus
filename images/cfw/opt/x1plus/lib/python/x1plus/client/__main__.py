import argparse
from . import ota, settings, base

"""
Basic command-line X1Plus management tool.
"""

parser = argparse.ArgumentParser(prog='x1plus', description='Command-line management tool for X1Plus')
subparsers = parser.add_subparsers(title = 'commands', required = True)

ota.add_subparser(subparsers)
settings.add_subparser(subparsers)

def _cmd_i2c(args):
    from jeepney import DBusAddress
    I2C_DBUS_ADDRESS = DBusAddress('/x1plus/i2c', bus_name='x1plus.x1plusd', interface='x1plus.i2c')
    print(base.call(I2C_DBUS_ADDRESS, 'GetSht41'))

i2c = subparsers.add_parser('i2c')
i2c.set_defaults(func=_cmd_i2c)

args = parser.parse_args()
args.func(args)