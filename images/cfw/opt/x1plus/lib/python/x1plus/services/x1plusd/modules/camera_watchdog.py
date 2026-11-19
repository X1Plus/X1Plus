"""
Kicks ipcam when it misbehaves and brings it back online

ipcam can stop serving RTSP, freeze, or lose the camera after a brief USB
disconnect. In the last case it never closes the old /dev/video20, so the kernel
gives the returning camera the next free number (video21). ipcam never notices,
and the "camera disconnected" error stays until a manual reboot. We restart ipcam, which
frees video20, then rebind the camera so it comes back as video20 and the new
ipcam picks it up.

Everything is driven by ipcam's heartbeat on device/inter/report/ipcam. The port
322 probe and RTSP restore only run when the user has RTSP enabled. After a
restart we clear the camera HMS codes the old ipcam left behind.

Works in cloud, LAN, and Shield modes

Settings:
  camera.watchdog.interval - int, port 322 probe interval in seconds (default: 60)

[X1PLUS_MODULE_INFO]
module:
  name: camera_watchdog
  default_enabled: true
[END_X1PLUS_MODULE_INFO]
"""

import asyncio
import json
import logging
import os
import signal
import ssl
import subprocess
import threading
import time

import x1plus.dds

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL      = 60
PROBE_TIMEOUT         = 10
IPCAM_PORT            = 322
IPCAM_INIT            = "/etc/init.d/S99ipcam_service"
IPCAM_PIDFILE         = "/var/run/ipcam.pid"
ACCESS_TOKEN          = "/config/device/access_token"
PRINTER_JSON          = "/config/screen/printer.json"

WATCH_INTERVAL        = 2

# ipcams heartbeat comes every 2s. Anything older isnt trusted.
REPORT_MAX_AGE        = 10
HEARTBEAT_TIMEOUT     = 30

RESTART_READY_TIMEOUT = 60
STOP_KILL_TIMEOUT     = 5
RESTART_GIVE_UP_TIME  = 600

RTSP_INIT_ATTEMPTS    = 3
RTSP_INIT_TIMEOUT     = 10
# ipcam needs a moment after the camera comes back before an rtsp toggle will work, if not it throws an
# hms code (at least for me it does.)
RTSP_RESTORE_DELAY    = 3

CAMERA_GONE_TIMEOUT   = 10
CAMERA_RETURN_TIMEOUT = 20
USB_DRIVER            = "/sys/bus/usb/drivers/usb"

# The camera hms codes ipcam causes, ipcam should clear them itself
# when the camera comes back but if we kill it nothing does,
# so we clear them when we restart it.
HMS_CAMERA_ATTR       = 0x05000100
HMS_CAMERA_CODES      = (0x00020001, 0x00020002, 0x00020003)


# True if rtsp is turned on in the LAN access settings
def _rtsp_wanted():
    try:
        with open(PRINTER_JSON) as f:
            return json.load(f).get("rtspServer") is True
    except (OSError, ValueError):
        return False


def _ipcam_pid():
    # the pidfile can be stale and point at some other process that got the same number,
    # so make sure its actually ipcam before we kill anything
    try:
        with open(IPCAM_PIDFILE) as f:
            pid = int(f.read())
        with open(f"/proc/{pid}/comm") as f:
            return pid if f.read().strip() == "ipcam" else None
    except (OSError, ValueError):
        return None


# True if ipcam is still holding a deleted /dev/video node, means its lost the camera.
def _ipcam_holds_deleted_video():
    pid = _ipcam_pid()
    try:
        fds = os.listdir(f"/proc/{pid}/fd")
    except OSError:
        return False
    for fd in fds:
        try:
            target = os.readlink(f"/proc/{pid}/fd/{fd}")
        except OSError:
            continue
        if target.startswith("/dev/video") and target.endswith("(deleted)"):
            return True
    return False


