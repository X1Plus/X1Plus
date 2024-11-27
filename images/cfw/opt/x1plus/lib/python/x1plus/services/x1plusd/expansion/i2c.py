import os
import re
import logging
import importlib

import pyftdi.i2c
import binascii

import asyncio
import time

from x1plus.utils import module_loader, module_docstring_parser

logger = logging.getLogger(__name__)

class I2cDriver():
    DEVICE_DRIVERS = {}
    DRIVER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), './i2c_drivers')
    
    def __init__(self, daemon, config, ftdi_path, port_name):
        self.ftdi_path = ftdi_path

        self.i2c = pyftdi.i2c.I2cController()
        self.i2c.configure(ftdi_path, frequency=50000)
        
        self.daemon = daemon
        self.devices = []

        # Load all valid driver classes from directory
        for filename in os.listdir(self.DRIVER_DIR):
            if filename.endswith(".py") and not filename.startswith("_"):
                module_name = filename[:-3]
                driver_path = os.path.join(self.DRIVER_DIR, filename)

                driver_data = module_docstring_parser(driver_path, "i2c-driver")
                if not driver_data or not driver_data.get("class_name", None) or not driver_data.get("device_type", None):
                    continue

                package = "x1plus.services.x1plusd.expansion.i2c_drivers"

                module, module_name = module_loader(driver_path, package)
                if not module:
                    continue
                if not hasattr(module, driver_data.get("class_name")):
                    logger.warn(f"Could not load {module_name} in i2c driver loader. Class not found: {driver_data.get("class_name")}")
                    continue

                try:
                    driver_class = getattr(module, driver_data.get("class_name"))
                    self.DEVICE_DRIVERS[driver_data.get("device_type")] = driver_class
                    logger.info(f"Loaded I2C Driver: {driver_data.get("device_type")}")
                except Exception as e:
                    logger.error(f"Failed to load I2C Driver '{driver_data.get("device_type")}': {e.__class__.__name__}: {e}")
        
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
