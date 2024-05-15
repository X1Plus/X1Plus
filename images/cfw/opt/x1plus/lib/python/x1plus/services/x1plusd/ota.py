import json
import ssl
import aiohttp
import datetime
import asyncio

import x1plus.utils
from .dbus import *

logger = logging.getLogger(__name__)

OTA_INTERFACE = "x1plus.ota"
OTA_PATH = "/x1plus/ota"

UPDATE_CHECK_SUCCESSFUL_INTERVAL = datetime.timedelta(hours = 24)
UPDATE_CHECK_FAILED_INTERVAL = datetime.timedelta(hours = 4)
DEFAULT_OTA_URL = "https://ota.x1plus.net/stable/ota.json"

# Setup SSL for aiohttp
ssl_ctx = ssl.create_default_context(capath="/etc/ssl/certs")


class OTAService(X1PlusDBusService):
    STATUS_DISABLED = "DISABLED"
    STATUS_IDLE = "IDLE"
    STATUS_CHECKING_OTA = "CHECKING_OTA"
    
    def __init__(self, settings, **kwargs):
        self.x1psettings = settings
        self.ota_url = DEFAULT_OTA_URL
        self.ota_available = False
        self.last_check_timestamp = None
        self.last_check_response = None
        self.last_check_error = False
        self.next_check_timestamp = datetime.datetime.now()
        self.ota_downloaded = False
        self.ota_task_wake = asyncio.Event()
        self.last_status_object = None
        self.task_status = OTAService.STATUS_DISABLED

        try:
            # XXX: check is_emulating
            with open("/opt/x1plus/etc/version.json", "r") as fh:
                self.build_info = json.load(fh)
        except FileNotFoundError:
            logger.warning(
                "OTA engine did not find /opt/x1plus/etc/version.json; setting mock values so we get an OTA to recover!"
            )
            self.build_info = {
                "cfwVersion": "0.1",
                "date": "2024-04-17",
                "buildTimestamp": 1713397465.0,
            }
        
        super().__init__(
            dbus_interface=OTA_INTERFACE, dbus_path=OTA_PATH, **kwargs
        )

    def ota_enabled(self):
        return not not self.x1psettings.get("ota.enabled", False)

    async def task(self):
        # On startup run an update check to populate info
        asyncio.create_task(self._ota_task())
        await super().task()
    
    def _make_status_object(self):
        return {
            "status": self.task_status,
            "enabled": self.ota_enabled(),
            "ota_available": self.ota_available,
            "err_on_last_check": self.last_check_error,
            "last_checked": self.last_check_timestamp,
            "ota_info": self.last_check_response,
            "is_downloaded": self.ota_downloaded,
        }
    
    async def dbus_CheckNow(self, req):
        self.next_check_timestamp = datetime.datetime.now()
        self.ota_task_wake.set()
        return {"status": "ok" if self.ota_enabled() else "disabled"}

    async def dbus_GetStatus(self, req):
        return self._make_status_object()

    async def _maybe_publish_status_object(self):
        "Publish a new _make_status_object as a DBus signal iff something has changed."
        
        status_object = self._make_status_object()
        if status_object != self.last_status_object:
            # equality on a dict is object-equality, not reference-equality
            self.last_status_object = status_object
            await self.emit_signal("StatusChanged", status_object)
            logger.debug(f"ota status changed to {status_object}")

    async def _check_for_ota(self):
        self.task_status = OTAService.STATUS_CHECKING_OTA
        await self._maybe_publish_status_object()

        try:
            # Update check timestamp first
            self.last_check_timestamp = datetime.datetime.now().timestamp()
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as session:
                async with session.get(self.ota_url, timeout=5) as response:
                    response.raise_for_status()
                    self.last_check_response = await response.json()
        except Exception as e:
            logger.error(f"Exception calling OTA URL! {e.__class__.__name__}: \"{e}\"")
            # we Timed out, or hit other error with requests
            self.last_check_error = True
            self.next_check_timestamp = datetime.datetime.now() + UPDATE_CHECK_FAILED_INTERVAL
            return
        finally:
            self.task_status = OTAService.STATUS_IDLE
            # this will get published at the end of the main loop either way

        # Reset error flag at this point, since we ran through correctly
        self.last_check_error = False
        self.next_check_timestamp = datetime.datetime.now() + UPDATE_CHECK_SUCCESSFUL_INTERVAL

        # Now that we have the build info, do our check to see if there's an update
        if self.build_info.get("buildTimestamp", 0) < self.last_check_response.get(
            "buildTimestamp", 0
        ):
            self.ota_available = True

        logger.debug(
            f"Finished running _update_check, results of: {self.last_check_response}"
        )
    
    async def _ota_task(self):
        # Make sure that we are given a chance to see if there is work to do
        # when the OTA status changes.
        self.x1psettings.on("ota.enabled", lambda: self.ota_task_wake.set())
        
        while True:
            did_work = False
            ota_enabled = self.ota_enabled()

            if ota_enabled and datetime.datetime.now() > self.next_check_timestamp:
                await self._check_for_ota()
                did_work = True
            
            # if someone_asked_me_to_download_an_ota:
            #     do it...
            #     and grab the Bambu firmware associated with the ota?...
            #     and clear the someone_asked_me flag...
            #     did_work = True
            #
            # if someone_asked_me_to_reboot_into_the_ota:
            #     do it...

            if not ota_enabled:
                logger.debug(f"OTA engine is disabled, so we are definitely doing nothing")
                self.task_status = OTAService.STATUS_DISABLED
            
            await self._maybe_publish_status_object()
            
            if not did_work:
                # we have nothing to do -- wait until we either have
                # something to do, or until someone wakes us up to tell us
                # that they have given us work by setting the Event.  this
                # requires no mutual exclusion because asyncio is inherently
                # cooperatively multitasked (i.e., we will continue until we
                # yield)
                now = datetime.datetime.now()
                
                next_work = now + datetime.timedelta(days = 365) # really, "forever"
                if ota_enabled:
                    next_work = min((next_work, self.next_check_timestamp,))

                logger.debug(f"going to sleep for {next_work - now}")
                try:
                    await asyncio.wait_for(self.ota_task_wake.wait(), timeout = (next_work - now).total_seconds())
                except asyncio.TimeoutError:
                    pass
                self.ota_task_wake.clear()
