"""

asyncio interface to connect to the X1's RTSP daemon, grab exactly enough
data to decode a single frame, and then pass it through a h264-to-JPEG
encode engine

"""

import asyncio
import logging
import os
import sys
import ssl
import tempfile

from aiortsp.rtsp.reader import RTSPReader

logger = logging.getLogger(__name__)

NALU_TYPE_CODED_NONIDR_SLICE = 1
NALU_TYPE_CODED_IDR_SLICE = 5
NALU_TYPE_SEQUENCE_PARAMETER_SET = 7
NALU_TYPE_PICTURE_PARAMETER_SET = 8
NALU_TYPE_FU_A = 28 # that's "Fragmentation Unit A" to you!

class AioRtspReceiver:
    def __init__(self):
        self.url = f'rtsps://bblp:{open("/config/device/access_token", "r").read().strip()}@127.0.0.1/streaming/live/1'
    
    def local_rtspreader(self):
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        return RTSPReader(self.url, log_level=10, ssl=ssl_ctx)

    def handle_nalu(self, pkt):
        nalu_header = pkt[0]
        if nalu_header >> 7: # "forbidden_zero_bit"
            logger.error(f"NALU with header {nalu_header:2x} is broken")
            return
        nalu_nri = (nalu_header >> 5) & 3
        nalu_type = nalu_header & 0x1F
    
        if nalu_type == NALU_TYPE_FU_A:
            fu_header = pkt[1]
            if fu_header >> 7: # start bit for FU
                # forge a header
                self.fu_buf = bytes([(nalu_nri << 5) | (fu_header & 0x1F)])
            self.fu_buf += pkt[2:]
            if (fu_header >> 6) & 1: # end bit for FU
                self.handle_nalu(self.fu_buf)
        elif nalu_type == NALU_TYPE_SEQUENCE_PARAMETER_SET:
            self.got_seqparam = True
            self.received_nals += b"\x00\x00\x01" + pkt
            logger.debug("sequence parameter set")
        elif nalu_type == NALU_TYPE_PICTURE_PARAMETER_SET:
            self.got_picparam = True
            self.received_nals += b"\x00\x00\x01" + pkt
            logger.debug("picture parameter set")
        elif nalu_type == NALU_TYPE_CODED_IDR_SLICE:
            self.got_idr = True
            self.received_nals += b"\x00\x00\x01" + pkt
            logger.debug(f"coded IDR slice, {len(pkt)} bytes")
        elif nalu_type == NALU_TYPE_CODED_NONIDR_SLICE:
            logger.debug(f"coded non-IDR slice, {len(pkt)} bytes")
        else:
            logger.error(f"unknown NALU type {nalu_type}")

    async def receive_h264(self):
        self.received_nals = b""
        self.fu_buf = b""
        self.got_seqparam = False
        self.got_picparam = False
        self.got_idr = False

        async with self.local_rtspreader() as reader:
            async for pkt in reader.iter_packets():
                self.handle_nalu(pkt.data)
                
                if self.got_seqparam and self.got_picparam and self.got_idr:
                    logger.debug(f"received {len(self.received_nals)} bytes of h264")
                    return self.received_nals
    
    async def receive_jpeg(self):
        h264 = await self.receive_h264()
        with tempfile.NamedTemporaryFile() as h264file, tempfile.NamedTemporaryFile() as jpegfile:
            h264file.write(h264)
            os.system(f"/opt/x1plus/bin/h264tojpeg {h264file.name} {jpegfile.name}")
            jpeg = jpegfile.read()
        return jpeg

async def _main():
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)

    logger.debug("beginning rx...")
    rx = AioRtspReceiver()
    jpeg = await rx.receive_jpeg()
    logger.debug(f"jpeg length {len(jpeg)}")

if __name__ == '__main__':
    asyncio.run(_main())
