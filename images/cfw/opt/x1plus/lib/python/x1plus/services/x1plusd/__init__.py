# Always invoke this with python3 -m x1plus.services.x1plusd.

import asyncio
import logging, logging.handlers
import x1plus.utils
from .dbus import *
from .settings import SettingsService
from .ota import OTAService
from .sshd import SSHService
from .i2c import I2cService
from .npxl import NpxlService

logger = logging.getLogger(__name__)


async def main():
    logger.info("x1plusd is starting up")

    router = await get_dbus_router()
    settings = SettingsService(router=router)
    ota = OTAService(router=router, settings=settings)
    ssh = SSHService(settings=settings)
    i2c = I2cService(router=router, settings=settings)
    npxl = NpxlService(router=router, settings=settings)

    asyncio.create_task(settings.task())
    asyncio.create_task(ota.task())
    if settings.get("polar_cloud", False):
        from .polar_cloud import PolarPrintService
        polar_cloud = PolarPrintService(settings=settings)
        asyncio.create_task(polar_cloud.begin())
    asyncio.create_task(i2c.task())
    asyncio.create_task(npxl.task())

    logger.info("x1plusd is running")
