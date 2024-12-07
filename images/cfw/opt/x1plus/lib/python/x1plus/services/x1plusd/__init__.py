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

from x1plus.utils import module_importer

logger = logging.getLogger(__name__)

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
        
        self.custom_modules = {}
        """
        { "name": ClassInstance }
        """

        self.watched_keys = []
        self.MODULES = []

        BASE_MODULE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules"))
        self.load_modules(BASE_MODULE_DIR)

        SDCARD_MODULE_DIR = "/mnt/sdcard/x1plus/modules"
        if not os.path.isdir(SDCARD_MODULE_DIR):
            os.makedirs(SDCARD_MODULE_DIR)

        # Custom modules are loaded after all core modules
        # Full import paths will work if a dependency exists
        self.load_modules(SDCARD_MODULE_DIR)

        return self

    def load_modules(self, module_directory: str):
        self.MODULES.extend(module_importer(module_directory, include_subdirs=True))

        for scanned_module in self.MODULES:
            key = scanned_module.get('key')
            module = scanned_module.get('module', None)
            
            if key not in self.watched_keys:
                self.watched_keys.append(key)

            enabled = scanned_module.get("config", {}).get("enabled", "").lower() == "true"
            if module and self.settings.get(key, enabled) and hasattr(module, "load"):
                name = scanned_module.get("name")
                try:
                    module.load(daemon=self)
                except Exception as e:
                    logger.error(f"Error loading x1plusd module {name}. {e.__class__.__name__}: {e}")



    async def start(self):
        asyncio.create_task(self.settings.task())

        asyncio.create_task(self.mqtt.task())
        asyncio.create_task(self.ota.task())
        asyncio.create_task(self.httpd.task())
        asyncio.create_task(self.sensors.task())
        asyncio.create_task(self.expansion.task())
        asyncio.create_task(self.mcproto.task())
        asyncio.create_task(self.actions.task())

        for scanned_module in self.MODULES:
            key = scanned_module.get('key')
            module = scanned_module.get('module', None)
            enabled = scanned_module.get("config", {}).get("enabled", "").lower() == "true"
            if module and self.settings.get(key, enabled) and hasattr(module, "start"):
                name = scanned_module.get("name")
                try:
                    module.start(daemon=self)
                except Exception as e:
                    logger.error(f"Error starting x1plusd module {name}. {e.__class__.__name__}: {e}")

        logger.info("x1plusd is running")
