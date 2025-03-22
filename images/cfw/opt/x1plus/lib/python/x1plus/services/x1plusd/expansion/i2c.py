import logging

import pyftdi.i2c

logger = logging.getLogger(__name__)

DEVICE_DRIVERS = {}

def register_driver(name, clazz = None):
    """
    Register an i2c driver by name with the expansion i2c subsystem.
    
    If used with clazz == None, then behaves like a decorator.
    """
    def decorator(clazz):
        assert name not in DEVICE_DRIVERS
        DEVICE_DRIVERS[name] = clazz
        logger.info(f"registered I2C driver \"{name}\"")
        return clazz

    if clazz is None:
        return decorator
    else:
        decorator(clazz)
