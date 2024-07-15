import os
import logging

import pyftdi.i2c
import binascii

import usb.util
import asyncio

logger = logging.getLogger(__name__)

class I2cDriver():
    DEVICE_DRIVERS = {}
    
    def __init__(self, manager, config, ftdi_path):
        self.i2c = pyftdi.i2c.I2cController()
        self.i2c.configure(ftdi_path, frequency=50000)
        
        self.manager = manager
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
        self.sht41 = i2c_driver.i2c.get_port(address)

        self.sht41.write((self.CMD_SERIAL_NUMBER, ))
        sn = self.sht41.read(readlen = 6)
        self.sn = binascii.hexlify(sn[0:2] + sn[3:5]).decode()
        
        self.interval_ms = int(config.get('interval_ms', 1000))
        self.name = config.get('name', None)
        
        self.task = asyncio.create_task(self._task())
        logger.info(f"probed SHT41 sensor at 0x{address:2x} with serial number {self.sn}")

    def disconnect(self):
        if self.task:
            self.task.cancel()
            self.task = None
    
    async def _task(self):
        while True:
            self.sht41.write((self.CMD_MEASURE_HIGH_PRECISION, ))
            da = self.sht41.read(readlen = 6)
            t_raw = int.from_bytes(da[0:2], "big")
            rh_raw = int.from_bytes(da[3:5], "big")
            
            t_C = -45 + 175 * t_raw / 65535
            rh_pct = -6 + 125 * rh_raw/65535
            
            # XXX: later, feed this to a x1plusd sensors subsystem that pubs to mqtt and to DBus
            logger.info(f"SENSOR UPDATE: sensor name {self.name}, type sht41, serial {self.sn}, t {t_C}, rh_pct {rh_pct}")
            
            await asyncio.sleep(self.interval_ms / 1000.0)
    
I2cDriver.DEVICE_DRIVERS['sht41'] = Sht41Driver
