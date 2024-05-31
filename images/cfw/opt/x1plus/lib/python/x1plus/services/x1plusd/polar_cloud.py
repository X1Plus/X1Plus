"""
Module to allow printing using Polar Cloud service.
"""

import os
import subprocess

# from x1plusd.dbus import
import x1plus
from x1plus.utils import get_MAC, get_IP, serial_number, is_emulating

logger = logging.getLogger(__name__)


class PolarPrint:
    def __init__(self, settings):
        self.polar_settings = settings
        if is_emulating:
            # We're using .env for testing, until there's an interface.
            # Don't know if we have dotenv or something similar, so just open
            # the .env file and parse it. This means that .env file must
            # formatted correctly, with vars username, pin, and socketURL.
            with open(".env") as env:
                for line in env:
                    k, v = line.split("=")
                    self.polar_settings[k] = v.strip()
        # self.polar_settings.on("polarprint.enabled", self.sync_startstop())
        self.polar_settings.on("self.pin", self.set_pin())


    def set_pin(self):
        """If PIN is not set, open Polar Cloud interface window and get PIN."""
        pin = self.polar_settings.get("polarprint.pin", None)

        if not pin:
            # Get it from the interface.
            pass


    def set_interface(self):
        """Get IP and MAC addresses and store them in self.settings."""
        self.polar_settings["mac"] = get_MAC()
        self.polar_settings["ip"] = get_IP()


    def get_key(self):
        if "polar_private_key" not in self.polar_settings:
