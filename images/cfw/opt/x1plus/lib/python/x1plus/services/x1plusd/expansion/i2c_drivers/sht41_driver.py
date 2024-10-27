import binascii

import asyncio
import time

class Sht41Driver():
    CMD_SERIAL_NUMBER = 0x89
    CMD_MEASURE_HIGH_PRECISION = 0xFD
    
    device_type = 'sht41'

    def __init__(self, address, i2c_driver, config, logger):
        self.logger = logger
        self.sensors = i2c_driver.daemon.sensors

        self.sht41 = i2c_driver.i2c.get_port(address)

        self.sht41.write((self.CMD_SERIAL_NUMBER, ))
        sn = self.sht41.read(readlen = 6)
        self.sn = binascii.hexlify(sn[0:2] + sn[3:5]).decode()
        
        self.interval_ms = int(config.get('interval_ms', 1000))
        self.name = config.get('name', f"{i2c_driver.ftdi_path}/i2c/0x{address:02x}/{self.device_type}/{self.sn}")
        
        self.task = asyncio.create_task(self._task())
        self.logger.info(f"probed {self.device_type.upper()} sensor at 0x{address:2x} with serial number {self.sn}")

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
            
                await self.sensors.publish(self.name, type = self.device_type, serial = self.sn, t_c = t_C, rh_pct = rh_pct)
            except Exception as e:
                await self.sensors.publish(self.name, type = self.device_type, serial = self.sn, inop = { 'exception': f"{e.__class__.__name__}: {e}" })
            
            await asyncio.sleep(self.interval_ms / 1000.0)