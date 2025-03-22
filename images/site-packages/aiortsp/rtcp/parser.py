"""
RTCP Parsing module
-------------------
This should really just be a lib call like we do for RTP (using dpkt),
but there is no light/easily importable RTCP parser available...
"""
from abc import ABC, abstractmethod
from struct import unpack, pack
from typing import Tuple, Dict, Type, Optional, List

TS_OFFSET_1900 = 2208988800


def ts_to_ntp(ts: float) -> Tuple[int, int]:
    """
    Convert from time.time() output to NTP (seconds, fraction).
    """
    ts += TS_OFFSET_1900  # From 1900 to 1970
    seconds, fraction = divmod(ts, 1)
    return int(seconds), int(fraction * 2**32)


def ntp_to_ts(seconds: int, fraction: int) -> float:
    """
    Convert from NTP (seconds, fraction) to time similar to time.time() output.
    """
    return (seconds + fraction / 2**32) - TS_OFFSET_1900


RTCP_TYPES: Dict[int, Type['RTCPPacket']] = {}


class RTCPPacket:
    """
    Sub-content of a generic RTCP container
    """
    pt = 0

    def __init_subclass__(cls, **kwargs):
        """
        Register RTCP type in the RTCP_TYPES registry
        """
        super().__init_subclass__(**kwargs)

        if cls.pt:
            RTCP_TYPES[cls.pt] = cls

    @classmethod
    @abstractmethod
    def unpack(cls, px, pt, p_len, data) -> 'RTCPPacket':
        """
        Unpack an RTCP sub-packet
        """

    @abstractmethod
    def __bytes__(self):
        """Serialize to bytes"""

    def pack(self, count, value, pad=False) -> bytes:
        """
        Turn an RTCP packet back into bytes
        """
        length = len(value) // 4 + (1 if len(value) % 4 != 0 else 0)
        px = 0x80 | (pad and len(value) % 4 != 0 and 0x20 or 0x00) | (count & 0x1f)
        header = pack('!BBH', px, self.pt, length)

        if not pad or len(value) % 4 == 0:
            padding = b''
        else:
            padding = b'\x00' * (4 - len(value) % 4 - 1) + pack('!B', 4 - len(value) % 4)
        return header + value + padding


class SRReport:
    """
    Sender/Receiver report content
    """

    def __init__(self, ssrc, flost, clost, hseq, jitter, lsr, dlsr):
        self.ssrc = ssrc
        self.flost = flost
        self.clost = clost
        self.hseq = hseq
        self.jitter = jitter
        self.lsr = lsr
        self.dlsr = dlsr

    @classmethod
    def unpack(cls, data: bytes) -> 'SRReport':
        """
        Transform a report into bytes
        """
        assert len(data) == 24
        ssrc, lost, hseq, jitter, lsr, dlsr = unpack('!IIIIII', data)
        flost, clost = (lost >> 24) & 0xFF, (lost & 0x00FFFFFF)
        return cls(ssrc, flost, clost, hseq, jitter, lsr, dlsr)

    def __repr__(self):
        return f'<SRReport ssrc={self.ssrc} seq={self.hseq} flost={self.flost}/256 cumul={self.clost} jitter={self.jitter}>'

    def __bytes__(self):
        return pack(
            '!IIIIII',
            self.ssrc,
            (self.flost << 24) | (self.clost & 0x00FFFFFF),
            self.hseq & 0xFFFFFFFF,
            self.jitter,
            self.lsr,
            self.dlsr
        )


class SRRR(RTCPPacket, ABC):
    """
    Base SR/RR class (most things in common)
    """

    def __init__(self, ssrc, extn=None, reports=None):
        self.ssrc = ssrc
        self.extn = extn
        self.reports = reports or []

    @classmethod
    def unpack(cls, px, pt, p_len, data):
        raise NotImplementedError

    @classmethod
    def parse_reports(cls, px, data):
        """
        Parse internal reports
        """
        reports = []
        for _ in range(px & 0x1F):
            assert len(data) >= 24
            report_data = data[:24]
            reports.append(SRReport.unpack(report_data))
            data = data[24:]
        return reports


class SR(SRRR):
    """
    SR sub-type
    """
    pt = 200

    def __init__(self, ssrc, ntp, ts=0, pkt_count=0, byte_count=0, extn=None, reports=None):
        super().__init__(ssrc=ssrc, extn=extn, reports=reports)
        self.ntp = ntp
        self.ts = ts
        self.pkt_count = pkt_count
        self.byte_count = byte_count

    @classmethod
    def unpack(cls, px, pt, p_len, data):
        ssrc, ntp1, ntp2, ts, pkt_count, byte_count = unpack('!IIIIII', data[:24])
        ntp = ntp_to_ts(ntp1, ntp2)
        reports = cls.parse_reports(px, data[24:])
        return cls(ssrc=ssrc, ntp=ntp, ts=ts, pkt_count=pkt_count, byte_count=byte_count, reports=reports)

    def __repr__(self):
        return f'<SR ssrc={self.ssrc} ts={self.ts} pkt={self.pkt_count} ntp={self.ntp} reports={self.reports}>'

    def __bytes__(self):
        ntp1, ntp2 = ts_to_ntp(self.ntp)
        value = pack('!IIIIII', self.ssrc, ntp1, ntp2, self.ts, self.pkt_count, self.byte_count)
        count = len(self.reports)
        for report in self.reports:
            value += bytes(report)
        if self.extn:
            value += self.extn

        return self.pack(count, value)


