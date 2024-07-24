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

async def main():
    logger.info("x1plusd is starting up")

    router = await get_dbus_router()
    settings = SettingsService(router=router)
    mqtt = MQTTClient(settings=settings)
    ota = OTAService(router=router, settings=settings)
    ssh = SSHService(settings=settings)
    httpd = HTTPService(router=router, settings=settings, mqtt=mqtt)
    sensors = SensorsService(router=router, settings=settings)
    expansion = ExpansionManager(settings=settings, sensors=sensors)

    asyncio.create_task(mqtt.task())
    asyncio.create_task(settings.task())
    asyncio.create_task(ota.task())
    asyncio.create_task(httpd.task())
    asyncio.create_task(sensors.task())
    if settings.get("polar_cloud", False):
        from .polar_cloud import PolarPrintService
        polar_cloud = PolarPrintService(settings=settings)
        asyncio.create_task(polar_cloud.begin())

    logger.info("x1plusd is running")
