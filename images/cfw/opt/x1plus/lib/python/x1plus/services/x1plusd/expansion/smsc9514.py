import sys
import usb
import struct
import time

USB_DIR_OUT = 0
USB_DIR_IN = 0x80
USB_TYPE_VENDOR = 0x2 << 5
USB_RECIP_DEVICE = 0

USB_VENDOR_REQUEST_WRITE_REGISTER = 0xA0
USB_VENDOR_REQUEST_READ_REGISTER = 0xA1

ID_REV = 0x0
LED_GPIO_CFG = 0x24
GPIO_CFG = 0x28

E2P_CMD = 0x30
E2P_CMD_BUSY = 0x80000000
E2P_CMD_READ = 0x00000000
E2P_CMD_EWDS = 0x10000000
E2P_CMD_EWEN = 0x20000000
E2P_CMD_WRITE = 0x30000000
E2P_CMD_WRAL = 0x40000000
E2P_CMD_ERASE = 0x50000000
E2P_CMD_ERAL = 0x60000000
E2P_CMD_RELOAD = 0x70000000
E2P_CMD_TIMEOUT = 0x400
E2P_CMD_LOADED = 0x200
# E2P_CMD_ADDR is LSBs

E2P_DATA = 0x34


class Smsc9514:
    def __init__(self):
        self.smsc = usb.core.find(idVendor = 0x0424, idProduct = 0xEC00)
        if not self.smsc:
            raise RuntimeError("no LAN9514 found")
        assert self.reg_rd(ID_REV) == 0xEC000002, "invalid ID_REV"

    def reg_rd(self, addr):
        b = self.smsc.ctrl_transfer(USB_DIR_IN | USB_TYPE_VENDOR | USB_RECIP_DEVICE, USB_VENDOR_REQUEST_READ_REGISTER, 0, addr, 4)
        return struct.unpack("<L", b)[0]

    def reg_wr(self, addr, data):
        len = self.smsc.ctrl_transfer(USB_DIR_OUT | USB_TYPE_VENDOR | USB_RECIP_DEVICE, USB_VENDOR_REQUEST_WRITE_REGISTER, 0, addr, struct.pack("<L", data))
        assert len == 4

    def eeprom_wait(self, allow_timeout = True):
        for i in range(1000):
            rv = self.reg_rd(E2P_CMD)
            if (rv & E2P_CMD_TIMEOUT) and not allow_timeout:
                raise TimeoutError("EEPROM timeout detected by LAN9514")
            if (rv & E2P_CMD_BUSY) == 0:
                return
            time.sleep(0.001)
        raise TimeoutError("EEPROM wait timed out implicitly")

    def eeprom_read(self, addr):
        self.eeprom_wait()
        self.reg_wr(E2P_CMD, E2P_CMD_BUSY | E2P_CMD_READ | addr)
        self.eeprom_wait(allow_timeout = False)
        return self.reg_rd(E2P_DATA) & 0xFF
    
    def eeprom_write(self, addr, data):
        self.eeprom_wait()
        self.reg_wr(E2P_CMD, E2P_CMD_BUSY | E2P_CMD_EWEN)
        self.eeprom_wait(allow_timeout = False)
        self.reg_wr(E2P_DATA, data)
        self.reg_wr(E2P_CMD, E2P_CMD_BUSY | E2P_CMD_WRITE | addr)
        self.eeprom_wait(allow_timeout = False)

    def eeprom_readall(self):
        return bytes([self.eeprom_read(ad) for ad in range(512)])
    
    def eeprom_writeall(self, buf):
        for ad, da in enumerate(buf):
            self.eeprom_write(ad, da)
    
    def rp2040_reset(self):
        self.reg_wr(GPIO_CFG, (self.reg_rd(GPIO_CFG) & ~((1 << 28))) | (1 << 20) | (1 << 12) | (1 << 4))
        time.sleep(0.01)
        self.reg_wr(GPIO_CFG, (self.reg_rd(GPIO_CFG) & ~((1 << 28) | (1 << 4))) | (1 << 20) | (1 << 12))
        time.sleep(0.01)
        self.reg_wr(GPIO_CFG, (self.reg_rd(GPIO_CFG) & ~((1 << 28))) | (1 << 20) | (1 << 12) | (1 << 4))
        time.sleep(0.01)
