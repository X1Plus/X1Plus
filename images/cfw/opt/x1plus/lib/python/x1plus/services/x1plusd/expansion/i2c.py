import os
import re
import logging
import importlib

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

        # Load all valid driver classes from directory
        for filename in os.listdir(self.DRIVER_DIR):
            if filename.endswith(".py") and not filename.startswith("_"):
                module_name = filename[:-3]
                driver_path = os.path.join(self.DRIVER_DIR, filename)

                driver_data = self.driver_parser(driver_path)
                if not driver_data or not driver_data.get("class_name", None) or not driver_data.get("device_type", None):
                    continue

                package = "x1plus.services.x1plusd.expansion.i2c_drivers"

                module, module_name = self.load_module(driver_path, package)
                if not hasattr(module, driver_data.get("class_name")):
                    logger.warn(f"Could not load {module_name} in i2c driver loader. Class not found: {driver_data.get("class_name")}")
                    continue

                driver_class = getattr(module, driver_data.get("class_name"))
                self.DEVICE_DRIVERS[driver_data.get("device_type")] = driver_class
        
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

    
    def load_module(self, file_path, package_name):
        module_name = os.path.splitext(os.path.basename(file_path))[0]
        module = importlib.import_module(f"{package_name}.{module_name}")
        return module, module_name


    def driver_parser(self, filepath: str) -> dict:
        content = None
        config = {}
        try:
            with open(filepath, 'r') as file:
                content = file.read()
        except Exception as e:
            logger.warn(f"Could not load {filepath} in i2c driver loader. {e.__class__.__name__}: {e}")
            return config
        
        docstring_match = re.match(r"^([\"']{3})(.*?)\1", content, re.DOTALL)
        if not docstring_match:
            logger.debug(f"No docstring found for {filepath} for i2c driver loader")
            return config
        
        docstring = docstring_match.group(2).strip()
        definition_block_match = re.search(r"\[i2c-driver\](.*?)\[end\]", docstring, re.DOTALL)
        if not definition_block_match:
            logger.info(f"Could not find driver definition in docstring for {filepath} for i2c driver loader")
            return config

        definition_block = definition_block_match.group(1).strip()
        for line in definition_block.splitlines():
            if "=" in line:
                key, val = map(str.strip, line.split("=", 1))
                config[key] = val
        return config
  
