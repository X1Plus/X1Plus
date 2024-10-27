import os
import logging
import importlib.util
import inspect

import pyftdi.i2c
import binascii

import asyncio
import time

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
        
        self.drivers = {}
        
        # Load all valid driver classes from directory
        for filename in os.listdir(self.DRIVER_DIR):
            if filename.endswith('.py'):
                module_name = filename[:-3]
                driver_path = os.path.join(self.DRIVER_DIR, filename)
                spec = importlib.util.spec_from_file_location(module_name, driver_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                for name, driver in inspect.getmembers(module, inspect.isclass):
                    if hasattr(driver, 'device_type'): 
                        self.DEVICE_DRIVERS[driver.device_type] = driver
        
        # I2C config format is just a dict of addresses -> devices
        for address, devices in config.items():
            address = int(address, 0)
            
            for device, subconfig in devices.items():
                try:
                    # Only load device with driver if requested by I2C config
                    if driver := self.DEVICE_DRIVERS.get(device, None):
                        self.devices.append(driver(address = address, i2c_driver = self, config = subconfig, logger = logger))
                    else:
                        logger.error(f"failed to initialize driver for {device}@0x{address:2x} on {ftdi_path}. Compatible driver not found")
                except Exception as e:
                    logger.error(f"failed to initialize {device}@0x{address:2x} on {ftdi_path}: {e.__class__.__name__}: {e}")
    
    def disconnect(self):
        logger.info("shutting down I2C")
        for d in self.devices:
            d.disconnect()
        self.i2c.close()
