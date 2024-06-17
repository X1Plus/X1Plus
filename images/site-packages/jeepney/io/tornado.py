from asyncio import as_completed, Future, wait_for
from itertools import count
import socket
from typing import Optional
from warnings import warn

from tornado.ioloop import IOLoop
from tornado.iostream import IOStream
from tornado.locks import Event
from tornado.queues import Queue, QueueFull

from jeepney.auth import SASLParser, make_auth_external, BEGIN, AuthenticationError
from jeepney.bus import get_bus
from jeepney.low_level import Parser, MessageType, Message, MessageFlag
from jeepney.wrappers import ProxyBase, unwrap_msg
from jeepney.routing import Router
from jeepney.bus_messages import message_bus
from .common import (
    MessageFilters, FilterHandle, ReplyMatcher, RouterClosed, check_replyable,
)

warn("jeepney.io.tornado is deprecated. Tornado is now built on top of "
     "asyncio, so please use jeepney.io.asyncio instead.", stacklevel=2)


class DBusConnection:
    def __init__(self, stream: IOStream):
        self.stream = stream
        self.parser = Parser()
        self.outgoing_serial = count(start=1)
        self.unique_name = None

    async def send(self, message: Message, *, serial=None):
        if serial is None:
            serial = next(self.outgoing_serial)
        # .write() immediately adds all the data to a buffer, so no lock needed
        await self.stream.write(message.serialise(serial))

    async def receive(self) -> Message:
        while True:
            msg = self.parser.get_next_message()
            if msg is not None:
                return msg

            b = await self.stream.read_bytes(4096, partial=True)
            self.parser.add_data(b)

    def close(self):
        self.stream.close()


async def open_dbus_connection(bus='SESSION'):
    bus_addr = get_bus(bus)
    stream = IOStream(socket.socket(family=socket.AF_UNIX))
    await stream.connect(bus_addr)
    await stream.write(b'\0' + make_auth_external())

    auth_parser = SASLParser()
    while not auth_parser.authenticated:
        auth_parser.feed(await stream.read_bytes(1024, partial=True))
        if auth_parser.error:
            raise AuthenticationError(auth_parser.error)

    await stream.write(BEGIN)

    conn = DBusConnection(stream)

    with DBusRouter(conn) as router:
        reply_body = await wait_for(Proxy(message_bus, router).Hello(), 10)
        conn.unique_name = reply_body[0]

    return conn


class DBusRouter:
    def __init__(self, conn: DBusConnection):
        self.conn = conn
        self._replies = ReplyMatcher()
        self._filters = MessageFilters()
        self._stop_receiving = Event()
        IOLoop.current().add_callback(self._receiver)

        # For backwards compatibility - old-style signal callbacks
        self.router = Router(Future)

    async def send(self, message, *, serial=None):
        await self.conn.send(message, serial=serial)

    async def send_and_get_reply(self, message):
        check_replyable(message)
        if self._stop_receiving.is_set():
            raise RouterClosed("This DBusRouter has stopped")

        serial = next(self.conn.outgoing_serial)

        with self._replies.catch(serial, Future()) as reply_fut:
            await self.send(message, serial=serial)
            return (await reply_fut)

    def filter(self, rule, *, queue: Optional[Queue] =None, bufsize=1):
        """Create a filter for incoming messages

        Usage::

            with router.filter(rule) as queue:
                matching_msg = await queue.get()

        :param jeepney.MatchRule rule: Catch messages matching this rule
        :param tornado.queues.Queue queue: Matched messages will be added to this
        :param int bufsize: If no queue is passed in, create one with this size
        """
        return FilterHandle(self._filters, rule, queue or Queue(bufsize))

    def stop(self):
        self._stop_receiving.set()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False

    # Backwards compatible interface (from old DBusConnection) --------

    @property
    def unique_name(self):
        return self.conn.unique_name

    async def send_message(self, message: Message):
        if (
                message.header.message_type == MessageType.method_return
                and not (message.header.flags & MessageFlag.no_reply_expected)
        ):
            return unwrap_msg(await self.send_and_get_reply(message))
        else:
            await self.send(message)


    # Code to run in receiver task ------------------------------------

    def _dispatch(self, msg: Message):
        """Handle one received message"""
        if self._replies.dispatch(msg):
            return

        for filter in self._filters.matches(msg):
            try:
                filter.queue.put_nowait(msg)
            except QueueFull:
                pass

    async def _receiver(self):
        """Receiver loop - runs in a separate task"""
        try:
            while True:
                for coro in as_completed([self.conn.receive(), self._stop_receiving.wait()]):
                    msg = await coro
                    if msg is None:
                        return  # Stopped
                    self._dispatch(msg)
                    self.router.incoming(msg)
        finally:
            self.is_running = False
            # Send errors to any tasks still waiting for a message.
            self._replies.drop_all()


class Proxy(ProxyBase):
    def __init__(self, msggen, router: DBusRouter):
        super().__init__(msggen)
        self._router = router

    def __repr__(self):
        return 'Proxy({}, {})'.format(self._msggen, self._router)

    def _method_call(self, make_msg):
        async def inner(*args, **kwargs):
            msg = make_msg(*args, **kwargs)
            assert msg.header.message_type is MessageType.method_call
            return unwrap_msg(await self._router.send_and_get_reply(msg))

        return inner


class _RouterContext:
    conn = None
    router = None

    def __init__(self, bus='SESSION'):
        self.bus = bus

    async def __aenter__(self):
        self.conn = await open_dbus_connection(self.bus)
        self.router = DBusRouter(self.conn)
        return self.router

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.router.stop()
        self.conn.close()


def open_dbus_router(bus='SESSION'):
    """Open a D-Bus 'router' to send and receive messages.

    Use as an async context manager::

        async with open_dbus_router() as req:
            ...

    :param str bus: 'SESSION' or 'SYSTEM' or a supported address.
    :return: :class:`DBusRouter`

    This is a shortcut for::

        conn = await open_dbus_connection()
        async with conn:
            async with conn.router() as req:
                ...
    """
    return _RouterContext(bus)


