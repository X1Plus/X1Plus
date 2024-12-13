"""
[module]
enabled=true
[end]
"""

import os
import re
import logging

import pyftdi.i2c
import binascii

import asyncio
import time

from x1plus.utils import module_loader, module_docstring_parser

logger = logging.getLogger(__name__)

_registered_drivers = {}

class I2cDriver():
    DEVICE_DRIVERS = {}
    
    def __init__(self, daemon, config, ftdi_path, port_name):
        self.ftdi_path = ftdi_path

        self.i2c = pyftdi.i2c.I2cController()
        self.i2c.configure(ftdi_path, frequency=50000)
        
        self.daemon = daemon
        self.devices = []

        for driver in _registered_drivers:
            _registered_drivers[driver](self)

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

def register_driver(name, handler = None):
    """
    Register an i2c driver by name with the expansion i2c subsystem.
    
    If used with handler == None, then behaves like a decorator.
    """
    def decorator(handler):
        assert name not in _registered_drivers
        _registered_drivers[name] = handler
        logger.info(f"Registered I2C Driver from module: {name}")
        return handler

    if handler is None:
        return decorator
    else:
        decorator(handler)

def load(daemon):
    daemon.expansion.DRIVERS["i2c"] = I2cDriver