"""Deprecated: use jeepney.io.tornado instead"""
from warnings import warn

from jeepney.io.tornado import *

warn("jeepney.integrate.tornado is deprecated. Tornado is now built on top of "
     "asyncio, so please use jeepney.io.asyncio instead.", stacklevel=2)

async def connect_and_authenticate(bus='SESSION'):
    conn = await open_dbus_connection(bus)
    return DBusRouter(conn)


if __name__ == '__main__':
    rtr = IOLoop.current().run_sync(connect_and_authenticate)
    print("Unique name is:", rtr.unique_name)
