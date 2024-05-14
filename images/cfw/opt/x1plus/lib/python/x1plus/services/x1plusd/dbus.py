import json

import logging
import x1plus.utils

from jeepney import (
    HeaderFields,
    new_method_return,
    new_error,
    DBusAddress,
    new_signal,
)
from jeepney.bus_messages import message_bus, MatchRule
from jeepney.io.asyncio import open_dbus_connection, DBusRouter, Proxy

BUS_NAME = "x1plus.x1plusd"

logger = logging.getLogger(__name__)


async def get_dbus_router():
    if x1plus.utils.is_emulating():
        conn = await open_dbus_connection("SESSION")
    else:
        conn = await open_dbus_connection("SYSTEM")

    router = DBusRouter(conn)

    rv = await Proxy(message_bus, router).RequestName(BUS_NAME)
    if rv != (1,):
        raise RuntimeError(f"failed to attach bus name {BUS_NAME}")

    return router


class X1PlusDBusService:
    """
    An implementation of the very specific DBus service format that goes
    with Bambu's BDbus implementation.

    Bambu DBus methods always have exactly one argument -- a string,
    containing a JSON value -- and always return a string containing a JSON
    value.  Additionally, Bambu DBus signals also always have exactly one
    argument (you guessed it, a string containing a JSON value).  We
    abstract all of the DBus RPC logic into an asyncio task that a would-be
    DBus object can subclass to implement a BDbus-compatible object.
    """

    def __init__(self, router, dbus_interface, dbus_path):
        self.router = router
        self.dbus_interface = dbus_interface
        self.dbus_path = dbus_path

    async def task(self):
        match = MatchRule(
            interface=self.dbus_interface, path=self.dbus_path, type="method_call"
        )
        await Proxy(message_bus, self.router).AddMatch(match)
        with self.router.filter(match, bufsize=0) as queue:
            while True:
                msg = await queue.get()
                method = msg.header.fields[HeaderFields.member]

                if msg.header.fields[HeaderFields.signature] != "s":
                    await self.router.send(
                        new_error(msg, "x1plus.x1plusd.Error.BadSignature")
                    )
                    continue

                arg = msg.body[0]

                # Implement methods in your class of the form:
                #
                #   async def dbus_SomeMethod(self, req):
                #       return { 'resp': req }
                #
                # where the return value and the parameter are both things
                # that can be serialized to JSON values.  If such a method
                # exists, then a DBUS_INTERFACE.SomeMethod invoke this method.
                impl = getattr(self, f"dbus_{method}", None)
                if not callable(impl):
                    logger.warning(f"{method} -> NoMethod")
                    await self.router.send(
                        new_error(msg, "x1plus.x1plusd.Error.NoMethod")
                    )
                    continue

                try:
                    rv = await impl(json.loads(arg))
                except Exception as e:
                    logger.error(f"{method}({arg}) -> exception {e}")
                    await self.router.send(
                        new_error(msg, "x1plus.x1plusd.Error.InternalError")
                    )
                    continue

                logger.debug(f"{method}({arg}) -> {rv}")
                await self.router.send(new_method_return(msg, "s", (json.dumps(rv),)))

    async def emit_signal(self, name, val):
        signal = new_signal(
            DBusAddress("/", interface=self.dbus_interface),
            name,
            signature="s",
            body=(json.dumps(val),),
        )
        await self.router.send(signal)
