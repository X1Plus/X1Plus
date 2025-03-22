"""
RTP Transport base class.
---------------------
"""
import asyncio
import logging
import traceback
from time import time
from typing import Optional, Set

from dpkt.rtp import RTP

from aiortsp.rtcp.parser import RTCP
from aiortsp.rtcp.stats import RTCPStats

_logger = logging.getLogger('rtp.session')

DEFAULT_BUFFER_SIZE = 4 * 1024 * 1024


class RTPTransportClient:
    """
    RTP Transport Client class.
    - To be subscribed to the transport
    - Implementing wanted callbacks
    """

    def handle_rtp(self, rtp: RTP):
        """Handle an incoming RTP packet"""

    def handle_rtcp(self, rtcp: RTCP):
        """Handle an incoming RTP packet"""

    def handle_closed(self, error: Optional[Exception]):
        """Handle closing"""


class RTPTransport:
    """
    Base (abstract) RTP Transport class
    """

    def __init__(self, connection, *, logger=None, timeout=10):
        self.connection = connection
        self.clients: Set[RTPTransportClient] = set()
        self.stats = RTCPStats()
        self.logger = logger or _logger
        self.result = asyncio.Future()
        # Just to be sure we retrieve the exception at least once if client doesn't
        self.result.add_done_callback(lambda fut: fut.exception())
        self.timeout = timeout
        self.paused = False
        self._rtcp_loop = self._timeout_loop = None

    def subscribe(self, client: RTPTransportClient):
        """
        Add a subscription to RTP frames
        """
        self.clients.add(client)

    def unsubscribe(self, client: RTPTransportClient):
        """
        Remove a subscription to RTP frames
        """
        self.clients.remove(client)

    def handle_rtcp_data(self, data: bytes):
        """
        An RTCP report was received.
        """
        rtcp = RTCP.unpack(data)
        self.logger.debug('received RTCP report: %s', rtcp)

        self.stats.handle_rtcp(rtcp)

        if self._rtcp_loop is None:
            # This is the first packet ever!
            self._rtcp_loop = asyncio.ensure_future(self.rtcp_loop())

        for client in self.clients:
            try:
                client.handle_rtcp(rtcp)
            except Exception as ex:  # pylint: disable=broad-except
                self.logger.error('error on RTCP client callback: %r', ex)

    def handle_rtp_data(self, data: bytes):
        """
        An RTP packet was received.
        """
        rtp = RTP(data)

        self.stats.update(rtp)

        for client in self.clients:
            try:
                client.handle_rtp(rtp)
            except Exception as ex:  # pylint: disable=broad-except
                self.logger.error('error on RTP client callback: %r', ex)

    @staticmethod
    def parse_transport_fields(header) -> dict:
        """
        Parse Transport request/response
        """
        res = {}
        fields_ = header.split(';')
        for field in fields_:
            if '=' in field:
                k, v = field.split('=', 1)
            else:
                k, v = field, None

            res[k.strip()] = v.strip() if v is not None else None

        return res

    async def rtcp_loop(self):
        """
        Handling report sending and timeout
        """
        initial = True
        while self.running:
            delay = self.stats.rtcp_interval(initial)
            initial = False
            self.logger.debug('sleeping for RTCP delay: %s', delay)
            await asyncio.sleep(delay)

            try:
                rtcp = self.stats.build_rtcp()

                if not rtcp:
                    self.logger.warning('no RTCP report available yet (are we receiving anything?)')
                    continue
            except Exception as ex:  # pylint: disable=broad-except
                self.logger.error('unable to build RTCP report: %r', ex)
                traceback.print_exc()
                continue

            try:
                self.logger.debug('sending RTCP report: %s', rtcp)
                await self.send_rtcp_report(rtcp)
            except asyncio.CancelledError:
                break
            except Exception as ex:  # pylint: disable=broad-except
                self.logger.error('unable to send RTCP report: %r', ex)

    async def timeout_loop(self):
        """
        Handling report sending and timeout
        """
        sleep_duration = self.timeout
        while self.running:
            await asyncio.sleep(sleep_duration)

            # Check if (and when) we received anything
            diff = time() - self.stats.last_received
            if not self.paused and diff > self.timeout:
                self.logger.error('no RTP received for %s seconds: closing', self.timeout)
                return self.close(TimeoutError('no data'))

            sleep_duration = max(self.timeout - diff, 1)

    def close(self, error=None):
        """
        Called when transport needs closing
        """
        if not self.result.done():
            if error:
                self.result.set_exception(error)
            else:
                self.result.set_result(False)

        if self._rtcp_loop:
            self._rtcp_loop.cancel()
            self._rtcp_loop = None

        if self._timeout_loop and not self._timeout_loop.done():
            self._timeout_loop.cancel()
            self._timeout_loop = None

        for client in self.clients:
            try:
                client.handle_closed(error)
            except Exception as ex:  # pylint: disable=broad-except
                self.logger.error('error on RTP client callback: %r', ex)

    async def __aenter__(self):
        await self.prepare()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
        self.close(exc_val)

    def __enter__(self):
        raise RuntimeError('did you mean `async with`?')

    def __exit__(self, exc_type, exc_val, exc_tb):
        raise RuntimeError('should never be called')

    def on_transport_request(self, headers: dict):
        """
        Given a setup request headers dict,
        add whatever headers are necessary, usually the 'Transport' header.
        """
        raise NotImplementedError

    def on_transport_response(self, headers: dict):
        """
        Given a setup response headers dict,
        Allow the transport to read whatever is necessary.
        """
        raise NotImplementedError

    async def prepare(self):
        """
        Called before setting up the media session.
        Any
        :return:
        """

    async def cleanup(self):
        """
        Called before setting up the media session.
        Any
        :return:
        """

    async def warmup(self):
        """
        Called before playing.
        Whatever should be done before playing should be done here.
        """
        if self.timeout:
            self._timeout_loop = asyncio.ensure_future(self.timeout_loop())

    @property
    def running(self) -> bool:
        """
        Tells if the transport is still open and running
        """
        raise NotImplementedError

    async def send_rtcp_report(self, rtcp: RTCP):
        """
        Send an RTCP report back to the server
        """
        raise NotImplementedError
