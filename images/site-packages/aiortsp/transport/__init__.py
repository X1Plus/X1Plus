"""
RTP Transport module.
---------------------

In this file lies the main part of:
 - handling RTP/RTCP data
 - sending RTCP reports
 - allowing clients to subscribe to RTP/RTCP packets

Then in different files can be found different transport implementation.
"""
from typing import Type

from .base import RTPTransport, RTPTransportClient  # noqa
from .tcp import TCPTransport
from .udp import UDPTransport


def transport_for_scheme(scheme: str) -> Type[RTPTransport]:
    """Return transport type based on scheme"""
    transport_class = {
        'rtsp': UDPTransport,
        'rtspt': TCPTransport,
        'rtsps': TCPTransport
    }.get(scheme)

    if not transport_class:
        raise ValueError(f'invalid URL scheme `{scheme}`')

    return transport_class
