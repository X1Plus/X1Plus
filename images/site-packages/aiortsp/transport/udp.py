"""
UDP Socket transport
"""
import asyncio
import logging
import socket
from random import randint
from typing import Tuple

from aiortsp.rtcp.parser import RTCP
from aiortsp.rtsp.errors import RTSPError
from .base import RTPTransport

_logger = logging.getLogger('rtp.session')

DEFAULT_BUFFER_SIZE = 4 * 1024 * 1024


class DatagramSink(asyncio.DatagramProtocol):
    """
    Default sink implementation.
    """
    def __init__(self, receiver: 'UDPTransport'):
        self.receiver = receiver
        self.transport = None

    @property
    def local_port(self) -> int:
        """
        local port or identifier
        """
        if self.transport:
            return self.transport.get_extra_info('socket').getsockname()[1]
        return 0

    @property
    def running(self) -> bool:
        """
        A sink is running until marked as done
        """
        return self.transport is not None

    def sendto(self, data, remote):
        """
        Convenient wrapper
        """
        if self.transport:
            self.transport.sendto(data, remote)

    def close(self):
        """
        Convenient wrapper
        """
        if self.transport:
            self.transport.close()

    def connection_made(self, transport):
        self.transport = transport

        sock = self.transport.get_extra_info('socket')

        try:
            self.receiver.logger.debug(
                'setting socket send buffer size to: %s', self.receiver.send_buffer)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.receiver.send_buffer)
        except OSError as ex:
            # What can we do here?
            #  - On Linux it would just set the max.
            #  - On mac, if too big it will just fail
            self.receiver.logger.warning('could not set socket SO_SNDBUF: %s', ex)

        try:
            self.receiver.logger.debug(
                'setting socket receive buffer size to: %s', self.receiver.receive_buffer)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.receiver.receive_buffer)
        except OSError as ex:
            # What can we do here?
            #  - On Linux it would just set the max.
            #  - On mac, if too big it will just fail
            self.receiver.logger.warning('could not set socket SO_RCVBUF: %s', ex)

    def connection_lost(self, exc):
        self.transport = None


class RTCPSink(DatagramSink):
    """
    RTCP Report sink
    """
    def datagram_received(self, data, addr):
        self.receiver.handle_rtcp(data, addr)


class RTPSink(DatagramSink):
    """
    RTP sink
    """
    def datagram_received(self, data, addr):
        self.receiver.handle_rtp_data(data)


class UDPTransport(RTPTransport):
    """
    UDP Transport.
    --------------

    Uses a pair of consecutive UDP socket to receive RTP and RTCP.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.receive_buffer = kwargs.get('receive_buffer', DEFAULT_BUFFER_SIZE)
        self.send_buffer = kwargs.get('send_buffer', DEFAULT_BUFFER_SIZE)

        self.rtp_sink: RTPSink = None
        self.rtcp_sink: RTCPSink = None
        self.server_rtp = None
        self.server_rtcp = None
        self.rtcp_sender = None

    @classmethod
    def get_socket_pair(cls, bind_address=None, retry=10) -> Tuple[socket.socket, socket.socket]:
        """
        Try to allocate a pair of consecutive UDP ports.
        In theory, RTP and RTCP could have completely unrelated port numbers,
        but many server assume that RTCP = RTP + 1 (and even that RTP is always even...).
        :param bind_address: IP address to bind UDP ports. Default is ANY
        :param retry: number of attempts to perform before giving up.
        :return:
        """
        while retry > 0:
            retry -= 1
            rtp_sock = rtcp_sock = None

            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.bind((bind_address or '0.0.0.0', 0))

                rtp_port = sock.getsockname()[1]

                sock2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock2.bind((bind_address or '0.0.0.0', rtp_port + 1 if (rtp_port % 2) == 0 else rtp_port - 1))

                # Done!
                if (rtp_port % 2) == 0:
                    return sock, sock2

                return sock2, sock

            except IOError:
                _logger.error('unable to create requested socket pair')
                if rtp_sock:
                    rtp_sock.close()
                if rtcp_sock:
                    rtcp_sock.close()

        raise IOError('unable to allocate 2 consecutive ports')

    async def prepare(self):
        rtp_transport = rtcp_transport = None
        try:
            loop = asyncio.get_event_loop()

            rtp_sock, rtcp_sock = await asyncio.wait_for(
                loop.run_in_executor(None, self.get_socket_pair), 10)

            # Try to create RTP endpoint
            rtp_transport, self.rtp_sink = await loop.create_datagram_endpoint(
                lambda: RTPSink(self),
                sock=rtp_sock
            )

            # Try to create RTCP endpoint
            rtcp_transport, self.rtcp_sink = await loop.create_datagram_endpoint(
                lambda: RTCPSink(self),
                sock=rtcp_sock
            )

            self.logger.info(
                'UDP Transport ready, will use ports %s-%s',
                self.rtp_sink.local_port,
                self.rtcp_sink.local_port,
            )

        except Exception:
            if rtp_transport:
                rtp_transport.close()

            if rtcp_transport:
                rtcp_transport.close()

            raise

    @property
    def running(self) -> bool:
        """
        True if both RTP and RTCP sinks are running.
        """
        return self.rtp_sink.running and self.rtcp_sink.running

    def handle_rtcp(self, data, sender):
        """
        Special case for RTCP: we may not have received any report yet
        :param data:
        :param sender:
        """
        if self.rtcp_sender is None:
            self.logger.info('received RTCP from %s', sender)
            self.rtcp_sender = sender
        self.handle_rtcp_data(data)

    def on_transport_request(self, headers: dict):
        rtp_port = self.rtp_sink.local_port
        rtcp_port = self.rtcp_sink.local_port
        headers['Transport'] = f'RTP/AVP;unicast;client_port={rtp_port}-{rtcp_port}'

    def on_transport_response(self, headers: dict):
        if 'transport' not in headers:
            raise RTSPError('error on SETUP: Transport not found')

        # Get server port
        fields = self.parse_transport_fields(headers['transport'])

        if 'server_port' in fields:
            self.server_rtp, self.server_rtcp = fields['server_port'].split('-', 1)
            self.server_rtp = int(self.server_rtp)
            self.server_rtcp = int(self.server_rtcp)
            self.logger.info('server RTP/RTCP ports: %s-%s', self.server_rtp, self.server_rtcp)

    def close(self, error=None):
        """
        Perform cleanup, which by default is closing both sinks.
        """
        super().close(error)
        self.rtp_sink.close()
        self.rtcp_sink.close()

    @staticmethod
    def send_upstream(sink, address, port, count=5, length=200):
        """
        Send dummy packets to RTP source port to force NAT traversal
        :param sink: socket where to send dummy traffic
        :param address: server address
        :param port: server port
        :param count: number of packets to be sent
        :param length: length of payload
        """
        for _ in range(count):
            data = bytearray([randint(0, 255) for _ in range(length)])
            sink.sendto(data, (address, port))

    async def warmup(self):
        """
        If server ports were received, send reverse direction dummy
        packets to force NAT traversal
        """
        await super().warmup()

        if self.server_rtp is not None:
            self.logger.info('sending warmup RTP uplink traffic')
            self.send_upstream(self.rtp_sink, self.connection.host, self.server_rtp)

        if self.server_rtcp is not None:
            self.logger.info('sending warmup RTCP uplink traffic')
            self.send_upstream(self.rtcp_sink, self.connection.host, self.server_rtcp)

    async def send_rtcp_report(self, rtcp: RTCP):
        if self.rtcp_sender:
            self.rtcp_sink.sendto(bytes(rtcp), self.rtcp_sender)
