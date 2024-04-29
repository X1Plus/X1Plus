#!/opt/python/bin/python3
import os
import copy
from functools import lru_cache 
import json
import subprocess
import traceback
import time

import asyncio

import logging, logging.handlers

from jeepney import MessageType, HeaderFields, new_method_return, new_error, DBusAddress, new_signal
from jeepney.bus_messages import message_bus, MatchRule
from jeepney.io.asyncio import open_dbus_connection, DBusRouter, Proxy

BUS_NAME = 'x1plus.x1plusd'

IS_EMULATING = not os.path.exists("/etc/bblap")

logger = logging.getLogger('x1plusd')
logger.setLevel(logging.DEBUG)

slh = logging.handlers.SysLogHandler(address = '/dev/log')
slh.setLevel(logging.INFO)
slh.setFormatter(logging.Formatter('%(name)s: %(message)s'))
logger.addHandler(slh)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(logging.Formatter('[%(asctime)s] %(name)s: %(levelname)s: %(message)s'))
logger.addHandler(ch)

class SettingsService:
    DEFAULT_X1PLUS_SETTINGS = {
        "ota": {
            "enable_check": False
        },
        "quick_boot": False,
        "dump_emmc": False,
        "sdcard_syslog": False
    }

    def __init__(self, router):
        self.router = router

        if IS_EMULATING:
            self.filename = "/tmp/x1plus-settings.json"
        else:
            settings_dir = f"/mnt/sdcard/x1plus/printers/{_get_sn()}"
            self.filename = f"{settings_dir}/settings.json"
            os.makedirs(settings_dir, exist_ok = True)
        
        # Before we startup, do we have our settings file? Try to read, create if it doesn't exist.
        try:
            with open(self.filename, 'r') as fh:
                self.settings = json.load(fh)
        except FileNotFoundError as exc:
            logger.warning('settings file does not exist; creating with defaults...')
            # TODO: Add logic here (call helper function) to check for flag files, 
            # and adjust our defaults to match
            self.settings = copy.deepcopy(SettingsService.DEFAULT_X1PLUS_SETTINGS)
            self._save()
    
    async def task(self):
        signal = new_signal(DBusAddress('/', interface = 'x1plus.settings'), 'SettingsChanged', signature = 's', body = (json.dumps(self.settings), ))
        await self.router.send(signal)

        # probably ought refactor this out into a decorator, but here we are
        SettingsMatch = MatchRule(interface = 'x1plus.settings', path = '/x1plus/settings', type = 'method_call')
        await Proxy(message_bus, self.router).AddMatch(SettingsMatch)
        with self.router.filter(SettingsMatch, bufsize = 0) as queue:
            while True:
                msg = await queue.get()
                method = msg.header.fields[HeaderFields.member]
                
                if msg.header.fields[HeaderFields.signature] != 's':
                    await self.router.send(new_error(msg, "x1plus.x1plusd.Error.BadSignature"))
                    continue
                
                arg = msg.body[0]
                
                rv = None
                try:
                    if method == 'PutSettings':
                        rv = await self.PutSettings(arg) 
                    elif method == 'GetSettings':
                        rv = json.dumps(self.settings)
                except Exception as e:
                    logger.error(f"{method}({arg}) -> exception {e}")
                    await self.router.send(new_error(msg, "x1plus.x1plusd.Error.InternalError"))
                    continue
                
                if not rv:
                    logger.warning(f"{method} -> NoMethod")
                    await self.router.send(new_error(msg, "x1plus.x1plusd.Error.NoMethod"))
                    continue
                
                logger.debug(f"{method}({arg}) -> {rv}")
                await self.router.send(new_method_return(msg, "s", (rv, )))

    def _save(self):
        # XXX: atomically rename this
        
        with open(self.filename, 'w') as f:
            json.dump(self.settings, f, indent = 4)
    
    async def PutSettings(self, req: str) -> str:
        settings_set = json.loads(req)
        
        if not isinstance(settings_set, dict):
            logger.error(f"x1p_settings: set request {req} is not a dictionary")
            return json.dumps({'status': 'error'})
        self.settings.update(settings_set)
        self._save()
        
        logger.debug(f"x1p_settings: updated {settings_set}")
            
        # Inform everyone else on the system, only *after* we have saved
        # and made it visible.  That way, anybody who wants to know
        # about this setting either will have read it from disk
        # initially, or will have heard about the update from us after
        # they read it.
        signal = new_signal(DBusAddress('/', interface = 'x1plus.settings'), 'SettingsChanged', signature = 's', body = (json.dumps(settings_set), ))
        await self.router.send(signal)
        
        return json.dumps({'status': 'ok'})

# TODO: hoist this into an x1plus package
@lru_cache(None)
def _get_sn():
    """
    Used to get the Serial Number for the Printer
    """
    try:
        return subprocess.check_output(["bbl_3dpsn"], stderr=subprocess.DEVNULL).decode('utf-8')
    except:
        logger.error("_get_sn() failed to run bbl_3dpsn, and we are now dazed and confused. Exiting...")
        raise

def exceptions(loop, ctx):
    logger.error(f"exception in coroutine: {ctx['message']} {ctx.get('exception', '')}")
    loop.default_exception_handler(ctx)

async def main():
    logger.info('x1plusd is starting up')
    
    asyncio.get_running_loop().set_exception_handler(exceptions)
    
    if IS_EMULATING:
        # we must be running in emulation
        conn = await open_dbus_connection('SESSION')
    else:
        conn = await open_dbus_connection('SYSTEM')
    
    router = DBusRouter(conn)

    rv = await Proxy(message_bus, router).RequestName(BUS_NAME)
    if rv != (1, ):
        logger.error(f"failed to attach bus name {BUS_NAME}")
        asyncio.get_running_loop().stop()
        return

    try:
        settings = SettingsService(router)
        asyncio.create_task(settings.task())
    except:
        asyncio.get_running_loop().stop()
        raise

    logger.info('x1plusd is running')

if __name__ == "__main__":
    #TODO: check if we are already running
    loop = asyncio.new_event_loop()
    loop.create_task(main())
    try:
        loop.run_forever()
    finally:
        logger.error('x1plusd event loop has terminated!')
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
