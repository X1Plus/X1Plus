import json
import os
import sys

from jeepney import new_method_call, DBusAddress, MessageType, HeaderFields
from jeepney.io.blocking import open_dbus_connection

if 'x1plus.services.x1plusd' in sys.modules:
    # x1plus.client uses blocking DBus API calls, while x1plusd needs to use
    # the jeepney asyncio interface.  don't do this!
    raise ImportError("you cannot import x1plus.client from inside x1plusd!")

if not os.path.exists("/etc/bblap"):
    # we must be running in emulation
    dbus_connection = open_dbus_connection('SESSION')
else:
    dbus_connection = open_dbus_connection('SYSTEM')

def call(addr, method, param = None):
    msg = new_method_call(addr, method, 's', (json.dumps(param), ))
    reply = dbus_connection.send_and_get_reply(msg)
    if reply.header.message_type == MessageType.error:
        error_name = reply.header.fields.get(HeaderFields.error_name, 'unknown-error')
        raise RuntimeError(error_name, reply.body[0] if len(reply.body) > 0 else '')
    return json.loads(reply.body[0])

