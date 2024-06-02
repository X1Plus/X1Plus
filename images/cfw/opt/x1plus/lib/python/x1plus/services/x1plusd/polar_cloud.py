"""
Module to allow printing using Polar Cloud service.
"""

import asyncio
import logging
import os
import subprocess
import socketio
from typing import Dict

# from x1plusd.dbus import
import x1plus
from x1plus.utils import get_MAC, get_IP, serial_number, is_emulating

logger = logging.getLogger(__name__)


class PolarPrint:
    def __init__(self, settings):
        self.public_key = ""
        self.polar_sn = ""
        self.private_key = ""
        self.connected = False
        self.mac = ""
        self.pin = ""
        self.username = ""
        self.server_url = ""
        self.socket = None
        self.ip = ""
        self.polar_settings = settings
        # self.polar_settings.on("polarprint.enabled", self.sync_startstop())
        # self.polar_settings.on("self.pin", self.set_pin())
        self.socket = None
        self.connected = False  # We might not need this, but here for now.
        if is_emulating():
            import inspect
            # I need to use actual account creds to connect, so we're using .env
            # for testing, until there's an interface.
            # dotenv isn't installed, so just open the .env file and parse it.
            # This means that .env file must formatted correctly, with var names
            # `username`, `pin`, and `server_url`.
            env_dir = os.path.dirname(inspect.getfile(inspect.currentframe()))
            with open(os.path.join(env_dir, ".env")) as env:
                for line in env:
                    k, v = line.split("=")
                    setattr(self, k, v.strip())


    async def begin(self):
        await self._create_socket()  # After this self.socket should no longer be None.


    async def _make_request(self, which_request, data: Dict[str, str]) -> None:
        """Make a request to the server."""
        if self.socket:
            await self.socket.emit(which_request, data)
        else:
            logger.error(f"{which_request} failed. Socket is closed.")
            # Log an error here. Find polite failure mode.

    async def _create_socket(self) -> None:
        """Create Socket.IO client and connect to server."""
        self.socket = socketio.AsyncClient()
        connect = asyncio.create_task(
            self.socket.connect(
                self.server_url, transports=["websocket"]
            )
        )
        await connect

        # Assign socket callbacks
        self.socket.on("connect", self._on_connect)
        # self.socket.on("registerResponse", self._on_register_response)
        self.socket.on("keyPair", self._on_keypair_response)
        # self.socket.on("helloResponse", self._on_hello_reponse)
        self.socket.on("welcome", self._on_welcome)

        self.socket.connect(self.server_url)

    def _on_connect(self):
        self.connected = True

    async def _on_welcome(self, response, *args, **kwargs):
        """
        Check to see if printer has already been registered. If it has, we can
        ignore this. Otherwise, must get a key pair, then call register, then
        save the new serial number.
        """
        logger.debug(f"_on_welcome: {response}")
        if not self.public_key:
            # We need to get an RSA key pair before we can go farther.
            await self.socket.emit("makeKeyPair", {"type": "RSA", "bits": 2048})
        if not self.polar_sn:
            # We have keys, but still need to register. Use the welcome challenge
            # to do so.
            if is_emulating:
                sn = "123456789"
            else:
                sn = serial_number()
            data = {
                "mfg": "bambu",
                "email": self.username,
                "pin": self.pin,
                "publicKey": self.public_key,
                "mfgSn": sn,
                "myInfo": {
                    "MAC": get_MAC()
                }
            }
            await self.socket.emit("register", data)
        else:
            # The printer has just reconnected. Must validate with hello command.
            # First, encode challenge string
            # Note that we're now using the serial number assigned by the server.
            data = {
                "serialNumber": self.polar_sn,
                "signature": "signed challenge",   # BASE64 encoded string, required
                "MAC": get_MAC(),
                "protocol": "2.0",
                "mfgSn": serial_number(),
            }
            """
            Note that the following optional fields might be used in future.
            "printerMake": "printer make",                       // string, optional
            "version": "currently installed software version",   // string, optional
            "localIP": "printer's local IP address",             // string, optional
            "rotateImg": 0 | 1,                                  // integer, optional
            "transformImg": 0 - 7,                               // integer, optional
            "camOff": 0 | 1,                                     // integer, optional
            "camUrl": "URL for printer's live camera feed"       // string, optional
            """

            # Send register request; get back a Polar Cloud serial number.
            await self.socket.emit("register", data)


    def _on_keypair_response(self, response, *args, **kwargs):
        logger.debug(f"_on_keypair_response: {response}")
        if 'status' in response and response["status"] == "SUCCESS":
            self.public_key = response["public"]
            self.private_key = response["private"]


    # We cannot do anything with the challenge until we know that
    # the printer has been registered previously. So we will check on connection
    # to the status server if there is a serial number and deal with the latest
    # challenge later
    # The cloud response after opening a connection to it
    # @arguments data: The payload from the cloud
    async def onWelcome(self, data, *args, **kwargs):
        # Only store the challenge if we have a serial assigned already
        if self.printer.serialNumber() != "":
            if "challenge" in data:
                self.challenge = data["challenge"]
                self.logger.debug("Challenge received: {}".format(self.challenge))
                # Choose the correct MAC in use currently
                myMac = self.ethIface
                if self.activeIface == self.wlanIface:
                    myMac = self.wlanIface
                # The payload the 'hello' command is expecting
                data = {
                    "serialNumber": self.printer.serialNumber(),
                    "signature": crypto.sign(self.key, self.challenge, "sha256"),
                    "MAC": myMac,
                    "localIP": self.ip,
                    "protocol": "2",
                    "version": __version__,
                    "rotateImg": 0,
                    # Streaming URL
                    "camUrl": "http://" + self.ip + ":8080/?action=stream",
                    "printerMake": self.printer.printerMake(),
                }
                await self.socket.emit("hello", data)
                # The challenge can be removed now that it has been dealt with
                self.challenge = None
            else:
                # This should never happen as it is not part of the protocol
                self.logger.error("Welcome did not contain a challenge")
                self.socket.disconnect()

    def set_pin(self):
        """If PIN is not set, open Polar Cloud interface window and get PIN."""
        if not self.pin:
            # Get it from the interface.
            pass

    def set_interface(self):
        """Get IP and MAC addresses and store them in self.settings."""
        self.mac = get_MAC()
        self.ip = get_IP()

    def get_key(self):
        if not self.private_key:
            pass
