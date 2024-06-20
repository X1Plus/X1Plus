import os
import copy
from pathlib import Path
import json

import logging
import x1plus.utils
from .dbus import *

logger = logging.getLogger(__name__)

SETTINGS_INTERFACE = "x1plus.settings"
SETTINGS_PATH = "/x1plus/settings"


class SettingsService(X1PlusDBusService):
    """
    Settings manager for all X1Plus configuration.

    The core concept is that SettingsService listens on DBus for requests to
    change settings, and then broadcasts signals when any client on the
    system changes a setting.  Settings are JSON values; the SettingsService
    persists them on disk.

    Known settings keys and values are listed in the wiki page:

      https://github.com/X1Plus/X1Plus/wiki/Developer-Notes:-Configuration-settings

    Never write directly to settings.json while x1plusd is running; x1plusd
    will overwrite your changes!  If you want to modify a setting, use a
    DBus invocation tool (currently, x1plus-test-settings).
    """

    DEFAULT_X1PLUS_SETTINGS = {
        "boot.quick_boot": False,
        "boot.dump_emmc": False,
        "boot.sdcard_syslog": False,
        "boot.perf_log": False,
        "ota.enabled": False,
    }

    def __init__(self, **kwargs):
        if x1plus.utils.is_emulating():
            self.settings_dir = "/"
            self.filename = "/tmp/x1plus-settings.json"
        else:
            self.settings_dir = (
                f"/mnt/sdcard/x1plus/printers/{x1plus.utils.serial_number()}"
            )
            self.filename = f"{self.settings_dir}/settings.json"
            os.makedirs(self.settings_dir, exist_ok=True)

        # Before we startup, do we have our settings file? Try to read, create if it doesn't exist.
        try:
            with open(self.filename, "r") as fh:
                self.settings = json.load(fh)
                logger.debug(f"loaded settings with {len(self.settings)} keys")
        except Exception as e:
            if isinstance(e, FileNotFoundError):
                logger.warning("settings file does not exist; creating with defaults...")
            else:
                bakfile = f"{self.filename}.bad"
                logger.error(f"settings file was unreadable ({e}); moving it to {bakfile} and starting from scratch")
                try:
                    os.replace(self.filename, bakfile)
                except Exception as e:
                    logger.error(f"failed to even move the old file out of the way ({e})!")
            self.settings = self._migrate_old_settings()
            self._save()
        
        self.settings_callbacks = {}

        super().__init__(
            dbus_interface=SETTINGS_INTERFACE, dbus_path=SETTINGS_PATH, **kwargs
        )

    def _migrate_old_settings(self):
        """
        Used to migrate init.d flag files to our new json on first run.
        All bbl_screen settings MUST BE MIGRATED BY bbl_screen!
        """
        defaults = copy.deepcopy(SettingsService.DEFAULT_X1PLUS_SETTINGS)

        # For each flag file name & x1plus settings name, determine setting & cleanup flag file
        for fname, skey in [
            ("quick-boot", "boot.quick_boot"),
            ("dump-emmc", "boot.dump_emmc"),
            ("logsd", "boot.sdcard_syslog"),
            ("perf_log", "boot.perf_log"),
        ]:
            if os.path.exists(f"{self.settings_dir}/{fname}"):
                defaults[skey] = True
                Path(f"{self.settings_dir}/{fname}").unlink(missing_ok=True)

        return defaults

    async def task(self):
        await self.emit_signal("SettingsChanged", self.settings)
        await super().task()

    def _save(self):
        # TODO: at some point, copy out the old file to .bak, and try
        # loading the .bak at startup

        with open(self.filename + ".new", "w") as f:
            json.dump(self.settings, f, indent=4)
            f.flush()
            os.fsync(f.fileno())

        os.replace(self.filename + ".new", self.filename)

    def get(self, *args):
        "For internal consumers in x1plusd, returns the value of a setting."

        return self.settings.get(*args)

    def on(self, setting, fn):
        """
        For internal consumers in x1plusd, receive a synchronous callback
        when an x1plusd setting changes.  If you need to perform an async
        task, then you will need to spawn it with asyncio.create_task().
        """
        
        if setting not in self.settings_callbacks:
            self.settings_callbacks[setting] = []
        self.settings_callbacks[setting].append(fn)

    async def put_multiple(self, settings_set):
        settings_updated = {}
        for k, v in settings_set.items():
            if v is None:
                if k in self.settings:
                    del self.settings[k]
                    settings_updated[k] = v
            else:
                # TODO: this comparison does not make much sense for dicts /
                # arrays, but at least we fail safe
                if k not in self.settings or self.settings[k] != v:
                    self.settings[k] = v
                    settings_updated[k] = v
        self._save()

        # Inform everybody locally inside x1plusd who might want to know
        # that a setting has changed.
        for k in settings_updated.keys():
            for cb in self.settings_callbacks.get(k, []):
                cb()

        # Inform everyone else on the system, only *after* we have saved
        # and made it visible.  That way, anybody who wants to know
        # about this setting either will have read it from disk
        # initially, or will have heard about the update from us after
        # they read it.
        if len(settings_updated) > 0:
            await self.emit_signal("SettingsChanged", settings_updated)
        
        return settings_updated
    
    async def put(self, key, value):
        return await self.put_multiple({key: value})

    async def dbus_GetSettings(self, req):
        return self.settings

    async def dbus_PutSettings(self, settings_set):
        if not isinstance(settings_set, dict):
            logger.error(
                f"x1p_settings: set request {settings_set} is not a dictionary"
            )
            return {"status": "error"}

        settings_updated = await self.put_multiple(settings_set)
        
        logger.debug(
            f"x1p_settings: requested {settings_set}, updated {settings_updated}"
        )

        return {"status": "ok", "updated": list(settings_updated.keys())}
