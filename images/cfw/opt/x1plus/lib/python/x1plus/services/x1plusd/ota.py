import json
import ssl
import aiohttp
import datetime

import x1plus.utils
from .dbus import *

logger = logging.getLogger(__name__)

OTA_INTERFACE = "x1plus.ota"
OTA_PATH = "/x1plus/ota"

# Setup SSL for aiohttp
ssl_ctx = ssl.create_default_context(capath="/etc/ssl/certs")


class OTAService(X1PlusDBusService):
    def __init__(self, settings, **kwargs):
        self.x1psettings = settings
        self.ota_url = "https://ota.x1plus.net/stable/ota.json"
        self.ota_available = False
        self.last_check_timestamp = None
        self.last_check_response = None
        self.last_check_error = False
        self.ota_downloaded = False

        try:
            # XXX: check is_emulating
            with open("/opt/info.json", "r") as fh:
                self.build_info = json.load(fh)
        except FileNotFoundError:
            logger.warning(
                "OTA engine did not find /opt/info.json, Setting mock values so we get an OTA to recover!"
            )
            self.build_info = {
                "cfwVersion": "0.1",
                "date": "2024-04-17",
                "buildTimestamp": 1713397465.0,
            }
        
        super().__init__(
            dbus_interface=OTA_INTERFACE, dbus_path=OTA_PATH, **kwargs
        )


    async def task(self):
        # On startup run an update check to populate info
        await self._update_check()
        await super().task()
    
    async def dbus_CheckNow(self, req):
        await self._update_check()
        return {"CheckNow": "Triggered"}

    async def dbus_GetStatus(self, req):
        return {
            "ota_available": self.ota_available,
            "err_on_last_check": self.last_check_error,
            "last_checked": self.last_check_timestamp,
            "ota_info": self.last_check_response,
            "is_downloaded": self.ota_downloaded,
        }

    async def _update_check(self):
        # Do we have OTAs enabled? If not, just return current status
        if not self.x1psettings.get("ota.enable", False):
            logger.info("OTA check is disabled, skipping check!")
            return

        # If we are here we want to check, so check
        try:
            # Update check timestamp first
            self.last_check_timestamp = datetime.datetime.now().timestamp()
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as session:
                async with session.get(self.ota_url, timeout=5) as response:
                    self.last_check_response = await response.json()
        except Exception as e:
            logger.error(f"Exception calling OTA URL! Error of: {e}")
            # we Timed out, or hit other error with requests
            self.last_check_error = True
            return

        # Reset error flag at this point, since we ran through correctly
        self.last_check_error = False

        # Now that we have the build info, do our check to see if there's an update
        if self.build_info.get("buildTimestamp", 0) < self.last_check_response.get(
            "buildTimestamp", 0
        ):
            self.ota_available = True

        logger.debug(
            f"Finished running _update_check, results of: {self.last_check_response}"
        )

        return