class RR(SRRR):
    """
    RR sub-type
    """
    pt = 201

    @classmethod
    def unpack(cls, px, pt, p_len, data):
        ssrc, = unpack('!I', data[:4])
        reports = cls.parse_reports(px, data[4:])
        return cls(ssrc, reports=reports)

    def __repr__(self):
        return f'<RR ssrc={self.ssrc} reports={self.reports}>'

    def __bytes__(self):
        value = pack('!I', self.ssrc)
        count = len(self.reports)

        for report in self.reports:
            value += bytes(report)

        if self.extn:
            value += self.extn

        return self.pack(count, value)


class SDES(RTCPPacket):
    """
    SDES sub-type
    """
    pt = 202

    CNAME, NAME, EMAIL, PHONE, LOC, TOOL, NOTE, PRIV = range(1, 9)

    def __init__(self, items=None):
        self.items = items or []

    @classmethod
    def unpack(cls, px, pt, p_len, data):
        items = []
        for _ in range(0, px & 0x1F):
            ssrc, = unpack('!I', data[:4])
            local_items = []
            data, count = data[4:], 0

            while len(data) >= 2:
                itype, ilen = unpack('!BB', data[:2])
                count += (2 + ilen)
                ivalue, data = data[2:2+ilen], data[2+ilen:]
                if itype == 0:
                    break
                local_items.append((itype, ivalue))
            if count % 4 != 0:
                data = data[(4-count % 4):]
            items.append((ssrc, local_items))

        return cls(items=items)

    def __repr__(self):
        return f'<SDES items={self.items}>'

    def __bytes__(self):
        value = b''
        count = len(self.items)

        for ssrc, items in self.items:
            chunk = pack('!I', ssrc)
            for n, v in items:
                chunk += pack('!BB', n, len(v) > 255 and 255 or len(v)) + v[:256]
            chunk += pack('!BB', 0, 0)  # to indicate end of items.
            if len(chunk) % 4 != 0:
                chunk += b'\x00' * (4 - len(chunk) % 4)
            value += chunk

        return self.pack(count, value)


class BYE(RTCPPacket):
    """
    BYE sub-type
    """
    pt = 203

    def __init__(self, ssrcs=None, reason=None):
        self.ssrcs = ssrcs or []
        self.reason = reason

    @classmethod
    def unpack(cls, px, pt, p_len, data):
        ssrcs, reason = [], None

        for _ in range(0, px & 0x01F):
            ssrc, = unpack('!I', data[:4])
            ssrcs.append(ssrc)
            data = data[4:]

        if data:
            rlen, = unpack('!B', data[:1])
            reason = data[1:1+rlen]

        return cls(ssrcs=ssrcs, reason=reason)

    def __repr__(self):
        return f'<BYE ssrcs={self.ssrcs} reason={self.reason}>'

    def __bytes__(self):
        value = b''
        count = len(self.ssrcs)
        for ssrc in self.ssrcs:
            value += pack('!I', ssrc)

        if self.reason:
            reason_len = min(len(self.reason), 255)
            value += pack('!B', reason_len) + self.reason[:reason_len]

        return self.pack(count, value)


class APP(RTCPPacket):
    """
    APP sub-type
    """
    pt = 204

    def __init__(self, subtype, ssrc, name, data=None):
        self.subtype = subtype
        self.ssrc = ssrc
        self.name = name
        self.data = data

    @classmethod
    def unpack(cls, px, pt, p_len, data):
        subtype = px & 0x1F
        ssrc, name = unpack('!I4s', data[:8])
        data = data[8:]

        return cls(subtype=subtype, ssrc=ssrc, name=name, data=data)

    def __repr__(self):
        return f'<APP stype={self.subtype} ssrc={self.ssrc} name={self.name} data_len={len(self.data)}>'

    def __bytes__(self):
        return self.pack(self.subtype, self.data)


class RTCP:
    """
    RTP Control Protocol Packet
    """

    def __init__(self, packets=None):
        self.packets: List[RTCPPacket] = packets or []

    @classmethod
    def unpack(cls, data: bytes) -> 'RTCP':
        """
        Parse a buffer into an RTCP instance
        """
        packets = []

        # Iterate on every packet found
        while data:

            # Unpack the header before deciding type
            px, pt, p_len = unpack('!BBH', data[:4])

            # Check version
            if px & 0xC0 != 0x80:
                raise ValueError('RTP version must be 2')

            # Check type exists
            if pt not in RTCP_TYPES:
                raise ValueError(f'Not an RTCP packet type: {pt}')

            # Split current bytes and bytes from next packet
            payload_length = 4 + p_len * 4
            if payload_length > len(data):
                raise ValueError(f'RTCP Packet truncated ({payload_length} > {len(data)})')

            payload, data = data[4:payload_length], data[payload_length:]

            if px & 0x20:
                # There is some padding to be removed
                payload = payload[:len(payload)-payload[-1]]

            packets.append(RTCP_TYPES[pt].unpack(px, pt, p_len, payload))

        return cls(packets=packets)

    def get(self, pt: int) -> Optional[RTCPPacket]:
        """
        Return first occurrence of given payload type, if any.
        """
        match = [p for p in self.packets if p.pt == pt]
        return None if not match else match[0]

    def __repr__(self):
        return f'RTCP({self.packets})'

    def __bytes__(self):
        result = b''
        for packet in self.packets:
            result += bytes(packet)
        return result
