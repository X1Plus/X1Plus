import logging

import pyftdi.i2c
import binascii

from ..i2c import DEVICE_DRIVERS

logger = logging.getLogger(__name__)

class I2cDriver():
    def __init__(self, daemon, config, expansion, port, port_name):
        self.ftdi_path = f"{expansion.ftdi_path}{port + 1}"
        
        self.i2c_path = f"{port_name}/i2c"

        self.i2c = pyftdi.i2c.I2cController()
        self.i2c.configure(self.ftdi_path, frequency=50000)
        
        self.daemon = daemon
        self.devices = []

        # I2C config format is just a dict of addresses -> devices
        for address, devices in config.items():
            address = int(address, 0)
            
            for device, subconfig in devices.items():
                try:
                    # Only load device with driver if requested by I2C config
                    if driver := DEVICE_DRIVERS.get(device, None):
                        self.devices.append(driver(address = address, i2c_driver = self, config = subconfig))
                    else:
                        logger.error(f"failed to initialize driver for {device}@0x{address:2x} on {self.ftdi_path}. Compatible driver not found")
                except Exception as e:
                    logger.error(f"failed to initialize {device}@0x{address:2x} on {self.ftdi_path}: {e.__class__.__name__}: {e}")

    def disconnect(self):
        logger.info("shutting down I2C")
        for d in self.devices:
            d.disconnect()
        self.i2c.close()
