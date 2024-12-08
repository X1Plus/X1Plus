"""
[module]
name=pmsa003i
enabled=true
[end]
"""
try:
    from x1plus.services.x1plusd.modules.expansion.i2c import register_driver
except ImportError:
    from ..expansion.i2c import register_driver

import logging
import asyncio
import time

logger = logging.getLogger(__name__)
name = 'pmsa003i'

class Pmsa003iDriver():

    def __init__(self, address, i2c_driver, config):
        self.sensors = i2c_driver.daemon.sensors

        self.pmsa003i = i2c_driver.i2c.get_port(address)
        
        self.interval_ms = int(config.get('interval_ms', 1000))
        self.name = config.get('name', f"{i2c_driver.ftdi_path}/i2c/0x{address:02x}/{name}")
        self.overflow_mitigation = config.get('overflow_mitigation', False)
        
        
        self.task = asyncio.create_task(self._task())
        logger.info(f"probed {name.upper()} sensor at 0x{address:2x}")

    def disconnect(self):
        if self.task:
            self.task.cancel()
            self.task = None
    
   
    async def _task(self):
        while True:
            try:
            
                did_read = False
                da = None
                for i in range(20):
                    da = self.pmsa003i.read(readlen = 32)
                    if da[0] == 0x42 and da[1] == 0x4D:
                        did_read = True
                        break
                    await asyncio.sleep(0.01)
                if not did_read or da is None:
                    raise Exception(f"{name.upper()} did not finish measuring")

                # Standard Concentration µg/m^3
                pm1_0_ugm3_std = (da[4] << 8) | da[5]
                pm2_5_ugm3_std = (da[6] << 8) | da[7]
                pm10_ugm3_std = (da[8] << 8) | da[9]
                
                # Environmental Concentration µg/m^3 - Useful
                pm1_0_ugm3_env = (da[10] << 8) | da[11]
                pm2_5_ugm3_env = (da[12] << 8) | da[13]
                pm10_ugm3_env = (da[14] << 8) | da[15]
                
                # Particles Greater Than <particle_size>μm / 0.1L air
                pm0_3_conc = (da[16] << 8) | da[17]
                pm0_5_conc = (da[18] << 8) | da[19]
                pm1_0_conc = (da[20] << 8) | da[21]
                pm2_5_conc = (da[22] << 8) | da[23]
                pm5_0_conc = (da[24] << 8) | da[25]
                pm10_conc = (da[26] << 8) | da[27]
                
                # Overflow mitigation from 16bit limit
                if pm5_0_conc < pm10_conc:
                    if self.overflow_mitigation:
                        pm5_0_conc += 65535
                    else: 
                        pm5_0_conc = -1
                        logger.info(f"{name.upper()} {self.name} value for PM > 5.0 Concentation is out of range (>65535)")
                if pm2_5_conc < pm5_0_conc:
                    if self.overflow_mitigation:
                        pm2_5_conc += 65535
                    else: 
                        pm2_5_conc = -1
                        logger.info(f"{name.upper()} {self.name} value for PM > 2.5 Concentation is out of range (>65535)")
                if pm1_0_conc < pm2_5_conc:
                    if self.overflow_mitigation:
                        pm1_0_conc += 65535
                    else: 
                        pm1_0_conc = -1
                        logger.info(f"{name.upper()} {self.name} value for PM > 1.0 Concentation is out of range (>65535)")
                if pm0_5_conc < pm1_0_conc:
                    if self.overflow_mitigation:
                        pm0_5_conc += 65535
                    else: 
                        pm0_5_conc = -1
                        logger.info(f"{name.upper()} {self.name} value for PM > 0.5 Concentation is out of range (>65535)")
                if pm0_3_conc < pm0_5_conc:
                    if self.overflow_mitigation:
                        pm0_3_conc += 65535
                    else: 
                        pm0_3_conc = -1
                        logger.info(f"{name.upper()} {self.name} value for PM > 0.3 Concentation is out of range (>65535)")

                await self.sensors.publish(self.name, type = name,
                    pm1_0_ugm3_std = pm1_0_ugm3_std, pm2_5_ugm3_std = pm2_5_ugm3_std, pm10_ugm3_std = pm10_ugm3_std,
                    pm1_0_ugm3 = pm1_0_ugm3_env, pm2_5_ugm3 = pm2_5_ugm3_env, pm10_ugm3 = pm10_ugm3_env, 
                    pm0_3_conc = pm0_3_conc, pm0_5_conc = pm0_5_conc, pm1_0_conc = pm1_0_conc, 
                    pm2_5_conc = pm2_5_conc, pm5_0_conc = pm5_0_conc, pm10_conc = pm10_conc, overflow_mitigation=self.overflow_mitigation)
            except Exception as e:
                await self.sensors.publish(self.name, type = name, inop = { 'exception': f"{e.__class__.__name__}: {e}" })
            
            await asyncio.sleep(self.interval_ms / 1000.0)

@register_driver("pmsa003i")
def _driver_pmsa003i(handler):
    handler.DEVICE_DRIVERS.setdefault(name, Pmsa003iDriver)
