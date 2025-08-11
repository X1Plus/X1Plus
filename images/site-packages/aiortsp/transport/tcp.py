"""
TCP Interleaved transport.
"""
import logging

from aiortsp.rtcp.parser import RTCP
from aiortsp.rtsp.errors import RTSPError
from aiortsp.rtsp.parser import RTSPBinary
from .base import RTPTransport

_logger = logging.getLogger('rtp.session')

DEFAULT_BUFFER_SIZE = 4 * 1024 * 1024


class TCPTransport(RTPTransport):
    """
    TCP Transport.
    --------------

    Uses connection directly
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rtp_idx = None
        self.rtcp_idx = None

        self.receive_buffer = kwargs.get('receive_buffer', DEFAULT_BUFFER_SIZE)
        self.send_buffer = kwargs.get('send_buffer', DEFAULT_BUFFER_SIZE)

    async def prepare(self):
        self.rtp_idx = self.connection.register_binary_handler(self.handle_rtp_bin)
        self.rtcp_idx = self.connection.register_binary_handler(self.handle_rtcp_bin)
        self.logger.info(
            'receiving interleaved RTP (%s) and RTCP (%s)',
            self.rtp_idx, self.rtcp_idx
        )

    @property
    def running(self) -> bool:
        """
        True if both RTP and RTCP sinks are running.
        """
        return self.connection.running

    def close(self, error=None):
        """
        Perform cleanup, which by default is closing both sinks.
        """
        super().close(error)
        self.connection.close()

    def handle_rtcp_bin(self, binary: RTSPBinary):
        """
        Handle interleaved data registered as RTCP
        """
        self.handle_rtcp_data(binary.data)

    def handle_rtp_bin(self, binary: RTSPBinary):
        """
        Handle interleaved data registered as RTP
        """
        self.handle_rtp_data(binary.data)

    def on_transport_request(self, headers: dict):
        headers['Transport'] = f'RTP/AVP/TCP;unicast;interleaved={self.rtp_idx}-{self.rtcp_idx}'

    def on_transport_response(self, headers: dict):
        if 'transport' not in headers:
            raise RTSPError('error on SETUP: Transport not found')

        fields = self.parse_transport_fields(headers['transport'])

        assert fields.get('interleaved') == f'{self.rtp_idx}-{self.rtcp_idx}', 'invalid returned interleaved header'

    async def send_rtcp_report(self, rtcp: RTCP):
        self.connection.send_binary(self.rtcp_idx, bytes(rtcp))
