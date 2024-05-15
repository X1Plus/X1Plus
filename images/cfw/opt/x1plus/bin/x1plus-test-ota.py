#!/opt/python/bin/python3
import json
import os
import sys

from jeepney import new_method_call, DBusAddress
from jeepney.io.blocking import open_dbus_connection

if not os.path.exists("/etc/bblap"):
    # we must be running in emulation
    conn = open_dbus_connection('SESSION')
else:
    conn = open_dbus_connection('SYSTEM')

msg = new_method_call(DBusAddress('/x1plus/ota', bus_name='x1plus.x1plusd', interface='x1plus.ota'), 'CheckNow', 's', (json.dumps({}), ))
reply = conn.send_and_get_reply(msg)
print(json.loads(reply.body[0]))

msg = new_method_call(DBusAddress('/x1plus/ota', bus_name='x1plus.x1plusd', interface='x1plus.ota'), 'GetStatus', 's', (json.dumps({}), ))
reply = conn.send_and_get_reply(msg)
print(json.loads(reply.body[0]))