# The camera's USB device: 1-1.5 behind the Expanders hub, should be 1-1 on a bare printer.
def _usb_camera():
    base = "/sys/class/video4linux"
    try:
        nodes = sorted(os.listdir(base))
    except OSError:
        return None
    for node in nodes:
        # .../1-1/1-1.5/1-1.5:1.0 -> 1-1.5
        interface = os.path.realpath(f"{base}/{node}/device")
        if "/usb" not in interface or ":" not in os.path.basename(interface):
            continue
        return os.path.basename(os.path.dirname(interface))
    return None


def _rebind_usb_device(device):
    if os.path.exists(f"{USB_DRIVER}/{device}"):
        with open(f"{USB_DRIVER}/unbind", "w") as f:
            f.write(device)
        time.sleep(1)
    with open(f"{USB_DRIVER}/bind", "w") as f:
        f.write(device)


class CameraWatchdog:
    def __init__(self, daemon):
        self.daemon = daemon
        # (time received, ipcam report), set from the heartbeat thread.
        self.report = (time.monotonic(), {})

        self.last_restart = None  # Only restarts for a hang count toward giving up.
        self.gave_up = False
        self.ipcam = (None, time.monotonic())  # (pid, first seen)

        self.camera_was_present = None
        self.camera_device = None
        self.camera_off_usb = False
        self.camera_handled = False
        self.restore_failed = False
        self.rtsp_off_since = None
        self.camera_gone_since = None

        self.lock = asyncio.Lock()

        self._liveview_pub = x1plus.dds.publisher("device/request/liveview")
        self._hms_pub = x1plus.dds.publisher("device/inter/report/hms")
        heartbeats = x1plus.dds.subscribe("device/inter/report/ipcam")
        threading.Thread(target=self._read_heartbeats, args=(heartbeats,), daemon=True).start()

    def _read_heartbeats(self, q):
        while True:
            msg = q.get()
            try:
                self.report = (time.monotonic(), json.loads(msg)["ipcam"]["ipcam"])
            except Exception as e:
                logger.warning(f"could not handle DDS message {msg!r}: {e}")

    def _ipcam_report(self):
        received, ipcam = self.report
        return ipcam if time.monotonic() - received <= REPORT_MAX_AGE else None

    def _camera_present(self):
        ipcam = self._ipcam_report() or {}
        return {"1": True, "0": False}.get(ipcam.get("ipcam_dev"))

    def _rtsp_on(self):
        url = (self._ipcam_report() or {}).get("rtsp_url")
        return None if url is None else url != "disable"

    async def _wait_for(self, pred, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if pred():
                return True
            await asyncio.sleep(0.5)
        return pred()

    async def _restart_ipcam(self):
        """
        Stop ipcam and wait for service_check to start a new one.
        if ipcam is still around after STOP_KILL_TIMEOUT
        we kill it. Then we wait for a heartbeat from the new ipcam.
        """
        logger.warning("restarting ipcam")
        # only stop it if its actually running, the init script just signals whatever
        # pid is in the pidfile without checking
        pid = _ipcam_pid()
        if pid:
            result = await asyncio.to_thread(subprocess.run, [IPCAM_INIT, "stop"], capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"ipcam stop returned {result.returncode}: {result.stderr.strip()}")
                return

            # stop only sends SIGTERM which a hung ipcam can ignore, and service_check
            # wont start a new one till the old one is gone.
            if not await self._wait_for(lambda: _ipcam_pid() != pid, STOP_KILL_TIMEOUT):
                logger.warning(f"ipcam (pid {pid}) ignored SIGTERM, killing it")
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

        # old ipcam is dead so nothing is going to clear the hms codes it raised, anything
        # the new one raises after this is legit
        for code in HMS_CAMERA_CODES:
            self._hms_pub(json.dumps({"attr": HMS_CAMERA_ATTR, "code": code, "ctrl": 0}))
        logger.info("cleared the camera HMS codes the old ipcam left behind")

        # A heartbeat after this can only be from the new ipcam.
        stopped = time.monotonic()
        if await self._wait_for(lambda: self.report[0] > stopped, RESTART_READY_TIMEOUT):
            logger.info(f"ipcam is back after {time.monotonic() - stopped:.1f}s")
        else:
            logger.error(f"ipcam did not come back within {RESTART_READY_TIMEOUT}s")

    async def _restart_hung_ipcam(self, why):
        """
        Restart ipcam if its hung, unless restarting it isnt helping

        If it needs another restart within RESTART_GIVE_UP_TIME we stop trying and leave it
        alone until the probe sees its healthy again.
        """
        if self.gave_up:
            return
        if self.last_restart is not None and time.monotonic() - self.last_restart < RESTART_GIVE_UP_TIME:
            logger.error(f"ipcam {why} again within {RESTART_GIVE_UP_TIME}s of a restart, "
                         "leaving it alone until it recovers")
            self.gave_up = True
            return
        logger.warning(f"ipcam {why}")
        self.last_restart = time.monotonic()
        await self._restart_ipcam()

    async def _recover_camera(self):
        # Takes the lock itself.
        device = self.camera_device
        async with self.lock:
            if self._camera_present():
                return True
            if _ipcam_holds_deleted_video():
                logger.warning("ipcam is holding the camera's old video device")
                await self._restart_ipcam()
            logger.warning(f"re-binding USB device {device}")
            try:
                await asyncio.to_thread(_rebind_usb_device, device)
            except Exception as e:
                logger.error(f"could not re-bind USB device {device}: {e}")
                return False
            return await self._wait_for(self._camera_present, CAMERA_RETURN_TIMEOUT)

    async def _restore_rtsp(self):
        try:
            with open(ACCESS_TOKEN) as f:
                passwd = f.read().strip()
        except OSError as e:
            logger.error(f"could not read {ACCESS_TOKEN}: {e}")
            return False
        for attempt in range(1, RTSP_INIT_ATTEMPTS + 1):
            await self._send_liveview_init(passwd)
            if await self._wait_for(lambda: self._rtsp_on() or not _rtsp_wanted(), RTSP_INIT_TIMEOUT):
                if self._rtsp_on():
                    logger.info(f"RTSP server is on again (attempt {attempt})")
                return True
        logger.error("RTSP server did not come back on -- toggle it in LAN access settings")
        return False

    async def _send_liveview_init(self, passwd):
        # The same start/stop that bbl_screen sends. The retries in _restore_rtsp
        # cover a freshly started ipcam missing the first one.
        def send(seq, op):
            self._liveview_pub(json.dumps({"command": "liveview", "op_protocols": [op],
                                           "peer_host": "x1plusd", "sequence_id": seq, "version": 1}))

        send("1", {"command": "deinit", "type": "rtsp"})
        await asyncio.sleep(1)
        if _rtsp_wanted():  # The user may have just turned it off.
            send("2", {"command": "init", "type": "rtsp", "media_port": IPCAM_PORT, "server_use_tls": 1,
                       "streams_cfg": "default", "username": "bblp", "passwd": passwd})

    async def _watch_heartbeat(self):
        pid = _ipcam_pid()
        if pid != self.ipcam[0]:
            self.ipcam = (pid, time.monotonic())
        silent = time.monotonic() - max(self.report[0], self.ipcam[1])
        # Not tied to the RTSP setting: a frozen ipcam can break cloud live view and recording too afaik.
        if pid and silent > HEARTBEAT_TIMEOUT:
            async with self.lock:
                await self._restart_hung_ipcam(f"has sent no heartbeat for {silent:.0f}s")

    async def _watch_rtsp(self):
        off = _rtsp_wanted() and self._camera_present() and self._rtsp_on() is False
        if not off:
            self.restore_failed = False
            self.rtsp_off_since = None
            return
        now = time.monotonic()
        if self.rtsp_off_since is None:
            self.rtsp_off_since = now
        if self.restore_failed or now - self.rtsp_off_since < RTSP_RESTORE_DELAY:
            return
        self.rtsp_off_since = None
        logger.info("RTSP server is enabled but off, turning it on")
        async with self.lock:
            self.restore_failed = not await self._restore_rtsp()

    async def _watch_camera(self):
        """
        Get the camera back if ipcam lost it

        If ipcam says the camera is gone for CAMERA_GONE_TIMEOUT but its still on usb, ipcam
        lost track of it so we try to recover it once. If its off usb there's nothing to
        rebind so we just log it once and wait for it to come back
        """
        present = self._camera_present()
        # remember where it is, cant look it up once its off the bus
        self.camera_device = _usb_camera() or self.camera_device
        if present:
            self.camera_handled = False
        if present is not None and present != self.camera_was_present:
            logger.log(logging.INFO if present else logging.WARNING,
                       "camera connected" if present else "camera disconnected")
            self.camera_was_present = present

        # moving on or off the bus restarts the timeout.
        gone = present is False
        off_usb = gone and not os.path.exists(f"/sys/bus/usb/devices/{self.camera_device}")
        if off_usb != self.camera_off_usb:
            self.camera_off_usb = off_usb
            self.camera_handled = False
            self.camera_gone_since = None
        if not gone:
            self.camera_gone_since = None
            return
        now = time.monotonic()
        if self.camera_gone_since is None:
            self.camera_gone_since = now
        if self.camera_handled or now - self.camera_gone_since < CAMERA_GONE_TIMEOUT:
            return
        self.camera_gone_since = None
        self.camera_handled = True
        if off_usb:
            logger.error("camera is off USB -- check the cable, or power-cycle the printer")
            return
        logger.warning(f"camera has been gone for {CAMERA_GONE_TIMEOUT}s")
        if await self._recover_camera():
            logger.info("camera is back")
        else:
            logger.error("camera did not come back -- check the cable, or power-cycle the printer")

    async def _watch(self):
        while True:
            await asyncio.sleep(WATCH_INTERVAL)
            if self.lock.locked():
                # something is restarting, so start the timers over after
                self.rtsp_off_since = self.camera_gone_since = None
                continue
            for watch in (self._watch_heartbeat, self._watch_camera, self._watch_rtsp):
                try:
                    await watch()
                except Exception as e:
                    logger.exception(f"{watch.__name__} failed: {e}")

    async def _probe(self):
        """
        Checks ipcam is still serving by doing a TLS handshake on port 322

        We close it straight away without sending any rtsp so it doesnt show up as a client
        to ipcam or bbl_screen. A hung ipcam either refuses the connection or times out.
        """
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", IPCAM_PORT, ssl=ssl_ctx), timeout=PROBE_TIMEOUT)
            writer.close()
            await writer.wait_closed()
            return True
        except (asyncio.TimeoutError, OSError, ssl.SSLError) as e:
            logger.warning(f"camera probe failed: {e!r}")
            return False

    async def _check(self):
        # Port 322 only listens while RTSP is on.
        should_listen = lambda: _rtsp_wanted() and self._rtsp_on()
        if not should_listen():
            return
        healthy = await self._probe()
        if not healthy:
            # It might just be restarting, so check again.
            await asyncio.sleep(REPORT_MAX_AGE)
            if not should_listen():
                return
            healthy = await self._probe()

        if not healthy:
            await self._restart_hung_ipcam("is not answering on port 322")
        elif self.gave_up:
            logger.info("ipcam is healthy again, re-arming")
            self.gave_up = False

    async def task(self):
        asyncio.create_task(self._watch())
        logger.info("camera watchdog started")
        while True:
            await asyncio.sleep(self.daemon.settings.get("camera.watchdog.interval", DEFAULT_INTERVAL))
            try:
                async with self.lock:
                    await self._check()
            except Exception as e:
                logger.exception(f"camera check failed: {e}")


_daemon = None

def load(daemon):
    global _daemon
    _daemon = daemon
    daemon.camera_watchdog = CameraWatchdog(daemon=daemon)

def start():
    asyncio.create_task(_daemon.camera_watchdog.task())
