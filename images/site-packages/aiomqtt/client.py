# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import enum
import functools
import logging
import math
import socket
import ssl
import sys
from types import TracebackType
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Coroutine,
    Generator,
    Iterable,
    Iterator,
    Literal,
    TypeVar,
    cast,
)

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode
from paho.mqtt.subscribeoptions import SubscribeOptions

from .exceptions import MqttCodeError, MqttConnectError, MqttError, MqttReentrantError
from .message import Message
from .types import (
    P,
    PayloadType,
    SocketOption,
    SubscribeTopic,
    T,
    WebSocketHeaders,
    _PahoSocket,
)

if sys.version_info >= (3, 11):
    from typing import Concatenate, Self
elif sys.version_info >= (3, 10):
    from typing import Concatenate

    from typing_extensions import Self
else:
    from typing_extensions import Concatenate, Self


MQTT_LOGGER = logging.getLogger("mqtt")
MQTT_LOGGER.setLevel(logging.WARNING)

ClientT = TypeVar("ClientT", bound="Client")


class ProtocolVersion(enum.IntEnum):
    """Map paho-mqtt protocol versions to an Enum for use in type hints."""

    V31 = mqtt.MQTTv31
    V311 = mqtt.MQTTv311
    V5 = mqtt.MQTTv5


@dataclasses.dataclass(frozen=True)
class TLSParameters:
    ca_certs: str | None = None
    certfile: str | None = None
    keyfile: str | None = None
    cert_reqs: ssl.VerifyMode | None = None
    tls_version: Any | None = None
    ciphers: str | None = None
    keyfile_password: str | None = None


class ProxySettings:
    def __init__(  # noqa: PLR0913
        self,
        *,
        proxy_type: int,
        proxy_addr: str,
        proxy_rdns: bool | None = True,
        proxy_username: str | None = None,
        proxy_password: str | None = None,
    ) -> None:
        self.proxy_args = {
            "proxy_type": proxy_type,
            "proxy_addr": proxy_addr,
            "proxy_rdns": proxy_rdns,
            "proxy_username": proxy_username,
            "proxy_password": proxy_password,
        }


# TODO(frederik): Simplify the logic that surrounds `self._outgoing_calls_sem` with
# `nullcontext` when we support Python 3.10 (`nullcontext` becomes async-aware in
# 3.10). See: https://docs.python.org/3/library/contextlib.html#contextlib.nullcontext
def _outgoing_call(
    method: Callable[Concatenate[ClientT, P], Coroutine[Any, Any, T]],
) -> Callable[Concatenate[ClientT, P], Coroutine[Any, Any, T]]:
    @functools.wraps(method)
    async def decorated(self: ClientT, /, *args: P.args, **kwargs: P.kwargs) -> T:
        if not self._outgoing_calls_sem:
            return await method(self, *args, **kwargs)

        async with self._outgoing_calls_sem:
            return await method(self, *args, **kwargs)

    return decorated


@dataclasses.dataclass(frozen=True)
class Will:
    topic: str
    payload: PayloadType | None = None
    qos: int = 0
    retain: bool = False
    properties: Properties | None = None


