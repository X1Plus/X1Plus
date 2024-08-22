# Always invoke this with python3 -m x1plus.services.x1plusd.

import asyncio
import logging, logging.handlers
import x1plus.utils
from .dbus import *
from .settings import SettingsService
from .ota import OTAService
from .sshd import SSHService
from .httpd import HTTPService
from .mqtt import MQTTClient
from .expansion import ExpansionManager
from .sensors import SensorsService

logger = logging.getLogger(__name__)

class X1PlusDaemon:
    @classmethod
    async def create(cls):
        # must be a classmethod, since __init__ cannot be async
        self = X1PlusDaemon()

        logger.info("creating x1plusd services")
        self.router = await get_dbus_router()
        self.settings = SettingsService(router=self.router)
        self.mqtt = MQTTClient(daemon=self)
        self.ota = OTAService(router=self.router, daemon=self)
        self.ssh = SSHService(daemon=self)
        self.httpd = HTTPService(router=self.router, daemon=self)
        self.sensors = SensorsService(router=self.router, daemon=self)
        self.expansion = ExpansionManager(router=self.router, daemon=self)

        from .polar_cloud import PolarPrintService
        self.polar_cloud = PolarPrintService(router=self.router, daemon=self)
        logger.info("PolarPrintService object created.")

        return self

    async def start(self):
        asyncio.create_task(self.mqtt.task())
        asyncio.create_task(self.settings.task())
        asyncio.create_task(self.ota.task())
        asyncio.create_task(self.httpd.task())
        asyncio.create_task(self.sensors.task())
        asyncio.create_task(self.expansion.task())
        if self.polar_cloud:
            logger.info("Polar has attempted to start.")
            asyncio.create_task(self.polar_cloud.task())
        else:
            logger.info("Polar never attempted to start.")

        logger.info("x1plusd is running")
