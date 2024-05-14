# Always invoke this with python3 -m x1plus.services.x1plusd.

import asyncio
import logging, logging.handlers
import x1plus.utils
from .dbus import *
from .settings import SettingsService

logger = logging.getLogger(__name__)


async def main():
    logger.info("x1plusd is starting up")

    router = await get_dbus_router()
    settings = SettingsService(router=router)

    asyncio.create_task(settings.task())

    logger.info("x1plusd is running")
