import logging
import struct

import usb

logger = logging.getLogger(__name__)

RP2040_MAGIC = 0x431FD10B

class Rp2040Boot:
    def __init__(self):
        def is_boot_rp2040(dev):
            try:
                return dev.idVendor == 0x2E8A and dev.idProduct == 0x0003 and dev.product == "RP2 Boot"
            except:
                return False
        self.rp2040 = usb.core.find(custom_match = is_boot_rp2040)
        if not self.rp2040:
            raise IOError("no RP2040 bootloader found")
        
        for i in range(self.rp2040[0].bNumInterfaces):
            if self.rp2040.is_kernel_driver_active(i):
                logger.debug(f"detaching kernel driver from interface {i} so we can have it")
                self.rp2040.detach_kernel_driver(i)

        self.rp2040.set_configuration()
        self.intf = self.rp2040[0][(1, 0)] # XXX: this is not applicable if the MSC interface is not present
        self.intf.set_altsetting()
        self.ep_out = self.intf[0]
        self.ep_in  = self.intf[1]
        self.ep_out.clear_halt()
        self.ep_in.clear_halt()
    
    def send_cmd(self, cmdid, args = b"", data = b"", shouldreturn = True):
        cmd = struct.pack("<LLBBHL16s", RP2040_MAGIC, 31337, cmdid, len(args), 0, len(data), args)
        assert len(cmd) == 32
        self.ep_out.write(cmd)
        if len(data) > 0:
            self.ep_out.write(data)
        rv = None
        try:
            rv = self.ep_in.read(1024)
        except:
            if shouldreturn:
                raise
            else:
                usb.util.dispose_resources(self.rp2040)
                self.rp2040 = None
        if shouldreturn and rv:
            raise IOError("rp2040 returned from command that should have failed")
    
    def exclusive(self):
        self.send_cmd(0x01, b"\x02")
    
    def reboot(self, pc, sp, delay):
        args = struct.pack("<LLL", pc, sp, delay)
        self.send_cmd(0x02, args, shouldreturn = False)
    
    def write(self, addr, data):
        args = struct.pack("<LL", addr, len(data))
        self.send_cmd(0x05, args, data)
    
    def exec(self, addr):
        args = struct.pack("<L", addr)
        self.send_cmd(0x08, args, shouldreturn = False)
    
    def bootbin(self, fn):
        self.exclusive()
        
        with open(fn, "rb") as f:
            bs = f.read()
        
        logger.debug(f"writing {len(bs)} bytes to 0x20000000")
        self.write(0x20000000, bs)
        logger.debug(f"booting RP2040")
        self.reboot(0x20000001, 0x20040000, 10)
