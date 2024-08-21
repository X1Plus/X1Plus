import logging
import asyncio
import time

import x1plus.utils
from .dbus import *

logger = logging.getLogger(__name__)

SENSORS_INTERFACE = "x1plus.sensors"
SENSORS_PATH = "/x1plus/sensors"
SENSOR_TIMEOUT = 60

class SensorsService(X1PlusDBusService):
    def __init__(self, daemon, **kwargs):
        self.daemon = daemon
        self.sensors = {}
        super().__init__(
            dbus_interface=SENSORS_INTERFACE, dbus_path=SENSORS_PATH, **kwargs
        )

    async def dbus_GetSensors(self, arg):
        now = time.time()
        for name in list(self.sensors.keys()):
            if (now - self.sensors[name]['timestamp']) > SENSOR_TIMEOUT:
                logger.info(f"sensor {name} has not been heard from in quite a while; removing it")
                del self.sensors[name]
        return self.sensors
    
    async def publish(self, name, **data):
        data['timestamp'] = time.time()
        if name not in self.sensors:
            logger.info(f"sensor {name} has come online with data {data}")
        self.sensors[name] = data

        await self.emit_signal("SensorUpdate", { name: data })
        
        # use the "synthesize_report" mechanism in mqtt_reroute.cpp to make
        # device_gate publish both to the local mqtt broker and to the cloud
        await self.daemon.mqtt.publish_request({ "x1plus": { "synthesize_report": { "x1plus": { "sensor": { name: data } } } } })
