"""
Simplified RTP reader
"""
import asyncio
import logging
import ssl
from time import time
from typing import AsyncIterable, Optional
from urllib.parse import urlparse

from dpkt.rtp import RTP

from aiortsp.rtsp.connection import RTSPConnection
from aiortsp.rtsp.session import RTSPMediaSession, sanitize_rtsp_url
from aiortsp.transport import transport_for_scheme, RTPTransport, RTPTransportClient

class RTSPReader(RTPTransportClient):
    """
    Quick wrapper around base functions to start getting frames from an RTSP feed.

    Usage:

    .. code-block::

        async with RTSPReader('rtsp://foo/bar') as reader:
            async for pkt in reader.iter_packets():
                print(pkt)
    """

    def __init__(
            self, media_url: str, timeout=10, log_level=20,
            ssl = None,
            run_loop=False, **_
    ):
        self.media_url = media_url
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        self.timeout = timeout
        self.run_loop = run_loop
        self.ssl = ssl
        self.queue: 'asyncio.Queue[RTP]' = asyncio.Queue()
        self._runner = None
        self.connection: Optional[RTSPConnection] = None
        self.transport: Optional[RTPTransport] = None
        self.session: Optional[RTSPMediaSession] = None
        self.payload_type = None

    def handle_rtp(self, rtp: RTP):
        """Queue packets for the iterator"""
        if self.payload_type and self.payload_type != rtp.pt:
            return

        self.queue.put_nowait(rtp)

    def on_ready(self, connection: RTSPConnection, transport: RTPTransport, session: RTSPMediaSession):
        """Handler on ready to play stream, for sub classes to do their initialisation"""
        if session.sdp:
            self.payload_type = session.sdp.media_payload_type()
        transport.subscribe(self)
        self.connection = connection
        self.transport = transport
        self.session = session

    def handle_closed(self, error):
        """Handler for connection closed, for sub classes to cleanup their state"""
        self.logger.info('connection closed, error: %s', error)
        self.connection = None
        self.transport = None
        self.session = None

    async def run_stream_loop(self):
        """Run stream as a loop, forever restarting unless if cancelled"""
        while True:
            try:
                await self.run_stream()
            except asyncio.CancelledError:
                self.logger.error('Stopping run loop for %s', sanitize_rtsp_url(self.media_url))
                break
            except Exception as ex:  # pylint: disable=broad-except
                self.logger.error('Error on stream: %r. Reconnecting...', ex)
                await asyncio.sleep(1)

    async def run_stream(self):
        """
        Setup and play stream, and ensure it stays on.
        """
        self.logger.info('try loading stream %s', sanitize_rtsp_url(self.media_url))

        p_url = urlparse(self.media_url)

        if p_url.scheme == 'rtsps' and not self.ssl:
            self.ssl = ssl.create_default_context()
        if p_url.scheme == 'rtsps':
            default_port = 322
        else:
            default_port = 554

        async with RTSPConnection(
                p_url.hostname, p_url.port or default_port,
                p_url.username, p_url.password,
                logger=self.logger, timeout=self.timeout,
                ssl=self.ssl
        ) as conn:
            self.logger.info('connected!')

            transport_class = transport_for_scheme(p_url.scheme)
            async with transport_class(conn, logger=self.logger, timeout=self.timeout) as transport:
                async with RTSPMediaSession(conn, self.media_url, transport=transport, logger=self.logger) as sess:

                    self.on_ready(conn, transport, sess)

                    self.logger.info('playing stream...')
                    await sess.play()

                    try:
                        last_keep_alive = time()
                        while conn.running and transport.running:
                            # Check keep alive
                            now = time()
                            if (now - last_keep_alive) > sess.session_keepalive:
                                await sess.keep_alive()
                                last_keep_alive = now

                            await asyncio.sleep(1)

                    except asyncio.CancelledError:
                        self.logger.info('stopping stream...')
                        raise

    async def __aenter__(self):
        self._runner = asyncio.ensure_future(
            self.run_stream_loop() if self.run_loop else self.run_stream())
        self._runner.add_done_callback(lambda *_: self.queue.put_nowait(None))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._runner:
            self._runner.cancel()

    async def iter_packets(self) -> AsyncIterable[RTP]:
        """
        Yield RTP packets as they come.
        User can then do whatever they want, without too much boiler plate.
        """
        while True:
            pkt = await self.queue.get()

            if not pkt:
                break

            yield pkt