class Client:
    """The async context manager that manages the connection to the broker.

    Args:
        hostname: The hostname or IP address of the remote broker.
        port: The network port of the remote broker.
        username: The username to authenticate with.
        password: The password to authenticate with.
        logger: Custom logger instance.
        identifier: The client identifier. Generated automatically if ``None``.
        queue_type: The class to use for the queue. The default is
            ``asyncio.Queue``, which stores messages in FIFO order. For LIFO order,
            you can use ``asyncio.LifoQueue``; For priority order you can subclass
            ``asyncio.PriorityQueue``.
        protocol: The version of the MQTT protocol.
        will: The will message to publish if the client disconnects unexpectedly.
        clean_session: If ``True``, the broker will remove all information about this
            client when it disconnects. If ``False``, the client is a persistent client
            and subscription information and queued messages will be retained when the
            client disconnects.
        transport: The transport protocol to use. Either ``"tcp"`` or ``"websockets"``.
        timeout: The default timeout for all communication with the broker in seconds.
        keepalive: The keepalive timeout for the client in seconds.
        bind_address: The IP address of a local network interface to bind this client
            to.
        bind_port: The network port to bind this client to.
        clean_start: (MQTT v5.0 only) Set the clean start flag always, never, or only
            on the first successful connection to the broker.
        max_queued_incoming_messages: Restricts the incoming message queue size. If the
            queue is full, further incoming messages are discarded. ``0`` or less means
            unlimited (the default).
        max_queued_outgoing_messages: Resticts the outgoing message queue size. If the
            queue is full, further outgoing messages are discarded. ``0`` means
            unlimited (the default).
        max_inflight_messages: The maximum number of messages with QoS > ``0`` that can
            be part way through their network flow at once.
        max_concurrent_outgoing_calls: The maximum number of concurrent outgoing calls.
        properties: (MQTT v5.0 only) The properties associated with the client.
        tls_context: The SSL/TLS context.
        tls_params: The SSL/TLS configuration to use.
        tls_insecure: Enable/disable server hostname verification when using SSL/TLS.
        proxy: Configure a proxy for the connection.
        socket_options: Options to pass to the underlying socket.
        websocket_path: The path to use for websockets.
        websocket_headers: The headers to use for websockets.

    Attributes:
        messages (typing.AsyncGenerator[aiomqtt.client.Message, None]):
            Async generator that yields messages from the underlying message queue.
        identifier (str):
            The client identifier.
    """

    def __init__(  # noqa: C901, PLR0912, PLR0913, PLR0915
        self,
        hostname: str,
        port: int = 1883,
        *,
        username: str | None = None,
        password: str | None = None,
        logger: logging.Logger | None = None,
        identifier: str | None = None,
        queue_type: type[asyncio.Queue[Message]] | None = None,
        protocol: ProtocolVersion | None = None,
        will: Will | None = None,
        clean_session: bool | None = None,
        transport: Literal["tcp", "websockets"] = "tcp",
        timeout: float | None = None,
        keepalive: int = 60,
        bind_address: str = "",
        bind_port: int = 0,
        clean_start: mqtt.CleanStartOption = mqtt.MQTT_CLEAN_START_FIRST_ONLY,
        max_queued_incoming_messages: int | None = None,
        max_queued_outgoing_messages: int | None = None,
        max_inflight_messages: int | None = None,
        max_concurrent_outgoing_calls: int | None = None,
        properties: Properties | None = None,
        tls_context: ssl.SSLContext | None = None,
        tls_params: TLSParameters | None = None,
        tls_insecure: bool | None = None,
        proxy: ProxySettings | None = None,
        socket_options: Iterable[SocketOption] | None = None,
        websocket_path: str | None = None,
        websocket_headers: WebSocketHeaders | None = None,
    ) -> None:
        self._hostname = hostname
        self._port = port
        self._keepalive = keepalive
        self._bind_address = bind_address
        self._bind_port = bind_port
        self._clean_start = clean_start
        self._properties = properties
        self._loop = asyncio.get_event_loop()

        # Connection state
        self._connected: asyncio.Future[None] = asyncio.Future()
        self._disconnected: asyncio.Future[None] = asyncio.Future()
        self._lock: asyncio.Lock = asyncio.Lock()

        # Pending subscribe, unsubscribe, and publish calls
        self._pending_subscribes: dict[
            int, asyncio.Future[tuple[int, ...] | list[ReasonCode]]
        ] = {}
        self._pending_unsubscribes: dict[int, asyncio.Event] = {}
        self._pending_publishes: dict[int, asyncio.Event] = {}
        self.pending_calls_threshold: int = 10
        self._misc_task: asyncio.Task[None] | None = None

        # Queue that holds incoming messages
        if queue_type is None:
            queue_type = cast("type[asyncio.Queue[Message]]", asyncio.Queue)
        if max_queued_incoming_messages is None:
            max_queued_incoming_messages = 0
        self._queue = queue_type(maxsize=max_queued_incoming_messages)

        # Semaphore to limit the number of concurrent outgoing calls
        self._outgoing_calls_sem: asyncio.Semaphore | None
        if max_concurrent_outgoing_calls is not None:
            self._outgoing_calls_sem = asyncio.Semaphore(max_concurrent_outgoing_calls)
        else:
            self._outgoing_calls_sem = None

        if protocol is None:
            protocol = ProtocolVersion.V311

        # Create the underlying paho-mqtt client instance
        self._client: mqtt.Client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=identifier,
            protocol=protocol.value,
            clean_session=clean_session,
            transport=transport,
            reconnect_on_failure=False,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_subscribe = self._on_subscribe
        self._client.on_unsubscribe = self._on_unsubscribe
        self._client.on_message = self._on_message
        self._client.on_publish = self._on_publish

        # Callbacks for custom event loop
        self._client.on_socket_open = self._on_socket_open
        self._client.on_socket_close = self._on_socket_close
        self._client.on_socket_register_write = self._on_socket_register_write
        self._client.on_socket_unregister_write = self._on_socket_unregister_write

        if max_inflight_messages is not None:
            self._client.max_inflight_messages_set(max_inflight_messages)
        if max_queued_outgoing_messages is not None:
            self._client.max_queued_messages_set(max_queued_outgoing_messages)

        if logger is None:
            logger = MQTT_LOGGER
        self._logger = logger
        self._client.enable_logger(logger)

        if username is not None:
            self._client.username_pw_set(username=username, password=password)

        if tls_context is not None:
            self._client.tls_set_context(tls_context)

        if tls_params is not None:
            self._client.tls_set(
                ca_certs=tls_params.ca_certs,
                certfile=tls_params.certfile,
                keyfile=tls_params.keyfile,
                cert_reqs=tls_params.cert_reqs,
                tls_version=tls_params.tls_version,
                ciphers=tls_params.ciphers,
                keyfile_password=tls_params.keyfile_password,
            )

        if tls_insecure is not None:
            self._client.tls_insecure_set(tls_insecure)

        if proxy is not None:
            self._client.proxy_set(**proxy.proxy_args)

        if websocket_path is not None:
            self._client.ws_set_options(path=websocket_path, headers=websocket_headers)

        if will is not None:
            self._client.will_set(
                will.topic, will.payload, will.qos, will.retain, will.properties
            )

        if socket_options is None:
            socket_options = ()
        self._socket_options = tuple(socket_options)

        if timeout is None:
            timeout = 10
        self.timeout = timeout

    @property
    def messages(self) -> AsyncGenerator[Message, None]:
        return self._messages()

    @property
    def identifier(self) -> str:
        """Return the client identifier.

        Note that paho-mqtt stores the client ID as `bytes` internally. We assume that
        the client ID is a UTF8-encoded string and decode it first.
        """
        return self._client._client_id.decode()  # noqa: SLF001

    @property
    def _pending_calls(self) -> Generator[int, None, None]:
        """Yield all message IDs with pending calls."""
        yield from self._pending_subscribes.keys()
        yield from self._pending_unsubscribes.keys()
        yield from self._pending_publishes.keys()

    @_outgoing_call
    async def subscribe(  # noqa: PLR0913
        self,
        /,
        topic: SubscribeTopic,
        qos: int = 0,
        options: SubscribeOptions | None = None,
        properties: Properties | None = None,
        *args: Any,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> tuple[int, ...] | list[ReasonCode]:
        """Subscribe to a topic or wildcard.

        Args:
            topic: The topic or wildcard to subscribe to.
            qos: The requested QoS level for the subscription.
            options: (MQTT v5.0 only) Optional paho-mqtt subscription options.
            properties: (MQTT v5.0 only) Optional paho-mqtt properties.
            *args: Additional positional arguments to pass to paho-mqtt's subscribe
                method.
            timeout: The maximum time in seconds to wait for the subscription to
                complete. Use ``math.inf`` to wait indefinitely.
            **kwargs: Additional keyword arguments to pass to paho-mqtt's subscribe
                method.

        """
        result, mid = self._client.subscribe(
            topic, qos, options, properties, *args, **kwargs
        )
        # Early out on error
        if result != mqtt.MQTT_ERR_SUCCESS or mid is None:
            raise MqttCodeError(result, "Could not subscribe to topic")
        # Create future for when the on_subscribe callback is called
        callback_result: asyncio.Future[tuple[int, ...] | list[ReasonCode]] = (
            asyncio.Future()
        )
        with self._pending_call(mid, callback_result, self._pending_subscribes):
            # Wait for callback_result
            return await self._wait_for(callback_result, timeout=timeout)

    @_outgoing_call
    async def unsubscribe(
        self,
        /,
        topic: str | list[str],
        properties: Properties | None = None,
        *args: Any,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Unsubscribe from a topic or wildcard.

        Args:
            topic: The topic or wildcard to unsubscribe from.
            properties: (MQTT v5.0 only) Optional paho-mqtt properties.
            *args: Additional positional arguments to pass to paho-mqtt's unsubscribe
                method.
            timeout: The maximum time in seconds to wait for the unsubscription to
                complete. Use ``math.inf`` to wait indefinitely.
            **kwargs: Additional keyword arguments to pass to paho-mqtt's unsubscribe
                method.
        """
        result, mid = self._client.unsubscribe(topic, properties, *args, **kwargs)
        # Early out on error
        if result != mqtt.MQTT_ERR_SUCCESS or mid is None:
            raise MqttCodeError(result, "Could not unsubscribe from topic")
        # Create event for when the on_unsubscribe callback is called
        confirmation = asyncio.Event()
        with self._pending_call(mid, confirmation, self._pending_unsubscribes):
            # Wait for confirmation
            await self._wait_for(confirmation.wait(), timeout=timeout)

    @_outgoing_call
    async def publish(  # noqa: PLR0913
        self,
        /,
        topic: str,
        payload: PayloadType = None,
        qos: int = 0,
        retain: bool = False,
        properties: Properties | None = None,
        *args: Any,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Publish a message to the broker.

        Args:
            topic: The topic to publish to.
            payload: The message payload.
            qos: The QoS level to use for publication.
            retain: If set to ``True``, the message will be retained by the broker.
            properties: (MQTT v5.0 only) Optional paho-mqtt properties.
            *args: Additional positional arguments to pass to paho-mqtt's publish
                method.
            timeout: The maximum time in seconds to wait for publication to complete.
                Use ``math.inf`` to wait indefinitely.
            **kwargs: Additional keyword arguments to pass to paho-mqtt's publish
                method.
        """
        info = self._client.publish(
            topic, payload, qos, retain, properties, *args, **kwargs
        )  # [2]
        # Early out on error
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise MqttCodeError(info.rc, "Could not publish message")
        # Early out on immediate success
        if info.is_published():
            return
        # Create event for when the on_publish callback is called
        confirmation = asyncio.Event()
        with self._pending_call(info.mid, confirmation, self._pending_publishes):
            # Wait for confirmation
            await self._wait_for(confirmation.wait(), timeout=timeout)

    async def _messages(self) -> AsyncGenerator[Message, None]:
        """Async generator that yields messages from the underlying message queue."""
        while True:
            # Wait until we either:
            #  1. Receive a message
            #  2. Disconnect from the broker
            task = self._loop.create_task(self._queue.get())
            try:
                done, _ = await asyncio.wait(
                    (task, self._disconnected), return_when=asyncio.FIRST_COMPLETED
                )
            except asyncio.CancelledError:
                # If the asyncio.wait is cancelled, we must make sure
                # to also cancel the underlying tasks.
                task.cancel()
                raise
            if task in done:
                # We received a message. Return the result.
                yield task.result()
            else:
                # We were disconnected from the broker
                task.cancel()
                # Stop the generator with an exception
                msg = "Disconnected during message iteration"
                raise MqttError(msg)

    async def _wait_for(
        self, fut: Awaitable[T], timeout: float | None, **kwargs: Any
    ) -> T:
        if timeout is None:
            timeout = self.timeout
        # Note that asyncio uses `None` to mean "No timeout". We use `math.inf`.
        timeout_for_asyncio = None if timeout == math.inf else timeout
        try:
            return await asyncio.wait_for(fut, timeout=timeout_for_asyncio, **kwargs)
        except asyncio.TimeoutError:
            msg = "Operation timed out"
            raise MqttError(msg) from None

    @contextlib.contextmanager
    def _pending_call(
        self, mid: int, value: T, pending_dict: dict[int, T]
    ) -> Iterator[None]:
        if mid in self._pending_calls:
            msg = f'There already exists a pending call for message ID "{mid}"'
            raise RuntimeError(msg)
        pending_dict[mid] = value  # [1]
        try:
            # Log a warning if there is a concerning number of pending calls
            pending = len(list(self._pending_calls))
            if pending > self.pending_calls_threshold:
                self._logger.warning("There are %d pending publish calls.", pending)
            # Back to the caller (run whatever is inside the with statement)
            yield
        finally:
            # The normal procedure is:
            #  * We add the item at [1]
            #  * A callback will remove the item
            #
            # However, if the callback doesn't get called (e.g., due to a
            # network error) we still need to remove the item from the dict.
            try:
                del pending_dict[mid]
            except KeyError:
                pass

    def _on_connect(  # noqa: PLR0913
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.ConnectFlags,
        reason_code: ReasonCode,
        properties: Properties | None = None,
    ) -> None:
        """Called when we receive a CONNACK message from the broker."""
        # Return early if already connected. Sometimes, paho-mqtt calls _on_connect
        # multiple times. Maybe because we receive multiple CONNACK messages
        # from the server. In any case, we return early so that we don't set
        # self._connected twice (as it raises an asyncio.InvalidStateError).
        if self._connected.done():
            return
        if reason_code == mqtt.CONNACK_ACCEPTED:
            self._connected.set_result(None)
        else:
            # We received a negative CONNACK response
            self._connected.set_exception(MqttConnectError(reason_code))

    def _on_disconnect(  # noqa: PLR0913
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.DisconnectFlags,
        reason_code: ReasonCode,
        properties: Properties | None = None,
    ) -> None:
        # Return early if the disconnect is already acknowledged.
        # Sometimes (e.g., due to timeouts), paho-mqtt calls _on_disconnect
        # twice. We return early to avoid setting self._disconnected twice
        # (as it raises an asyncio.InvalidStateError).
        if self._disconnected.done():
            return
        # Return early if we are not connected yet. This avoids calling
        # `_disconnected.set_exception` with an exception that will never
        # be retrieved (since `__aexit__` won't get called if `__aenter__`
        # fails). In turn, this avoids asyncio debug messages like the
        # following:
        #
        #   `[asyncio] Future exception was never retrieved`
        #
        # See also: https://docs.python.org/3/library/asyncio-dev.html#detect-never-retrieved-exceptions
        if not self._connected.done() or self._connected.exception() is not None:
            return
        if reason_code == mqtt.MQTT_ERR_SUCCESS:
            self._disconnected.set_result(None)
        else:
            self._disconnected.set_exception(
                MqttCodeError(reason_code, "Unexpected disconnection")
            )

    def _on_subscribe(  # noqa: PLR0913
        self,
        client: mqtt.Client,
        userdata: Any,
        mid: int,
        reason_codes: list[ReasonCode],
        properties: Properties | None = None,
    ) -> None:
        """Called when we receive a SUBACK message from the broker."""
        try:
            fut = self._pending_subscribes.pop(mid)
            if not fut.done():
                fut.set_result(reason_codes)
        except KeyError:
            self._logger.exception(
                'Unexpected message ID "%d" in on_subscribe callback', mid
            )

    def _on_unsubscribe(  # noqa: PLR0913
        self,
        client: mqtt.Client,
        userdata: Any,
        mid: int,
        reason_codes: list[ReasonCode],
        properties: Properties | None = None,
    ) -> None:
        """Called when we receive an UNSUBACK message from the broker."""
        try:
            self._pending_unsubscribes.pop(mid).set()
        except KeyError:
            self._logger.exception(
                'Unexpected message ID "%d" in on_unsubscribe callback', mid
            )

    def _on_message(
        self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage
    ) -> None:
        # Convert the paho.mqtt message into our own Message type
        m = Message._from_paho_message(message)  # noqa: SLF001
        # Put the message in the message queue
        try:
            self._queue.put_nowait(m)
        except asyncio.QueueFull:
            self._logger.warning("Message queue is full. Discarding message.")

    def _on_publish(  # noqa: PLR0913
        self,
        client: mqtt.Client,
        userdata: Any,
        mid: int,
        reason_code: ReasonCode,
        properties: Properties,
    ) -> None:
        try:
            self._pending_publishes.pop(mid).set()
        except KeyError:
            # Do nothing since [2] may call on_publish before it even returns.
            # That is, the message may already be published before we even get a
            # chance to set up the 'pending_call' logic.
            pass

    def _on_socket_open(
        self, client: mqtt.Client, userdata: Any, sock: _PahoSocket
    ) -> None:
        def callback() -> None:
            # client.loop_read() may raise an exception, such as BadPipe. It's
            # usually a sign that the underlaying connection broke, therefore we
            # disconnect straight away
            try:
                client.loop_read()
            except Exception as exc:
                if not self._disconnected.done():
                    self._disconnected.set_exception(exc)

        # paho-mqtt calls this function from the executor thread on which we've called
        # `self._client.connect()` (see [3]), so we can't do most operations on
        # self._loop directly.
        def create_misc_task() -> None:
            self._misc_task = self._loop.create_task(self._misc_loop())

        self._loop.call_soon_threadsafe(self._loop.add_reader, sock.fileno(), callback)
        self._loop.call_soon_threadsafe(create_misc_task)

    def _on_socket_close(
        self, client: mqtt.Client, userdata: Any, sock: _PahoSocket
    ) -> None:
        fileno = sock.fileno()
        if fileno > -1:
            self._loop.remove_reader(fileno)
        if self._misc_task is not None and not self._misc_task.done():
            self._loop.call_soon_threadsafe(self._misc_task.cancel)

    def _on_socket_register_write(
        self, client: mqtt.Client, userdata: Any, sock: _PahoSocket
    ) -> None:
        def callback() -> None:
            # client.loop_write() may raise an exception, such as BadPipe. It's
            # usually a sign that the underlaying connection broke, therefore we
            # disconnect straight away
            try:
                client.loop_write()
            except Exception as exc:
                if not self._disconnected.done():
                    self._disconnected.set_exception(exc)

        # paho-mqtt may call this function from the executor thread on which we've called
        # `self._client.connect()` (see [3]), so we can't do most operations on
        # self._loop directly.
        self._loop.call_soon_threadsafe(self._loop.add_writer, sock, callback)

    def _on_socket_unregister_write(
        self, client: mqtt.Client, userdata: Any, sock: _PahoSocket
    ) -> None:
        self._loop.remove_writer(sock)

    async def _misc_loop(self) -> None:
        while self._client.loop_misc() == mqtt.MQTT_ERR_SUCCESS:
            await asyncio.sleep(1)

    async def __aenter__(self) -> Self:
        """Connect to the broker."""
        if self._lock.locked():
            msg = "The client context manager is reusable, but not reentrant"
            raise MqttReentrantError(msg)
        await self._lock.acquire()
        try:
            loop = asyncio.get_running_loop()
            # [3] Run connect() within an executor thread, since it blocks on socket
            # connection for up to `keepalive` seconds: https://git.io/Jt5Yc
            await loop.run_in_executor(
                None,
                self._client.connect,
                self._hostname,
                self._port,
                self._keepalive,
                self._bind_address,
                self._bind_port,
                self._clean_start,
                self._properties,
            )
            _set_client_socket_defaults(self._client.socket(), self._socket_options)
        # Convert all possible paho-mqtt Client.connect exceptions to our MqttError
        # See: https://github.com/eclipse/paho.mqtt.python/blob/v1.5.0/src/paho/mqtt/client.py#L1770
        except (OSError, mqtt.WebsocketConnectionError) as exc:
            self._lock.release()
            raise MqttError(str(exc)) from None
        try:
            await self._wait_for(self._connected, timeout=None)
        except MqttError:
            # Reset state if connection attempt times out or CONNACK returns negative
            self._lock.release()
            self._connected = asyncio.Future()
            raise
        # Reset `_disconnected` if it's already in completed state after connecting
        if self._disconnected.done():
            self._disconnected = asyncio.Future()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Disconnect from the broker."""
        if self._disconnected.done():
            # Return early if the client is already disconnected
            if self._lock.locked():
                self._lock.release()
            if (exc := self._disconnected.exception()) is not None:
                # If the disconnect wasn't intentional, raise the error that caused it
                raise exc
            return
        # Try to gracefully disconnect from the broker
        rc = self._client.disconnect()
        if rc == mqtt.MQTT_ERR_SUCCESS:
            # Wait for acknowledgement
            await self._wait_for(self._disconnected, timeout=None)
            # Reset `_connected` if it's still in completed state after disconnecting
            if self._connected.done():
                self._connected = asyncio.Future()
        else:
            self._logger.warning(
                "Could not gracefully disconnect: %d. Forcing disconnection.", rc
            )
        # Force disconnection if we cannot gracefully disconnect
        if not self._disconnected.done():
            self._disconnected.set_result(None)
        # Release the reusability lock
        if self._lock.locked():
            self._lock.release()


def _set_client_socket_defaults(
    client_socket: _PahoSocket | None, socket_options: Iterable[SocketOption]
) -> None:
    # Note that socket may be None if, e.g., the username and
    # password combination didn't work. In this case, we return early.
    if client_socket is None:
        return
    # Furthermore, paho sometimes gives us a socket wrapper instead of
    # the raw socket. E.g., for WebSocket-based connections.
    if not isinstance(client_socket, socket.socket):
        return
    # At this point, we know that we got an actual socket. We change
    # some of the default options.
    for socket_option in socket_options:
        client_socket.setsockopt(*socket_option)
