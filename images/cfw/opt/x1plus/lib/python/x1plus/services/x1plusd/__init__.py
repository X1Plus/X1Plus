# Always invoke this with python3 -m x1plus.services.x1plusd.

import asyncio
import os
import sys
import re
import importlib
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

from x1plus.utils import module_loader, module_docstring_parser

logger = logging.getLogger(__name__)

class X1PlusDaemon:

    MODULES = {}    
    """
    MODULES = {
        "name": {
            "definition": {},
            "module_class": Class,
            "loaded": true/false. False if error loading.
        }
    } 
    """


    @classmethod
    async def create(cls):
        # must be a classmethod, since __init__ cannot be async
        self = X1PlusDaemon()

        logger.info("creating x1plusd services")
        
        # Required modules
        self.router = await get_dbus_router()
        self.settings = SettingsService(router=self.router)

        self.mqtt = MQTTClient(daemon=self)
        self.ota = OTAService(router=self.router, daemon=self)
        self.ssh = SSHService(daemon=self)
        self.httpd = HTTPService(router=self.router, daemon=self)
        self.sensors = SensorsService(router=self.router, daemon=self)
        self.mcproto = MCProtoParser(daemon=self)
        self.expansion = ExpansionManager(router=self.router, daemon=self)
        self.gpios = GpioManager(daemon=self)
        self.actions = ActionHandler(router=self.router, daemon=self)
        
        self.custom_modules = {}
        """
        { "name": ClassInstance }
        """

        self.settings_keys = []

        BASE_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
        # Custom module folder could be in x1plus.services.x1plusd.custom, and symlinked to sd card?

        directories = [BASE_MODULE_DIR]

        for filename in os.listdir(BASE_MODULE_DIR):
            full_path = os.path.join(BASE_MODULE_DIR, filename)
            if os.path.isdir(full_path) and not filename.startswith("_"):
                directories.append(full_path)

        for directory in directories:
            if not os.path.isdir(directory):
                continue
            for filename in os.listdir(directory):
                try: 
                    file_path = os.path.join(directory, filename)
                    if not os.path.isfile(file_path):
                        continue

                    if filename.endswith(".py") and not filename.startswith("_"):
                        module_data = module_docstring_parser(file_path, "x1plusd-module")
                        if not module_data or not module_data.get("class_name", None):
                            continue
                        if not module_data.get("name", None):
                            logger.warn(f"Missing required definitions in x1plusd module spec for {module_name}.")
                            continue

                        package = None
                        if BASE_MODULE_DIR in directory:
                            root_package = "x1plus.services.x1plusd"
                            nested_dir = directory.replace(BASE_MODULE_DIR, "").replace("/", ".")
                            if nested_dir: 
                                # One level deep, i.e., 'custom'
                                root_package = ".".join([root_package, nested_dir])
                                root_package = root_package.replace("..", ".")
                            package = root_package
                        if not package:
                            continue

                        module, module_name = module_loader(file_path, package)

                        """
                        [x1plusd-module]
                        name=name, required
                        class_name=ClassName, required
                        requires_router=bool, default: false
                        start_func=function_name, default: task, set as 'null' if it does not have a start function
                        [end]
                        """

                        if not module:
                            continue
                        if not hasattr(module, module_data.get("class_name")):
                            logger.warn(f"Could not load {module_name} in x1plusd module loader. Class not found: {module_data.get("class_name")}")
                            continue

                        self.settings_keys.append(f"x1plusd.modules.{module_data.get("name")}")
                        if not self.settings.get(f"x1plusd.modules.{module_data.get("name")}", False):
                            # Module found, but disabled in settings. Do not load, but added to restart listener above
                            continue

                        module_class = getattr(module, module_data.get("class_name"))
                        # Disabled modules will not get added at all currently
                        self.MODULES[module_data.get("name")] = {
                            "definition": module_data,
                            "module_class": module_class,
                            "loaded": False
                        }

                        try: 
                            if module_data.get("start_func", "") == "null":
                                if not callable(module_class):
                                    continue

                                if module_data.get("requires_router", "false").lower() == "false":
                                    self.custom_modules[module_data.get("name")] = module_class(daemon=self)
                                else:
                                    self.custom_modules[module_data.get("name")] = module_class(router=self.router, daemon=self)

                                self.MODULES[module_data.get("name")]["loaded"] = True

                        except Exception as e:
                            logger.error(f"Could not start x1plusd module {module_data.get("name")}. {e.__class__.__name__}: {e}")
                except Exception as e:
                    logger.error(f"Error loading x1plusd modules. {e.__class__.__name__}: {e}")

        modules_loaded = False
        try:

            for name, module in self.MODULES.items():
                if module.get("loaded") or self.custom_modules.get(name, None):
                    continue
                
                module_class = module.get("module_class")
                if not callable(module_class):
                    continue
                try: 

                    if module.get("definition", {}).get("requires_router", "false").lower() == "false":
                        self.custom_modules[name] = module_class(daemon=self)
                    else:
                        self.custom_modules[name] = module_class(router=self.router, daemon=self)

                    module["loaded"] = True

                except Exception as e:
                    logger.error(f"Could not start x1plusd module {name}. {e.__class__.__name__}: {e}")
                    continue
                continue

        except Exception as e:
            logger.error(f"Error adding x1plusd modules. {e.__class__.__name__}: {e}")

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
        
        default_start_func = 'task'

        for name, module in self.MODULES.items():
            if not module.get("loaded", False):
                continue

            try: 
                start_func = module.get('definition', {}).get('start_func', default_start_func)
                if start_func != 'null':
                    if not self.custom_modules.get(name, None) or not hasattr(self.custom_modules.get(name), start_func):
                        logger.warn(f"Could not start task for x1plusd module {name}. Start function not found: {start_func}")
                        continue
                    asyncio.create_task(getattr(self.custom_modules.get(name), start_func)())
            except Exception as e:
                logger.error(f"Error starting x1plusd module {name}. {e.__class__.__name__}: {e}")

        logger.info("x1plusd is running")
