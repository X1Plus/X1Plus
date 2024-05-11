#!/opt/python/bin/python3
import os
import copy
from functools import lru_cache
from pathlib import Path
import json
import subprocess

import asyncio

import logging, logging.handlers

from jeepney import (
    HeaderFields,
    new_method_return,
    new_error,
    DBusAddress,
    new_signal,
)
from jeepney.bus_messages import message_bus, MatchRule
from jeepney.io.asyncio import open_dbus_connection, DBusRouter, Proxy

BUS_NAME = "x1plus.x1plusd"

IS_EMULATING = not os.path.exists("/etc/bblap")

logger = logging.getLogger("x1plusd")
logger.setLevel(logging.DEBUG)

slh = logging.handlers.SysLogHandler(address="/dev/log")
slh.setLevel(logging.INFO)
slh.setFormatter(logging.Formatter("%(name)s: %(message)s"))
logger.addHandler(slh)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(logging.Formatter("[%(asctime)s] %(name)s: %(levelname)s: %(message)s"))
logger.addHandler(ch)


class SettingsService:
    DEFAULT_X1PLUS_SETTINGS = {
        "boot.quick_boot": False,
        "boot.dump_emmc": False,
        "boot.sdcard_syslog": False,
        "boot.perf_log": False,
        "ota.enable": False,
    }

    def __init__(self, router):
        self.router = router

        if IS_EMULATING:
            self.settings_dir = "/"
            self.filename = "/tmp/x1plus-settings.json"
        else:
            self.settings_dir = f"/mnt/sdcard/x1plus/printers/{_get_sn()}"
            self.filename = f"{self.settings_dir}/settings.json"
            os.makedirs(self.settings_dir, exist_ok=True)

        # Before we startup, do we have our settings file? Try to read, create if it doesn't exist.
        try:
            with open(self.filename, "r") as fh:
                self.settings = json.load(fh)
        except FileNotFoundError as exc:
            logger.warning("settings file does not exist; creating with defaults...")
            self.settings = self._migrate_old_settings()
            self._save()

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
        signal = new_signal(
            DBusAddress("/", interface="x1plus.settings"),
            "SettingsChanged",
            signature="s",
            body=(json.dumps(self.settings),),
        )
        await self.router.send(signal)

        # probably ought refactor this out into a decorator, but here we are
        SettingsMatch = MatchRule(
            interface="x1plus.settings", path="/x1plus/settings", type="method_call"
        )
        await Proxy(message_bus, self.router).AddMatch(SettingsMatch)
        with self.router.filter(SettingsMatch, bufsize=0) as queue:
            while True:
                msg = await queue.get()
                method = msg.header.fields[HeaderFields.member]

                if msg.header.fields[HeaderFields.signature] != "s":
                    await self.router.send(
                        new_error(msg, "x1plus.x1plusd.Error.BadSignature")
                    )
                    continue

                arg = msg.body[0]

                rv = None
                try:
                    if method == "PutSettings":
                        rv = await self.PutSettings(arg)
                    elif method == "GetSettings":
                        rv = json.dumps(self.settings)
                except Exception as e:
                    logger.error(f"{method}({arg}) -> exception {e}")
                    await self.router.send(
                        new_error(msg, "x1plus.x1plusd.Error.InternalError")
                    )
                    continue

                if not rv:
                    logger.warning(f"{method} -> NoMethod")
                    await self.router.send(
                        new_error(msg, "x1plus.x1plusd.Error.NoMethod")
                    )
                    continue

                logger.debug(f"{method}({arg}) -> {rv}")
                await self.router.send(new_method_return(msg, "s", (rv,)))

    def _save(self):
        # TODO: at some point, copy out the old file to .bak, and try
        # loading the .bak at startup

        with open(self.filename + ".new", "w") as f:
            json.dump(self.settings, f, indent=4)
            f.flush()
            os.fsync(f.fileno())

        os.replace(self.filename + ".new", self.filename)

    async def PutSettings(self, req: str) -> str:
        settings_set = json.loads(req)

        if not isinstance(settings_set, dict):
            logger.error(f"x1p_settings: set request {req} is not a dictionary")
            return json.dumps({"status": "error"})

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

        logger.debug(
            f"x1p_settings: requested {settings_set}, updated {settings_updated}"
        )

        # Inform everyone else on the system, only *after* we have saved
        # and made it visible.  That way, anybody who wants to know
        # about this setting either will have read it from disk
        # initially, or will have heard about the update from us after
        # they read it.
        if len(settings_updated) > 0:
            signal = new_signal(
                DBusAddress("/", interface="x1plus.settings"),
                "SettingsChanged",
                signature="s",
                body=(json.dumps(settings_updated),),
            )
            await self.router.send(signal)

        return json.dumps({"status": "ok", "updated": list(settings_updated.keys())})


# TODO: hoist this into an x1plus package
@lru_cache(None)
def _get_sn():
    """
    Used to get the Serial Number for the Printer
    """
    try:
        return subprocess.check_output(["bbl_3dpsn"], stderr=subprocess.DEVNULL).decode(
            "utf-8"
        )
    except:
        logger.error(
            "_get_sn() failed to run bbl_3dpsn, and we are now dazed and confused. Exiting..."
        )
        raise


def exceptions(loop, ctx):
    logger.error(f"exception in coroutine: {ctx['message']} {ctx.get('exception', '')}")
    loop.default_exception_handler(ctx)


async def main():
    logger.info("x1plusd is starting up")

    asyncio.get_running_loop().set_exception_handler(exceptions)

    if IS_EMULATING:
        # we must be running in emulation
        conn = await open_dbus_connection("SESSION")
    else:
        conn = await open_dbus_connection("SYSTEM")

    router = DBusRouter(conn)

    rv = await Proxy(message_bus, router).RequestName(BUS_NAME)
    if rv != (1,):
        logger.error(f"failed to attach bus name {BUS_NAME}")
        asyncio.get_running_loop().stop()
        return

    try:
        settings = SettingsService(router)
        asyncio.create_task(settings.task())
    except:
        asyncio.get_running_loop().stop()
        raise

    logger.info("x1plusd is running")


if __name__ == "__main__":
    # TODO: check if we are already running
    loop = asyncio.new_event_loop()
    loop.create_task(main())
    try:
        loop.run_forever()
    finally:
        logger.error("x1plusd event loop has terminated!")
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
