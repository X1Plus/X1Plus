import subprocess
from functools import lru_cache
import os
import glob
import re
import sys
import importlib
import logging, logging.handlers
import yaml

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

slh = logging.handlers.SysLogHandler(address="/dev/log")
slh.setLevel(logging.INFO)
slh.setFormatter(logging.Formatter("%(name)s: %(message)s"))
logger.addHandler(slh)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(logging.Formatter("[%(asctime)s] %(name)s: %(levelname)s: %(message)s"))
logger.addHandler(ch)

@lru_cache(None)
def is_emulating():
    return not os.path.exists("/etc/bblap")


@lru_cache(None)
def serial_number():
    """
    Used to get the Serial Number for the Printer
    """
    if is_emulating():
        return "A00000000000"

    return subprocess.check_output(["bbl_3dpsn"], stderr=subprocess.DEVNULL).decode(
        "utf-8"
    )


def get_MAC() -> str:
    """Return the MAC address of the wireless interface."""
    if is_emulating():
        return "CC:BD:D3:00:3B:D5"
    with open(f'/sys/class/net/wlan0/address', 'r') as file:
        mac_address = file.read().strip()
    return mac_address


def get_IP() -> str:
    """Return the IP address of the printer. This is currently on hold."""
    pass
    # if is_emulating():
    #     return "192.168.2.113"
    # hostname = subprocess.run(["hostname", "-I"], capture_output=True)
    # return hostname.stdout.decode().split(" ")[0]

class Module:
    def __init__(self, path, package, loader_type = "module"):
        self.loaded = False
        self.path = path
        self.package_name = package
        self.driver_data = module_docstring_parser(path, loader_type)
        if not self.driver_data:
            raise ImportError("module has no docstring keys")
        self.config_key = f"x1plusd.modules.{self.driver_data.get('name', package)}"
    
    def load(self, *args, **kwargs):
        # XXX: This currently does not load parent packages, and so
        # therefore `from ..  import` and such will not work, and the
        # package name is not a "real" package name in many ways.  Consider
        # doing something that recurs upwards:
        # https://docs.python.org/3/library/importlib.html#approximating-importlib-import-module
        #
        # Or consider registering a path entry hook to sandbox modules,
        # maybe, in the future?  Then we could just use import, or
        # something.
        
        assert not self.loaded
        assert os.path.splitext(os.path.basename(self.path))[0] == self.package_name.split('.')[-1]

        spec = importlib.util.spec_from_file_location(self.package_name, self.path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[self.package_name] = module
        spec.loader.exec_module(module)
        
        if hasattr(module, "load"):
            module.load(*args, **kwargs)
        self.module = module
        self.loaded = True
    
    def start(self):
        if hasattr(self.module, "start"):
            self.module.start()

def find_modules(directory: str, include_subdirs: bool = False, 
                 base_package: str = "x1plus.services.x1plusd.modules",
                 loader_type: str = "module"):
    """Dynamically import all valid modules from a directory"""
    modules = []

    if not os.path.isdir(directory):
        return modules
    
    pattern = f"{directory}/**[!__pycache__]**/[!_]*.py"

    files = glob.glob(pattern, recursive=include_subdirs)
    if include_subdirs:
        pattern2 = f"{directory}/[!_]*.py"
        files.extend(glob.glob(pattern2, recursive=False))

    for file_path in files:
        pkg_extension = file_path.replace(directory, "").replace("/", ".").replace(" ", "_").strip().lower()
        if pkg_extension.startswith("."):
            pkg_extension = pkg_extension[1:]
        if pkg_extension.endswith(".py"):
            pkg_extension = pkg_extension[:-3]

        package = f"{base_package}.{pkg_extension}"

        try:
            modules.append(Module(file_path, package, loader_type = loader_type))
        except ImportError:
            # it just had no docstring keys; that's fine
            pass
        except Exception as e:
            logger.error(f"failed to load module metadata from {file_path}: {e.__class__.__name__}: {e}")
    return modules

    
def module_docstring_parser(filepath: str, loader_type: str) -> dict:
    """Return dict for docstring values matching in a pre-defined block"""
    content = None

    try:
        with open(filepath, 'r') as file:
            content = file.read()
    except Exception as e:
        logger.warn(f"Could not load {filepath} in {loader_type} loader. {e.__class__.__name__}: {e}")
        return None
    
    docstring_match = re.match(r"^([\"']{3})(.*?)\1", content, re.DOTALL)
    if not docstring_match:
        logger.debug(f"No docstring found for {filepath} for {loader_type} loader")
        return None
    
    docstring = docstring_match.group(2).strip()
    definition_block_match = re.search(rf"\[X1PLUS_MODULE_INFO\](.*?)\[END_X1PLUS_MODULE_INFO\]", docstring, re.DOTALL)
    if not definition_block_match:
        logger.debug(f"Could not find module definition in docstring for {filepath} for {loader_type} loader")
        return None

    definition_block = definition_block_match.group(1).strip()
    try:
        contents = yaml.safe_load(definition_block)
    except Exception as e:
        logger.debug(f"module definition in {filepath} was not valid YAML: {e}")
        return None
    
    if type(contents) != dict or loader_type not in contents or type(contents[loader_type]) != dict:
        logger.debug(f"module definition in {filepath} was not dict or did not contain {loader_type} key")
        return None
    
    return contents[loader_type]
