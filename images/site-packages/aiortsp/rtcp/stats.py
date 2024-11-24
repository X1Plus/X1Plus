"""
RTCP Statistics module
"""

import logging
import random
from math import fabs
from time import time
from typing import Optional

from dpkt.rtp import RTP

from .parser import RTCP, SRReport, ts_to_ntp, RR, SDES, BYE, SR

_logger = logging.getLogger('rtcp.sink')

RTP_SEQ_MOD = (1 << 16)
MAX_MISORDER = 100
MAX_DROPOUT = 3000
UINT32_MASK = 0xFFFFFFFF
UINT32_MASK = 0xFFFFFFFF
NTP_MASK = 0xFFFF


class RTCPStats:
    """
    RTCP Statistics and response builder
    ------------------------------------

    This class builds statistics upon reception of RTP frames,
    handles reception of remote RTCP report from the server,
    and crafts RTCP report packet.

    This is a simplified version not handling multicast yet.
    """
    def __init__(self, name='unknown'):
        self.name = name
        self.ssrc = random.randint(0, 2**32)
        self.ntp = self.ntp_base = time()

        self.received = self.expected_prior = self.received_prior = self.transit = self.jitter = 0
        self.lost = self.fraction = self.pkt_count = self.oct_count = self.timeout = 0
        self.probation = self.last_received = self.ts = self.ts_base = 0

        self.maxseq = self.bad_seq = self.base_seq = self.cycles = None
        self.last_ts = self.last_ntp = self.rtcp_delay = None

    @property
    def cname(self) -> bytes:
        """
        Return CNAME for RR reporting
        """
        return f'{self.ssrc}@{self.name}'.encode()

    @property
    def extended_seq(self) -> int:
        """Extended sequence number, taking cycles into account"""
        return self.cycles + self.maxseq

    @property
    def lsr(self) -> int:
        """Build LSR report value"""
        ntp1, ntp2 = ts_to_ntp(self.last_ntp)
        return ((ntp1 & NTP_MASK) << 16) | ((ntp2 >> 16) & NTP_MASK)

    @property
    def dlsr(self) -> int:
        """Build DLSR report value"""
        return max(0, min(UINT32_MASK, int((time() - self.last_ntp) * 65536)))

    def init_seq(self, seq):
        """
        Initialize the seq using the newly received seq of RTP packet.
        """
        self.base_seq = self.maxseq = seq
        self.bad_seq = seq - 1
        self.cycles = self.received = self.received_prior = self.expected_prior = 0

    def update_seq(self, seq):
        """
        Update the source properties based on received RTP packet's seq.
        """
        seq_delta = (seq - self.maxseq) % 65536
        if self.probation > 0:
            if seq == self.maxseq + 1:
                self.probation = self.probation - 1
                self.maxseq = seq
                if self.probation == 0:
                    # reset
                    self.init_seq(seq)
                    self.received = self.received + 1
                    return
            else:
                # next packet should be in sequence
                self.probation = 1
                self.maxseq = seq
            return

        elif seq_delta < MAX_DROPOUT:
            # in order, within reasonable gap
            if seq < self.maxseq:
                self.cycles += RTP_SEQ_MOD
            self.maxseq = seq
        elif seq_delta <= (RTP_SEQ_MOD - MAX_MISORDER):
            # Huge gap
            if seq == self.bad_seq:
                # Sequence was either reset or changed
                self.init_seq(seq)
            else:
                self.bad_seq = (seq + 1) & (RTP_SEQ_MOD - 1)
                return
        # else:
            # duplicate or reordered packet

        # Count this packet
        self.received += 1

    def update_jitter(self, ts):
        """
        Update the jitter based on ts and arrival (in ts units).
        """
        transit = int(self.ts_now - ts)
        d, self.transit = int(fabs(transit - self.transit)), transit
        self.jitter += (1 / 16) * (d - self.jitter)

    def update_lost_expected(self):
        """
        Update the number of packets expected and lost for reporting.
        """
        expected = self.extended_seq - self.base_seq + 1
        received = self.received

        received_interval = received - self.received_prior
        expected_interval = expected - self.expected_prior
        lost_interval = expected_interval - received_interval

        self.expected_prior = expected
        self.received_prior = received
        self.lost = expected - received

        if expected_interval == 0 or lost_interval <= 0:
            self.fraction = 0
        else:
            self.fraction = (lost_interval << 8) // expected_interval

    @staticmethod
    def rtcp_interval(initial=False) -> float:
        """
        Simplified RTCP interval calculator.
        TODO implement multicast. In unicast, it does not really matter...
        :param initial: Is this the first interval (shorter)
        """
        return (2.5 if initial else 5.0) * (random.random() + 0.5) / 1.21828

    @property
    def ts_now(self):
        """The current RTP timestamp in ts unit based on current time."""
        ts = self.ts
        if self.ntp != self.ntp_base:
            ts += (time() - self.ntp) * ((self.ts - self.ts_base) / (self.ntp - self.ntp_base))
        return int(ts) & UINT32_MASK

    def update(self, pkt: RTP):
        """
        Called externally to handle a received RTP packet and update statistics.
        """
        seq = pkt.seq
        if self.base_seq is None:
            self.init_seq(seq)
        self.update_seq(seq)
        self.update_jitter(pkt.ts)
        self.last_received = time()

    def handle_rtcp(self, rtcp: RTCP):
        """
        RTCP packet received
        """
        for p in rtcp.packets:
            if isinstance(p, SR):
                self.last_ts = p.ts
                self.last_ntp = p.ntp

    def build_rtcp(self, send_bye=False) -> Optional[RTCP]:
        """
        Build an RTCP packet based on current situation.

        There may be not enough info yet to return anything!

        :param send_bye: Add a bye header
        """
        if self.last_ntp is None:
            # Not received a first SR report yet...
            return None

        if self.base_seq is None:
            # Not received an RTP packet yet...
            return None

        self.update_lost_expected()

        rtcp = RTCP()

        # Add receiver report
        rr = RR(self.ssrc, reports=[
            SRReport(
                ssrc=self.ssrc, flost=self.fraction, clost=self.lost,
                hseq=self.extended_seq, jitter=int(self.jitter),
                lsr=self.lsr, dlsr=self.dlsr)
        ])
        rtcp.packets.append(rr)

        # Add SDES identity
        sdes = SDES(items=[(1, [(SDES.CNAME, self.cname)])])
        rtcp.packets.append(sdes)

        # Add bye if requested
        if send_bye:
            bye = BYE(ssrcs=[self.ssrc])
            rtcp.packets.append(bye)

        return rtcp
