"""Deprecated: use jeepney.io.asyncio instead"""
import asyncio
from warnings import warn

from jeepney import Parser, MessageType
from jeepney.auth import AuthenticationError, BEGIN, make_auth_external, SASLParser
from jeepney.bus import get_bus
from jeepney.bus_messages import message_bus
from jeepney.routing import Router
from jeepney.wrappers import ProxyBase

warn("jeepney.integrate.asyncio is deprecated: please use jeepney.io.asyncio "
     "instead.", stacklevel=2)

class DBusProtocol(asyncio.Protocol):
    def __init__(self):
        self.auth_parser = SASLParser()
        self.parser = Parser()
        self.router = Router(asyncio.Future)
        self.authentication = asyncio.Future()
        self.unique_name = None

    def connection_made(self, transport):
        self.transport = transport
        self.transport.write(b'\0' + make_auth_external())

    def _authenticated(self):
        self.transport.write(BEGIN)
        self.authentication.set_result(True)
        self.data_received = self.data_received_post_auth
        self.data_received(self.auth_parser.buffer)

    def data_received(self, data):
        self.auth_parser.feed(data)
        if self.auth_parser.authenticated:
            self._authenticated()
        elif self.auth_parser.error:
            self.authentication.set_exception(AuthenticationError(self.auth_parser.error))

    def data_received_post_auth(self, data):
        for msg in self.parser.feed(data):
            self.router.incoming(msg)

    def send_message(self, message):
        if not self.authentication.done():
            raise RuntimeError("Wait for authentication before sending messages")

        future = self.router.outgoing(message)
        data = message.serialise()
        self.transport.write(data)
        return future

    async def send_and_get_reply(self, message):
        if message.header.message_type != MessageType.method_call:
            raise TypeError("Only method call messages have replies")

        return await self.send_message(message)

class Proxy(ProxyBase):
    """An asyncio proxy for calling D-Bus methods

    :param msggen: A message generator object.
    :param DBusProtocol proto: Protocol object to send and receive messages.
    """
    def __init__(self, msggen, protocol):
        super().__init__(msggen)
        self._protocol = protocol

    def __repr__(self):
        return 'Proxy({}, {})'.format(self._msggen, self._protocol)

    def _method_call(self, make_msg):
        async def inner(*args, **kwargs):
            msg = make_msg(*args, **kwargs)
            assert msg.header.message_type is MessageType.method_call
            return await self._protocol.send_and_get_reply(msg)

        return inner


async def connect_and_authenticate(bus='SESSION', loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()
    (t, p) = await loop.create_unix_connection(DBusProtocol, path=get_bus(bus))
    await p.authentication
    bus = Proxy(message_bus, p)
    hello_reply = await bus.Hello()
    p.unique_name = hello_reply[0]
    return (t, p)
