"""
[module]
name=sht41
default_enabled=true
[end]
"""
try:
    from x1plus.services.x1plusd.modules.expansion.i2c import register_driver
except ImportError:
    from ..expansion.i2c import register_driver

import binascii

import logging
import asyncio
import time

logger = logging.getLogger(__name__)
name = 'sht41'

class Sht41Driver():
    CMD_SERIAL_NUMBER = 0x89
    CMD_MEASURE_HIGH_PRECISION = 0xFD
    
    def __init__(self, address, i2c_driver, config):
        self.sensors = i2c_driver.daemon.sensors

        self.sht41 = i2c_driver.i2c.get_port(address)

        self.sht41.write((self.CMD_SERIAL_NUMBER, ))
        sn = self.sht41.read(readlen = 6)
        self.sn = binascii.hexlify(sn[0:2] + sn[3:5]).decode()
        
        self.interval_ms = int(config.get('interval_ms', 1000))
        self.name = config.get('name', f"{i2c_driver.ftdi_path}/i2c/0x{address:02x}/{name}/{self.sn}")
        
        self.task = asyncio.create_task(self._task())
        logger.info(f"probed {name.upper()} sensor at 0x{address:2x} with serial number {self.sn}")

    def disconnect(self):
        if self.task:
            self.task.cancel()
            self.task = None
    
    async def _task(self):
        while True:
            try:
                self.sht41.write((self.CMD_MEASURE_HIGH_PRECISION, ))
                da = self.sht41.read(readlen = 6)
                t_raw = int.from_bytes(da[0:2], "big")
                rh_raw = int.from_bytes(da[3:5], "big")
            
                t_C = -45 + 175 * t_raw / 65535
                rh_pct = -6 + 125 * rh_raw/65535
            
                await self.sensors.publish(self.name, type = name, serial = self.sn, t_c = t_C, rh_pct = rh_pct)
            except Exception as e:
                await self.sensors.publish(self.name, type = name, serial = self.sn, inop = { 'exception': f"{e.__class__.__name__}: {e}" })
            
            await asyncio.sleep(self.interval_ms / 1000.0)

@register_driver("sht41")
def _driver_sht41(handler):
    handler.DEVICE_DRIVERS.setdefault(name, Sht41Driver)
