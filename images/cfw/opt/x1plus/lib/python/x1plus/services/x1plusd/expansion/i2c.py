import os
import re
import logging

import pyftdi.i2c
import binascii

import asyncio
import time

from . import ExpansionManager

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
                    # Only load device with driver if requested by I2C config
                    if driver := self.DEVICE_DRIVERS.get(device, None):
                        self.devices.append(driver(address = address, i2c_driver = self, config = subconfig))
                    else:
                        logger.error(f"failed to initialize driver for {device}@0x{address:2x} on {ftdi_path}. Compatible driver not found")
                except Exception as e:
                    logger.error(f"failed to initialize {device}@0x{address:2x} on {ftdi_path}: {e.__class__.__name__}: {e}")

    def disconnect(self):
        logger.info("shutting down I2C")
        for d in self.devices:
            d.disconnect()
        self.i2c.close()

ExpansionManager.DRIVERS["i2c"] = I2cDriver

def register_driver(name, clazz = None):
    """
    Register an i2c driver by name with the expansion i2c subsystem.
    
    If used with clazz == None, then behaves like a decorator.
    """
    def decorator(clazz):
        assert name not in I2cDriver.DEVICE_DRIVERS
        I2cDriver.DEVICE_DRIVERS[name] = clazz
        logger.info(f"registered I2C driver \"{name}\"")
        return clazz

    if clazz is None:
        return decorator
    else:
        decorator(clazz)
