"""
[i2c-driver]
device_type=aht20
class_name=Aht20Driver
[end]
"""

import logging
import asyncio
import time

logger = logging.getLogger(__name__)

class Aht20Driver():
    CMD_RESET = 0xBA
    CMD_INITIALIZE = 0xE1
    CMD_MEASURE = 0xAC
    
    device_type = 'aht20'

    def __init__(self, address, i2c_driver, config):
        self.sensors = i2c_driver.daemon.sensors

        self.aht20 = i2c_driver.i2c.get_port(address)

        self.aht20.write((self.CMD_RESET, ))
        time.sleep(0.05)
        
        self.aht20.write(b'\xE1\x08\x00')
        time.sleep(0.02)
        self.aht20.write(b'\xBE\x08\x00')

        did_init = False
        for i in range(10):
            time.sleep(0.02)
            rv = self.aht20.read(readlen = 1)
            if (rv[0] & 0x88) == 0x08:
                did_init = True
                break
        if not did_init:
            raise Exception(f"{self.device_type.upper()} never calibrated")
        
        self.aht20.write(b'\x71')
        
        self.interval_ms = int(config.get('interval_ms', 1000))
        self.name = config.get('name', f"{i2c_driver.ftdi_path}/i2c/0x{address:02x}/{self.device_type}")
        
        self.task = asyncio.create_task(self._task())
        logger.info(f"probed {self.device_type.upper()} sensor at 0x{address:2x}")

    def disconnect(self):
        if self.task:
            self.task.cancel()
            self.task = None
    
    async def _task(self):
        while True:
            try:
                self.aht20.write(b'\xAC\x33\x00')#(self.CMD_MEASURE, 0x33, 0x00, ))
                await asyncio.sleep(0.01)
                
                did_read = False
                for i in range(10):
                    da = self.aht20.read(readlen = 1)
                    if da[0] & 0x80 == 0:
                        did_read = True
                        break
                    await asyncio.sleep(0.01)
                if not did_read:
                    raise Exception(f"{self.device_type.upper()} did not finish measuring")

                da = self.aht20.read(readlen = 6)
                
                rh_raw = (da[1] << 12) | (da[2] << 4) | (da[3] >> 4)
                rh_pct = (rh_raw * 100) / 0x100000
                
                t_raw = ((da[3] & 0xF) << 16) | (da[4] << 8) | da[5]
                t_C = ((t_raw * 200.0) / 0x100000) - 50                

                await self.sensors.publish(self.name, type = self.device_type, t_c = t_C, rh_pct = rh_pct)
            except Exception as e:
                await self.sensors.publish(self.name, type = self.device_type, inop = { 'exception': f"{e.__class__.__name__}: {e}" })
            
            await asyncio.sleep(self.interval_ms / 1000.0)