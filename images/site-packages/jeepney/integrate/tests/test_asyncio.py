import asyncio

import pytest

from jeepney import DBusAddress, new_method_call
from jeepney.bus_messages import message_bus
from jeepney.integrate.asyncio import (
    connect_and_authenticate, Proxy
)
from jeepney.io.tests.utils import have_session_bus

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not have_session_bus, reason="Tests require DBus session bus"
    ),
]

@pytest.fixture()
async def session_proto():
    transport, proto = await connect_and_authenticate(bus='SESSION')
    yield proto
    transport.close()

async def test_connect_old(session_proto):
    assert session_proto.unique_name.startswith(':')

bus_peer = DBusAddress(
    bus_name='org.freedesktop.DBus',
    object_path='/org/freedesktop/DBus',
    interface='org.freedesktop.DBus.Peer'
)

async def test_send_and_get_reply_old(session_proto):
    ping_call = new_method_call(bus_peer, 'Ping')
    reply_body = await asyncio.wait_for(
        session_proto.send_message(ping_call), timeout=5
    )
    assert reply_body == ()

async def test_proxy_old(session_proto):
    proxy = Proxy(message_bus, session_proto)
    name = "io.gitlab.takluyver.jeepney.examples.Server"
    res = await proxy.RequestName(name)
    assert res in {(1,), (2,)}  # 1: got the name, 2: queued

    has_owner, = await proxy.NameHasOwner(name)
    assert has_owner is True
