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

from x1plus.utils import module_loader, module_docstring_parser

logger = logging.getLogger(__name__)

class X1PlusDaemon:

    MODULES = {}    
    """
    MODULES = {
        "name": {
            "definition": {},
            "module_class": Class,
            "path": "",
            "loaded": true/false. If unable to load, deleted from modules
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

        BASE_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
        # Custom module folder could be in x1plus.services.x1plusd.custom, and symlinked to sd card?

        directories = [BASE_MODULE_DIR]

        for filename in os.listdir(BASE_MODULE_DIR):
            full_path = os.path.join(BASE_MODULE_DIR, filename)
            if os.path.isdir(full_path) and not filename.startswith("_"):
                directories.append(full_path)

        self.settings_keys = []

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

                        package = None
                        if BASE_MODULE_DIR in directory:
                            root_package = "x1plus.services.x1plusd"
                            nested_dir = directory.replace(BASE_MODULE_DIR, "").replace("/", ".")
                            if nested_dir: 
                                # One level deep, i.e., 'expansion', 'custom'
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
                        settings_key=settings.path.for.bool, required
                        start_func=function_name, default: task, set as 'null' if it does not have a start function
                        required_modules=module1,module2, default: none.
                        default_state=bool, default: false. Determines its default enabled state when not present in settings
                        [end]
                        """
                        if not module:
                            continue
                        if not hasattr(module, module_data.get("class_name")):
                            logger.warn(f"Could not load {module_name} in x1plusd module loader. Class not found: {module_data.get("class_name")}")
                            continue
                        if not module_data.get("name", None) or not module_data.get("settings_key", None):
                            logger.warn(f"Missing required definitions in x1plusd module spec for {module_name}.")
                            continue

                        self.settings_keys.append(module_data.get("settings_key"))
                        module_class = getattr(module, module_data.get("class_name"))

                        self.MODULES[module_data.get("name")] = {
                            "definition": module_data,
                            "path": file_path,
                            "module_class": module_class,
                            "loaded": False
                        }
                        try: 
                            if module_data.get("start_func", "") == "null" and not module_data.get("required_modules", None):
                                if not module_data.get("settings_key", None) or \
                                   not self.settings.get(module_data.get("settings_key"), 
                                                         module_data.get("default_state", "false").lower().strip() != "false") or \
                                   not callable(module_class):

                                    del self.MODULES[module_data.get("name")]
                                    continue

                                if module_data.get("requires_router", "false") == "false":
                                    setattr(self, module_data.get("name"), module_class(daemon=self))
                                else:
                                    setattr(self, module_data.get("name"), module_class(router=self.router, daemon=self))

                                self.MODULES[module_data.get("name")]["loaded"] = True

                        except Exception as e:
                            logger.error(f"Could not start x1plusd module {module_data.get("name")}. {e.__class__.__name__}: {e}")
                            del self.MODULES[module_data.get("name")]
                except Exception as e:
                    logger.error(f"Error loading x1plusd modules. {e.__class__.__name__}: {e}")

        modules_loaded = False
        max_tries = 20
        tries = 0
        # TODO: Create a priority map order based on requirements instead
        try:
            while not modules_loaded:
                failed_modules = []
                for name, module in self.MODULES.items():
                    if not module.get("definition").get("settings_key", None) or \
                       not self.settings.get(module.get("definition").get("settings_key"), 
                                             module.get("definition").get("default_state", "false").lower().strip() != "false"):
                        failed_modules.append(name)
                        continue
                    if hasattr(self, name) or module.get("loaded"):
                        continue
                    
                    requirements = list(map(str.strip, module.get("definition").get("required_modules", "").lower().split(",")))
                    if len(requirements) == 1 and requirements[0] == "":
                        requirements = []

                    if not requirements or all([hasattr(self, req_module) for req_module in requirements]):
                        module_class = module.get("module_class")
                        if not callable(module_class):
                            failed_modules.append(name)
                            continue
                        try: 

                            if module.get("definition", {}).get("requires_router", "false") == "false":
                                setattr(self, name, module_class(daemon=self))
                            else:
                                setattr(self, name, module_class(router=self.router, daemon=self))

                            module["loaded"] = True

                        except Exception as e:
                            logger.error(f"Could not start x1plusd module {name}. {e.__class__.__name__}: {e}")
                            failed_modules.append(name)
                            continue
                        continue

                    if not all([self.MODULES.get(req_module, None) for req_module in requirements]):
                        logger.error(f"Cannot load x1plusd module {name}. Not all required modules exist. Requires: {requirements}")
                        failed_modules.append(name)
                        continue

                for failed in failed_modules:
                    del self.MODULES[failed]
                failed_modules.clear()

                modules_loaded = all([hasattr(self, name) and module.get("loaded") for name, module in self.MODULES.items()])
                tries += 1

                if tries >= max_tries:
                    logger.warn(f"Could not load all x1plusd modules")
                    failed_modules = []
                    for name, module in self.MODULES.items():
                        if not module.get("loaded", False):
                            failed_modules.append(name)
                    for failed in failed_modules:
                        del self.MODULES[failed]
                    failed_modules.clear()
                    break

        except Exception as e:
            logger.error(f"Error adding x1plusd modules. {e.__class__.__name__}: {e}")

        return self

    async def start(self):
        asyncio.create_task(self.settings.task())
        
        default_start_func = 'task'

        for name, module in self.MODULES.items():
            try: 
                start_func = module.get('definition', {}).get('start_func', default_start_func)
                if start_func != 'null':
                    if not hasattr(getattr(self, name), start_func):
                        logger.warn(f"Could not start task for x1plusd module {name}. Start function not found: {start_func}")
                        continue
                    asyncio.create_task(getattr(getattr(self, name), start_func)())
            except Exception as e:
                logger.error(f"Error starting x1plusd module {name}. {e.__class__.__name__}: {e}")

        logger.info("x1plusd is running")
