import os
import logging

import pyftdi.i2c
import binascii

import asyncio
import time

logger = logging.getLogger(__name__)

class I2cDriver():
    DEVICE_DRIVERS = {}
    
    def __init__(self, daemon, config, ftdi_path, port_name):
        self.ftdi_path = ftdi_path

        self.i2c = pyftdi.i2c.I2cController()
        self.i2c.configure(ftdi_path, frequency=50000)
        
        self.daemon = daemon
        self.devices = []
        
        # I2C config format is just a dict of addresses -> devices
        for address, devices in config.items():
            address = int(address, 0)
            
            for device, subconfig in devices.items():
                try:
                    self.devices.append(self.DEVICE_DRIVERS[device](address = address, i2c_driver = self, config = subconfig))
                except Exception as e:
                    logger.error(f"failed to initialize {device}@0x{address:2x} on {ftdi_path}: {e.__class__.__name__}: {e}")
    
    def disconnect(self):
        logger.info("shutting down I2C")
        for d in self.devices:
            d.disconnect()
        self.i2c.close()

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
        self.name = config.get('name', f"{i2c_driver.ftdi_path}/i2c/0x{address:02x}/sht41/{self.sn}")
        
        self.task = asyncio.create_task(self._task())
        logger.info(f"probed SHT41 sensor at 0x{address:2x} with serial number {self.sn}")

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
            
                await self.sensors.publish(self.name, type = 'sht41', serial = self.sn, t_c = t_C, rh_pct = rh_pct)
            except Exception as e:
                await self.sensors.publish(self.name, type = 'sht41', serial = self.sn, inop = { 'exception': f"{e.__class__.__name__}: {e}" })
            
            await asyncio.sleep(self.interval_ms / 1000.0)
    
I2cDriver.DEVICE_DRIVERS['sht41'] = Sht41Driver

class Aht20Driver():
    CMD_RESET = 0xBA
    CMD_INITIALIZE = 0xE1
    CMD_MEASURE = 0xAC

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
            raise Exception("AHT20 never calibrated")
        
        self.aht20.write(b'\x71')
        
        self.interval_ms = int(config.get('interval_ms', 1000))
        self.name = config.get('name', f"{i2c_driver.ftdi_path}/i2c/0x{address:02x}/aht20")
        
        self.task = asyncio.create_task(self._task())
        logger.info(f"probed AHT20 sensor at 0x{address:2x}")

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
                    raise Exception("AHT20 did not finish measuring")

                da = self.aht20.read(readlen = 6)
                
                rh_raw = (da[1] << 12) | (da[2] << 4) | (da[3] >> 4)
                rh_pct = (rh_raw * 100) / 0x100000
                
                t_raw = ((da[3] & 0xF) << 16) | (da[4] << 8) | da[5]
                t_C = ((t_raw * 200.0) / 0x100000) - 50                

                await self.sensors.publish(self.name, type = 'aht20', t_c = t_C, rh_pct = rh_pct)
            except Exception as e:
                await self.sensors.publish(self.name, type = 'aht20', inop = { 'exception': f"{e.__class__.__name__}: {e}" })
            
            await asyncio.sleep(self.interval_ms / 1000.0)
    
I2cDriver.DEVICE_DRIVERS['aht20'] = Aht20Driver

class Pmsa003iDriver():

    device_type = 'pmsa003i'
    
    def __init__(self, address, i2c_driver, config):
        self.sensors = i2c_driver.daemon.sensors

        self.pmsa003i = i2c_driver.i2c.get_port(address)
        
        self.interval_ms = int(config.get('interval_ms', 1000))
        self.name = config.get('name', f"{i2c_driver.ftdi_path}/i2c/0x{address:02x}/{self.device_type}")
        self.overflow_mitigation = config.get('overflow_mitigation', False)
        
        
        self.task = asyncio.create_task(self._task())
        logger.info(f"probed {self.device_type.upper()} sensor at 0x{address:2x}")

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
                    raise Exception(f"{self.device_type.upper()} did not finish measuring")

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
                        logger.info(f"{self.device_type.upper()} {self.name} value for PM > 5.0 Concentation is out of range (>65535)")
                if pm2_5_conc < pm5_0_conc:
                    if self.overflow_mitigation:
                        pm2_5_conc += 65535
                    else: 
                        pm2_5_conc = -1
                        logger.info(f"{self.device_type.upper()} {self.name} value for PM > 2.5 Concentation is out of range (>65535)")
                if pm1_0_conc < pm2_5_conc:
                    if self.overflow_mitigation:
                        pm1_0_conc += 65535
                    else: 
                        pm1_0_conc = -1
                        logger.info(f"{self.device_type.upper()} {self.name} value for PM > 1.0 Concentation is out of range (>65535)")
                if pm0_5_conc < pm1_0_conc:
                    if self.overflow_mitigation:
                        pm0_5_conc += 65535
                    else: 
                        pm0_5_conc = -1
                        logger.info(f"{self.device_type.upper()} {self.name} value for PM > 0.5 Concentation is out of range (>65535)")
                if pm0_3_conc < pm0_5_conc:
                    if self.overflow_mitigation:
                        pm0_3_conc += 65535
                    else: 
                        pm0_3_conc = -1
                        logger.info(f"{self.device_type.upper()} {self.name} value for PM > 0.3 Concentation is out of range (>65535)")

                await self.sensors.publish(self.name, type = self.device_type,
                    pm1_0_ugm3_std = pm1_0_ugm3_std, pm2_5_ugm3_std = pm2_5_ugm3_std, pm10_ugm3_std = pm10_ugm3_std,
                    pm1_0_ugm3 = pm1_0_ugm3_env, pm2_5_ugm3 = pm2_5_ugm3_env, pm10_ugm3 = pm10_ugm3_env, 
                    pm0_3_conc = pm0_3_conc, pm0_5_conc = pm0_5_conc, pm1_0_conc = pm1_0_conc, 
                    pm2_5_conc = pm2_5_conc, pm5_0_conc = pm5_0_conc, pm10_conc = pm10_conc, overflow_mitigation=self.overflow_mitigation)
            except Exception as e:
                await self.sensors.publish(self.name, type = self.device_type, inop = { 'exception': f"{e.__class__.__name__}: {e}" })
            
            await asyncio.sleep(self.interval_ms / 1000.0)

I2cDriver.DEVICE_DRIVERS[Pmsa003iDriver.device_type] = Pmsa003iDriver
