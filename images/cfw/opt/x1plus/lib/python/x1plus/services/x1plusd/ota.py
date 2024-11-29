import os
import json
import ssl
import aiohttp
import datetime
import asyncio
import hashlib

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
    STATUS_DOWNLOADING_X1P = "DOWNLOADING_X1P"
    STATUS_DOWNLOADING_BASE = "DOWNLOADING_BASE"
    
    def __init__(self, daemon, **kwargs):
        self.daemon = daemon
        self.ota_url = self.daemon.settings.get('ota.json_url', DEFAULT_OTA_URL)
        self.ota_available = False
        self.last_check_timestamp = None
        self.last_check_response = None
        self.last_check_error = False
        self.next_check_timestamp = datetime.datetime.now()
        self.recheck_files_request = False
        self.download_ota_request = False
        self.download_base_update = False
        self.ota_downloaded = False
        self.base_update_downloaded = False
        self.ota_task_wake = asyncio.Event()
        self.last_status_object = None
        self.task_status = OTAService.STATUS_DISABLED
        self.sdcard_path = "/tmp/x1plus" if x1plus.utils.is_emulating() else "/sdcard"
        self.download_bytes = 0
        self.download_bytes_total = 0
        self.download_last_error = None

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
        return bool(self.daemon.settings.get("ota.enabled", True))

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
            "ota_is_downloaded": self.ota_downloaded,
            "ota_base_is_downloaded": self.base_update_downloaded,
            "download": {
                "bytes": self.download_bytes,
                "bytes_total": self.download_bytes_total,
                "last_error": self.download_last_error,
            },
        }
    
    async def dbus_CheckNow(self, req):
        self.next_check_timestamp = datetime.datetime.now()
        self.ota_task_wake.set()
        return {"status": "ok" if self.ota_enabled() else "disabled"}

    async def dbus_CheckFiles(self, req):
        self.recheck_files_request = True
        self.ota_task_wake.set()
        return {"status": "ok"}

    async def dbus_Download(self, req):
        self.download_ota_request = True
        self.ota_task_wake.set()
        self.download_base_update = bool(req.get('base_firmware', False))
        return {"status": "ok"}
    
    async def dbus_Update(self, req):
        # you're on your own to make sure you're not printing when you call
        # this method!
        if not self.ota_downloaded:
            return {"status": "failure", "reason": "ota not downloaded, doofus"}
        await self.daemon.settings.put('ota.filename', os.path.split(self.last_check_response['ota_url'])[-1])
        if not x1plus.utils.is_emulating():
            os.system("sync; sync; reboot")
            return {"status": "rebooting"}
        else:
            return {"status": "ok"}

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
                    if not isinstance(self.last_check_response, dict):
                        self.last_check_response = None
                        raise ValueError("OTA response was not a dict")
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
        
        # Also, since the last_check_response has changed, blank out that
        # the OTA has been downloaded until we check.
        self.ota_downloaded = False
        self.base_update_downloaded = False

        # Now that we have the build info, do our check to see if there's an update
        if self.build_info.get("buildTimestamp", 0) < self.last_check_response.get(
            "buildTimestamp", 0
        ):
            self.ota_available = True
            self._check_fwfiles()

        # the status diagnostics will give the contents later
        logger.debug("_update_check successfully downloaded ota.json")
    
    def _check_fwfiles(self):
        if not self.last_check_response:
            return

        logger.debug("checking to see if any OTA files are already on disk...")

        if not self.ota_downloaded:
            try:
                ota_url = self.last_check_response['ota_url']
                ota_md5 = self.last_check_response['ota_md5']
                ota_filename = os.path.split(ota_url)[-1]
                ota_on_disk_path = os.path.join(self.sdcard_path, ota_filename)
                accum = hashlib.md5()
                with open(ota_on_disk_path, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        accum.update(chunk)
                disk_md5 = accum.hexdigest()
                logger.debug(f"{ota_on_disk_path} has md5 {disk_md5}, want md5 {ota_md5}")
                self.ota_downloaded = ota_md5 == disk_md5
            except FileNotFoundError as e:
                logger.debug(f"{e}")
                pass
            except Exception as e:
                logger.error(f"exception while checking OTA file: {e.__class__.__name__}: \"{e}\"")

        if not self.base_update_downloaded:
            try:
                base_update_url = self.last_check_response['base_update_url']
                base_update_md5 = self.last_check_response['base_update_md5']
                base_update_filename = os.path.split(base_update_url)[-1]
                base_update_on_disk_path = os.path.join(self.sdcard_path, "x1plus", "firmware", base_update_filename)
                accum = hashlib.md5()
                with open(base_update_on_disk_path, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        accum.update(chunk)
                disk_md5 = accum.hexdigest()
                logger.debug(f"{base_update_on_disk_path} has md5 {disk_md5}, want md5 {base_update_md5}")
                self.base_update_downloaded = base_update_md5 == disk_md5
            except FileNotFoundError as e:
                logger.debug(f"{e}")
                pass
            except Exception as e:
                logger.error(f"exception while checking base update file: {e.__class__.__name__}: \"{e}\"")

    # can throw!  handle it yourself!
    async def _download_file(self, url, dest, md5):
        try:
            logger.debug(f"downloading {url} to {dest}")
            accum = hashlib.md5()
            self.download_bytes = 0
            self.download_bytes_total = -1
            with open(dest, 'wb') as f:
                # Total timeout of 15 minutes per request means you need to
                # sustain 100 kB/s from Bambu on a 90MB update.zip before we
                # time out.
                timeout = aiohttp.ClientTimeout(connect=5, total=900, sock_read=10)
                async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx), timeout=timeout) as session:
                    async with session.get(url) as response:
                        response.raise_for_status()
                        self.download_bytes_total = int(response.headers['content-length'])
                        self.download_bytes = 0
                        last_publish = datetime.datetime.now()
                        async for chunk in response.content.iter_chunked(131072):
                            self.download_bytes += len(chunk)
                            accum.update(chunk)
                            f.write(chunk)
                            
                            # only make noise at 5Hz
                            if (datetime.datetime.now() - last_publish) > datetime.timedelta(seconds = 0.2):
                                last_publish = datetime.datetime.now()
                                await self._maybe_publish_status_object()
                        await self._maybe_publish_status_object()
            disk_md5 = accum.hexdigest()
            logger.debug(f"{dest} has md5 {disk_md5}, want md5 {md5}")
            if disk_md5 != md5:
                raise ValueError("downloaded file had incorrect md5")
        except:
            try:
                os.unlink(dest)
            except:
                pass
            raise
    
    def _ota_url_changed(self):
        new_url = self.daemon.settings.get('ota.json_url', DEFAULT_OTA_URL)
        if self.ota_url != new_url:
            logger.debug("OTA URL has changed, triggering recheck")
        self.ota_url = new_url
        self.next_check_timestamp = datetime.datetime.now()
        self.ota_task_wake.set()
    
    async def _ota_task(self):
        # Make sure that we are given a chance to see if there is work to do
        # when the OTA status changes.
        self.daemon.settings.on("ota.enabled", lambda: self.ota_task_wake.set())
        self.daemon.settings.on("ota.json_url", lambda: self._ota_url_changed())
        
        while True:
            did_work = False
            ota_enabled = self.ota_enabled()

            if ota_enabled and datetime.datetime.now() > self.next_check_timestamp:
                await self._check_for_ota()
                did_work = True
            
            if self.recheck_files_request or self.download_ota_request:
                self._check_fwfiles()
                self.recheck_files_request = False
                did_work = True
            
            if ota_enabled and self.download_ota_request:
                self.download_last_error = None
                if not self.ota_downloaded:
                    self.task_status = OTAService.STATUS_DOWNLOADING_X1P
                    try:
                        ota_url = self.last_check_response['ota_url']
                        ota_md5 = self.last_check_response['ota_md5']
                        ota_filename = os.path.split(ota_url)[-1]
                        ota_on_disk_path = os.path.join(self.sdcard_path, ota_filename)
                        await self._download_file(ota_url, ota_on_disk_path, ota_md5)
                        self.ota_downloaded = True
                    except Exception as e:
                        self.download_last_error = f"exception while downloading OTA: {e.__class__.__name__}: \"{e}\""
                        logger.debug(self.download_last_error)
                    self.task_status = OTAService.STATUS_IDLE
                
                if not self.base_update_downloaded and self.download_base_update:
                    self.task_status = OTAService.STATUS_DOWNLOADING_BASE
                    try:
                        base_update_url = self.last_check_response['base_update_url']
                        base_update_md5 = self.last_check_response['base_update_md5']
                        base_update_filename = os.path.split(base_update_url)[-1]
                        base_update_on_disk_path = os.path.join(self.sdcard_path, "x1plus", "firmware", base_update_filename)
                        await self._download_file(base_update_url, base_update_on_disk_path, base_update_md5)
                        self.base_update_downloaded = True
                    except Exception as e:
                        self.download_last_error = f"exception while downloading base firmware: {e.__class__.__name__}: \"{e}\""
                        logger.debug(self.download_last_error)
                    self.task_status = OTAService.STATUS_IDLE
                self.download_ota_request = False
                did_work = True
            
            if not ota_enabled:
                logger.debug(f"OTA engine is disabled, so we are definitely doing nothing")
                self.task_status = OTAService.STATUS_DISABLED
            else:
                self.task_status = OTAService.STATUS_IDLE
            
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
