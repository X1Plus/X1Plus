# Always invoke this with python3 -m x1plus.services.x1plusd.

import asyncio
import os
import re
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
from .mcproto import MCProtoParser
from .actions import ActionHandler
from .gpios import GpioManager

from x1plus.utils import find_modules, is_emulating

logger = logging.getLogger(__name__)

MODULE_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules"))
MODULE_SDCARD_DIR = "/mnt/sdcard/x1plus/modules" if not is_emulating() else "/tmp/x1plus/modules"

class X1PlusDaemon:

    @classmethod
    async def create(cls):
        # must be a classmethod, since __init__ cannot be async
        self = X1PlusDaemon()

        logger.info("creating x1plusd services")
        
        # Required modules
        self.router = await get_dbus_router()
        self.settings = SettingsService(router=self.router)

        self.mqtt = MQTTClient(daemon=self)
        self.ota = OTAService(daemon=self)
        self.ssh = SSHService(daemon=self)
        self.httpd = HTTPService(daemon=self)
        self.sensors = SensorsService(daemon=self)
        self.mcproto = MCProtoParser(daemon=self)
        self.expansion = ExpansionManager(daemon=self)
        self.gpios = GpioManager(daemon=self)
        self.actions = ActionHandler(daemon=self)
        
        self.modules = []
        self.watched_keys = []

        # find modules on disk...
        self.modules.extend(find_modules(MODULE_BASE_DIR, include_subdirs = True))

        if not os.path.isdir(MODULE_SDCARD_DIR):
            os.makedirs(MODULE_SDCARD_DIR)
        self.modules.extend(find_modules(MODULE_SDCARD_DIR, include_subdirs = True))

        # ... and then load any of them that ought be enabled
        for module in self.modules:
            if module.config_key not in self.watched_keys:
                self.watched_keys.append(module.config_key)

            default_enabled = module.driver_data.get("default_enabled", False)
            if self.settings.get(module.config_key, default_enabled):
                try:
                    logger.info(f"loading x1plusd module {module.package_name}")
                    module.load(daemon=self)
                except Exception as e:
                    logger.error(f"error loading x1plusd module {module.package_name}: {e.__class__.__name__}: {e}")
            else:
                logger.info(f"x1plusd module {module.package_name} (config key {module.config_key}) is available, but not enabled")
        logger.debug(f"watched keys: {self.watched_keys}")

        return self

    async def start(self):
        asyncio.create_task(self.settings.task())

        asyncio.create_task(self.mqtt.task())
        asyncio.create_task(self.ota.task())
        asyncio.create_task(self.httpd.task())
        asyncio.create_task(self.sensors.task())
        asyncio.create_task(self.expansion.task())
        asyncio.create_task(self.mcproto.task())
        asyncio.create_task(self.actions.task())

        for module in self.modules:
            if module.loaded:
                try:
                    module.start()
                except Exception as e:
                    logger.error(f"error starting x1plusd module {module.package_name}: {e.__class__.__name__}: {e}")

        logger.info("x1plusd is running")
