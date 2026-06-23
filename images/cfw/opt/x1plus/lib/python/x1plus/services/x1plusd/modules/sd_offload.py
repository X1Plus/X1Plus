"""
Redirects high write SD card directories to USB storage via bind mounts.

The Bambu X1 SD card accumulates heavy write traffic from three sources:
   /sdcard/log/      : syslog rotation
   /sdcard/timelapse/: timelapse MP4s written during every print
   /sdcard/ipcam/    : continuous writes during prints

When a USB drive is detected this redirects those directories
to the USB drive using bind mounts. All existing firmware
code continues to use the same /sdcard/* paths transparently. When USB is
removed the bind mounts are lazily unmounted and writes fall back to SD.

Only FAT32 drives are used, the same filesystem as the SD card.

Settings:
  sd_offload.port  - str, USB port to offload to, or "off" to disable (default: "off")

[X1PLUS_MODULE_INFO]
module:
  name: sd_offload
  default_enabled: true
[END_X1PLUS_MODULE_INFO]
"""

import asyncio
import json
import logging
import os
import subprocess

from jeepney.bus_messages import MatchRule, message_bus
from jeepney.io.asyncio import Proxy

logger = logging.getLogger(__name__)

OFFLOAD_DIRS = [
    "/sdcard/log",
    "/sdcard/timelapse",
    "/sdcard/ipcam",
]

_daemon = None


def _mount_dir(usb_mount, sdcard_path):
    usb_path = os.path.join(usb_mount, os.path.basename(sdcard_path))
    try:
        os.makedirs(usb_path, exist_ok=True)
        os.makedirs(sdcard_path, exist_ok=True)
        result = subprocess.run(
            ["mount", "--bind", usb_path, sdcard_path],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            logger.info(f"bind-mounted {sdcard_path} -> {usb_path}")
        else:
            logger.error(f"bind mount failed for {sdcard_path}: {result.stderr.strip()}")
    except Exception as e:
        logger.error(f"error mounting {sdcard_path}: {e}")


def _umount_dir(sdcard_path):
    try:
        result = subprocess.run(
            ["umount", "-l", sdcard_path],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            logger.info(f"unmounted {sdcard_path}")
            return True
        logger.warning(f"unmount failed for {sdcard_path}: {result.stderr.strip()}")
    except Exception as e:
        logger.error(f"error unmounting {sdcard_path}: {e}")
    return False


def _setup_mounts(usb_mount):
    _teardown_mounts()
    for path in OFFLOAD_DIRS:
        _mount_dir(usb_mount, path)


def _teardown_mounts():
    # Checks what's actually mounted and cleans up stale mounts
    for path in OFFLOAD_DIRS:
        while os.path.ismount(path) and _umount_dir(path):
            pass


class SdOffload:
    def __init__(self, daemon):
        self.daemon = daemon
        self._usb_mount = None
        self._rejected = None

    def _on_settings_changed(self):
        try:
            self._handle_usb_state(self.daemon.expansion._usb)
        except AttributeError:
            pass

    def _handle_usb_state(self, usb_state):
        selected_port = self.daemon.settings.get("sd_offload.port", "off")
        mounts = usb_state.get("mounts", [])

        new_mount = None
        if selected_port != "off":
            for m in mounts:
                if str(m.get("usb_port", "")) == str(selected_port):
                    if m.get("filesystem") == "vfat":
                        new_mount = m["mount_point"]
                    elif self._rejected != m["mount_point"]:
                        logger.warning(f"drive on port {selected_port} is {m.get('filesystem')}, not FAT32; not offloading to it")
                        self._rejected = m["mount_point"]
                    break

        if new_mount and new_mount != self._usb_mount:
            if self._usb_mount:
                logger.info(f"USB drive changed from {self._usb_mount} to {new_mount}, remounting")
            logger.info(f"USB drive on port {selected_port} detected at {new_mount}, setting up offload mounts")
            self._usb_mount = new_mount
            _setup_mounts(self._usb_mount)
        elif not new_mount:
            if self._usb_mount:
                logger.info("USB drive removed or offload disabled, tearing down mounts")
            self._usb_mount = None
            _teardown_mounts()

    async def task(self):
        logger.info("SD offload module started")

        self.daemon.settings.on("sd_offload.port", self._on_settings_changed)

        match = MatchRule(type="signal", interface="x1plus.expansion", path="/", member="UsbChanged")
        await Proxy(message_bus, self.daemon.router).AddMatch(match)

        with self.daemon.router.filter(match) as queue:
            # A drive may already be plugged in before we start listening, so check once now
            try:
                self._handle_usb_state(self.daemon.expansion._usb)
            except AttributeError:
                pass  # USB state isn't ready yet, the first UsbChanged will cover it

            while True:
                msg = await queue.get()
                try:
                    self._handle_usb_state(json.loads(msg.body[0]))
                except Exception as e:
                    logger.error(f"error handling UsbChanged signal: {e}")


def load(daemon):
    global _daemon
    _daemon = daemon
    daemon.sd_offload = SdOffload(daemon=daemon)


def start():
    asyncio.create_task(_daemon.sd_offload.task())
