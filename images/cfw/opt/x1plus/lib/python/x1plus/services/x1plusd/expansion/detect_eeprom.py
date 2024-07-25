"""

The X1Plus expansion-expansion boards have a 24C02 EEPROM attached with
SCL=D7, SDA=D6.  We bit-bang this with the MPSSE engine, since there's no
actual I2C engine hooked up to those pins.

"""

import logging

from pyftdi.ftdi import Ftdi

logger = logging.getLogger(__name__)


# SCL = 0x80
# SDA = 0x40

start_and_addr = bytes([
    Ftdi.SET_BITS_LOW, 0x00, 0x00,
    Ftdi.SET_BITS_LOW, 0x00, 0x00,
    Ftdi.SET_BITS_LOW, 0x00, 0x00, # start sequence: SCL = 1, SDA = 1
    Ftdi.SET_BITS_LOW, 0x00, 0x40, # start sequence: SCL = 1, SDA = 0
    Ftdi.SET_BITS_LOW, 0x00, 0xC0, # start sequence: SCL = 0, SDA = 0
    
    Ftdi.SET_BITS_LOW, 0x00, 0x80, # SDA = 1, SCL = 0: address
    Ftdi.SET_BITS_LOW, 0x00, 0x00, # SDA = 1, SCL = 1
    Ftdi.SET_BITS_LOW, 0x00, 0x80, # SDA = 1, SCL = 0

    Ftdi.SET_BITS_LOW, 0x00, 0xC0, # SDA = 0, SCL = 0
    Ftdi.SET_BITS_LOW, 0x00, 0x40, # SDA = 0, SCL = 1
    Ftdi.SET_BITS_LOW, 0x00, 0xC0, # SDA = 0, SCL = 0

    Ftdi.SET_BITS_LOW, 0x00, 0x80, # SDA = 1, SCL = 0
    Ftdi.SET_BITS_LOW, 0x00, 0x00, # SDA = 1, SCL = 1
    Ftdi.SET_BITS_LOW, 0x00, 0x80, # SDA = 1, SCL = 0
    
    Ftdi.SET_BITS_LOW, 0x00, 0xC0, # SDA = 0, SCL = 0
    Ftdi.SET_BITS_LOW, 0x00, 0x40, # SDA = 0, SCL = 1
    Ftdi.SET_BITS_LOW, 0x00, 0xC0, # SDA = 0, SCL = 0

    Ftdi.SET_BITS_LOW, 0x00, 0xC0, # SDA = 0, SCL = 0
    Ftdi.SET_BITS_LOW, 0x00, 0x40, # SDA = 0, SCL = 1
    Ftdi.SET_BITS_LOW, 0x00, 0xC0, # SDA = 0, SCL = 0

    Ftdi.SET_BITS_LOW, 0x00, 0xC0, # SDA = 0, SCL = 0
    Ftdi.SET_BITS_LOW, 0x00, 0x40, # SDA = 0, SCL = 1
    Ftdi.SET_BITS_LOW, 0x00, 0xC0, # SDA = 0, SCL = 0

    Ftdi.SET_BITS_LOW, 0x00, 0xC0, # SDA = 0, SCL = 0
    Ftdi.SET_BITS_LOW, 0x00, 0x40, # SDA = 0, SCL = 1
    Ftdi.SET_BITS_LOW, 0x00, 0xC0, # SDA = 0, SCL = 0
])

writezero = bytes([
    Ftdi.SET_BITS_LOW, 0x00, 0xC0, # SDA = 0, SCL = 0: write
    Ftdi.SET_BITS_LOW, 0x00, 0x40, # SDA = 0, SCL = 1
    Ftdi.SET_BITS_LOW, 0x00, 0xC0, # SDA = 0, SCL = 0
])

writeone = bytes([
    Ftdi.SET_BITS_LOW, 0x00, 0x80, # SDA = 1, SCL = 0: write
    Ftdi.SET_BITS_LOW, 0x00, 0x00, # SDA = 1, SCL = 1
    Ftdi.SET_BITS_LOW, 0x00, 0x80, # SDA = 1, SCL = 0
])

readbit = bytes([
    Ftdi.SET_BITS_LOW, 0x00, 0x80, # SDA = 1, SCL = 0
    Ftdi.SET_BITS_LOW, 0x00, 0x00, # SDA = 1, SCL = 1: read ACK
    Ftdi.GET_BITS_LOW,
    Ftdi.SET_BITS_LOW, 0x00, 0x80, # SDA = 1, SCL = 0
])

stop = bytes([
    Ftdi.SET_BITS_LOW, 0x00, 0xC0, # stop sequence: SCL = 0, SDA = 0
    Ftdi.SET_BITS_LOW, 0x00, 0x40, # stop sequence: SCL = 1, SDA = 0
    Ftdi.SET_BITS_LOW, 0x00, 0x00, # stop sequence: SCL = 1, SDA = 1
    Ftdi.SET_BITS_LOW, 0x00, 0x00,
    Ftdi.SET_BITS_LOW, 0x00, 0x00,

    Ftdi.SEND_IMMEDIATE])

def detect_eeprom(ftdipath):
    ftdi = Ftdi()
    ftdi.open_mpsse_from_url(ftdipath, frequency=50000)
    ftdi.purge_buffers()
    ftdi.enable_adaptive_clock(False)

    # Write address 0x00.
    cmd = bytearray()
    cmd += start_and_addr
    cmd += writezero # write
    cmd += readbit # ACK
    for i in range(8):
        cmd += writezero # write 0 for address
    cmd += readbit # ACK
    cmd += stop

    ftdi.write_data(cmd)
    rd = ftdi.read_data_bytes(2, 4)
    if rd[0] & 0x40:
        logger.info(f"NACK for device address on {ftdipath}")
        return None
    if rd[0] & 0x40:
        logger.info(f"NACK for write address 0 on {ftdipath}")
        return None

    # Read a byte.

    cmd = bytearray()
    cmd += start_and_addr
    cmd += writeone # read
    cmd += readbit # ACK
    for i in range(8):
        cmd += readbit
    cmd += stop

    rbs = bytearray()
    for i in range(256):
        ftdi.write_data(cmd)
        rd = ftdi.read_data_bytes(9, 4)
        if rd[0] & 0x40:
            logger.info(f"NACK for read byte {i} on {ftdipath}")
            return None
        b = 0
        for d in rd[1:9]:
            b <<= 1
            b |= 1 if d & 0x40 else 0
        rbs.append(b)

    ftdi.close()
    
    return rbs
