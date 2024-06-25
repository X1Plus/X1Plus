# Always invoke this with python3 -m x1plus.services.x1plusd.

import asyncio
import logging, logging.handlers
import x1plus.utils
from .dbus import *
from .settings import SettingsService
from .ota import OTAService
from .sshd import SSHService
from .mqtt import MQTTService

logger = logging.getLogger(__name__)


async def main():
    logger.info("x1plusd is starting up")

    router = await get_dbus_router()
    settings = SettingsService(router=router)
    ota = OTAService(router=router, settings=settings)
    ssh = SSHService(settings=settings)
    mqtt = MQTTService(router=router)

    asyncio.create_task(settings.task())
    asyncio.create_task(ota.task())
    asyncio.create_task(mqtt.task())

    logger.info("x1plusd is running")
