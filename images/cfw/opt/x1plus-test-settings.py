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

upd = {}
for arg in sys.argv[1:]:
    k,v = arg.split('=', 1)
    if v == 'None':
        v = None
    upd[k] = v
msg = new_method_call(DBusAddress('/x1plus/settings', bus_name='x1plus.x1plusd', interface='x1plus.settings'), 'PutSettings', 's', (json.dumps(upd), ))
reply = conn.send_and_get_reply(msg)
print(json.loads(reply.body[0]))

msg = new_method_call(DBusAddress('/x1plus/settings', bus_name='x1plus.x1plusd', interface='x1plus.settings'), 'GetSettings', 's', (json.dumps({}), ))
reply = conn.send_and_get_reply(msg)
print(json.loads(reply.body[0]))
