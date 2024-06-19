"""
Module to allow printing using Polar Cloud service.
"""

import asyncio
import logging
import socketio

import x1plus
from x1plus.utils import get_MAC, get_IP, serial_number, is_emulating

logger = logging.getLogger(__name__)


class PolarPrintService:
    def __init__(self, settings):
        self.polar_sn = 0
        # Todo: VERY IMPORTANT!! The public and private keys MUST be moved to
        # non-volatile memory before release.
        self.public_key = ""
        self.private_key = ""
        self.connected = False
        self.mac = ""
        self.pin = ""
        self.username = ""
        self.server_url = "https://printer2.polar3d.com"
        self.socket = None
        self.ip = ""
        # Todo: Fix two "on" fn calls below. Also, start communicating with dbus.
        self.polar_settings = settings
        # self.polar_settings.on("polarprint.enabled", self.sync_startstop())
        # self.polar_settings.on("self.pin", self.set_pin())
        self.socket = None
        self.connected = False  # We might not need this, but here for now.


    async def begin(self):
        """Create Socket.IO client and connect to server."""
        self.socket = socketio.AsyncClient()
        connect_task = asyncio.create_task(
            self.socket.connect(self.server_url, transports=["websocket"])
        )
        await connect_task
