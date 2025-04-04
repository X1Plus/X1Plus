import logging

from ..i2c import DEVICE_DRIVERS

logger = logging.getLogger(__name__)

class I2cDriver():
    def __init__(self, daemon, config, expansion, port, port_name):
        self.daemon = daemon
        self.config = config
        self.expansion = expansion
        self.port = port

        self.i2c = _I2cController(self.expansion, self.port)
        
        self.i2c_path = f"{port_name}/i2c"
        
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
                        logger.error(f"failed to initialize driver for {device}@0x{address:2x} on {port_name}. Compatible driver not found")
                except Exception as e:
                    logger.error(f"failed to initialize {device}@0x{address:2x} on {port_name}: {e.__class__.__name__}: {e}")

    def disconnect(self):
        logger.info("shutting down I2C")
        for d in self.devices:
            d.disconnect()

class _I2cController():
    # "sort of" behaves like a pyftdi.i2c.I2cController
    def __init__(self, expansion, port):
        self.expansion = expansion
        self.port = port
    
    def write(self, addr, out):
        self.expansion._i2c_write(scl = self.expansion.PORTS[self.port][0], sda = self.expansion.PORTS[self.port][1], addr = addr, data = bytes(out))
    
    def read(self, addr, readlen = 0):
        return self.expansion._i2c_read(scl = self.expansion.PORTS[self.port][0], sda = self.expansion.PORTS[self.port][1], addr = addr, dlen = readlen)
    
    def get_port(self, addr):
        return _I2cPort(self, addr)

class _I2cPort():
    # "sort of" behaves like a pyftdi.i2c.I2cPort
    def __init__(self, controller, addr):
        self.controller = controller
        self.addr = addr
    
    def write(self, *args, **kwargs):
        return self.controller.write(self.addr, *args, **kwargs)
    
    def read(self, *args, **kwargs):
        return self.controller.read(self.addr, *args, **kwargs)
