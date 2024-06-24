"""
Module to allow printing using Polar Cloud service.
"""

import asyncio
import datetime
import logging
import socketio
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from base64 import b64encode

from x1plus.utils import get_MAC, get_IP, serial_number, is_emulating
from .dbus import X1PlusDBusService

logger = logging.getLogger(__name__)

POLAR_INTERFACE = "x1plus.polar"
POLAR_PATH = "/x1plus/polar"

class PolarPrintService(X1PlusDBusService):
    def __init__(self, settings, **kwargs):
        """
        The MAC is stored here, but on restart will always generated dynamically
        in an attempt to discourage movement of SD cards.
        """
        logger.info("PolarPrintService")
        self.mac = ""
        # The username can be stored in non-volatile memory, but the PIN must be
        # requested from the interface on every startup.
        self.pin = ""
        # username is here only for emulation mode when reading from .env.
        self.username = ""
        # Todo: Check to see if this is the correct server.
        self.server_url = "https://printer2.polar3d.com"
        self.socket = None
        self.ip = ""  # This will be used for sending camera images.
        self.polar_settings = settings
        self.polar_settings = settings
        # Todo: Fix two "on" fn calls below.
        # self.polar_settings.on("polarprint.enabled", self.sync_startstop())
        # self.polar_settings.on("self.pin", self.set_pin())
        self.socket = None
        super().__init__(
            dbus_interface=POLAR_INTERFACE, dbus_path=POLAR_PATH, **kwargs
        )

    def polar_enabled(self):
        return bool(self.x1psettings.get("ota.enabled", False))

    async def task(self):
        """Create Socket.IO client and connect to server."""
        self.socket = socketio.AsyncClient()
        self.set_interface()
        logger.info("Socket created!")
        try:
            await self.get_creds()
        except Exception as e:
            logger.debug(f"Polar get_creds: {e}")
            return
        await self.socket.connect(self.server_url, transports=["websocket"])
        # Assign socket callbacks.
        self.socket.on("registerResponse", self._on_register_response)
        self.socket.on("keyPair", self._on_keypair_response)
        self.socket.on("helloResponse", self._on_hello_response)
        self.socket.on("welcome", self._on_welcome)
        self.socket.on("delete", self._on_delete)

        await super().task()

    async def _on_welcome(self, response, *args, **kwargs) -> None:
        """
        Check to see if printer has already been registered. If it has, we can
        ignore this. Otherwise, must get a key pair, then call register.
        """
        logger.info("_on_welcome.")
        # Two possibilities here. If it's already registered there should be a
        # Polar Cloud serial number and a set of RSA keys. If not, then must
        # request keys first.
        if self.polar_settings.get("polar.sn", "") and self.polar_settings.get(
            "polar.private_key", ""
        ):
            logger.debug(f"challenge: {response['challenge']}")
            # The printer has been registered.
            # Remember that "polar.sn" is the serial number assigned by the server.
            # First, encode challenge string with the private key.
            private_key = self.polar_settings.get("polar.private_key").encode("utf-8")
            rsa_key = RSA.import_key(private_key)
            hashed_challenge = SHA256.new(response["challenge"].encode("utf-8"))
            key = pkcs1_15.new(rsa_key)
            data = {
                "serialNumber": self.polar_settings.get("polar.sn"), # Don't need a default here.
                "signature": b64encode(key.sign(hashed_challenge)).decode("utf-8"),
                "MAC": self.mac,
                "protocol": "2.0",
                "mfgSn": self.serial_number(),
            }
            """
            Note that the following optional fields might be used in future.
            "printerMake": "printer make",                     // string, optional
            "version": "currently installed software version", // string, optional
            "localIP": "printer's local IP address",           // string, optional
            "rotateImg": 0 | 1,                                // integer, optional
            "transformImg": 0 - 7,                             // integer, optional
            "camOff": 0 | 1,                                   // integer, optional
            "camUrl": "URL for printer's live camera feed"     // string, optional
            """
            await self.socket.emit("hello", data)
        elif not self.polar_settings.get(
            "polar.sn", ""
        ) and not self.polar_settings.get("polar.public_key", ""):
            # We need to get an RSA key pair before we can go further.
            # Todo: This needs to be moved locally rather than being remote, so
            # private key isn't transmitted.
            await self.socket.emit("makeKeyPair", {"type": "RSA", "bits": 2048})
        elif not self.polar_settings.get("polar.sn", ""):
            # We already have a key: just register.
            # Todo: I think there might be a race condition here.
            logger.info(f"_on_welcome Registering.")
            await self._register()
        else:
            # It's not possible to have a serial number and no key, so this
            # would be a real problem.
            logger.error("Somehow have an SN and no key.")
            exit()

    def _on_hello_response(self, response, *args, **kwargs) -> None:
        """
        If printer is previously registered, a successful hello response means
        the printer is connected and ready to print.
        """
        if response["status"] == "SUCCESS":
            logger.info("_on_hello_response success")
            logger.info("Polar Cloud connected.")
        else:
            logger.error(f"_on_hello_response failure: {response['message']}")
            # Todo: send error to interface.
            exit()
        self._status()

    async def _on_keypair_response(self, response, *args, **kwargs) -> None:
        """
        Request a keypair from the server. On success register. On failure kick
        out to interface for new email or pin.
        """
        if response["status"] == "SUCCESS":
            await self.polar_settings.put("polar.public_key", response["public"])
            await self.polar_settings.put("polar.private_key", response["private"])
            # We have keys, but still need to register. First disconnect.
            logger.info("_on_keypair_response success. Disconnecting.")
            # Todo: I'm not creating a race condition with the next three fn calls, am I?
            await self.socket.disconnect()
            # After the next request the server will respond with `welcome`.
            logger.info("Reconnecting.")
            await self.socket.connect(self.server_url, transports=["websocket"])
        else:
            # We have an error.
            logger.error(f"_on_keypair_response failure: {response['message']}")
            # Todo: communicate with dbus to fix this!
            # Todo: deal with error using interface.

    async def _on_register_response(self, response, *args, **kwargs) -> None:
        """
        Get register response from status server and save serial number.
        When this fn completes, printer will be ready to receive print calls.
        """
        if response["status"] == "SUCCESS":
            logger.info("_on_register_response success.")
            logger.debug(f"Serial number: {response['serialNumber']}")
            await self.polar_settings.put("polar.sn", response["serialNumber"])
            logger.info("Polar Cloud connected.")

        else:
            logger.error(f"_on_register_response failure: {response['reason']}")
            # Todo: deal with various failure modes here. Most can be dealt
            # with in interface. First three report as server erros? Modes are
            # "SERVER_ERROR": Report this?
            # "MFG_UNKNOWN": Again, should be impossible.
            # "INVALID_KEY": Ask for new key. Maybe have a counter and fail after two?
            # "MFG_MISSING": This should be impossible.
            # "EMAIL_PIN_ERROR": Send it to the interface.
            # "FORBIDDEN": There's an issue with the MAC address.
            if response["reason"].lower() == "forbidden":
                # Todo: Must communicate with dbus to debug this!
                logger.error(
                    f"Forbidden. Duplicate MAC problem!\nTerminating MAC: "
                    f"{self.mac}\n\n"
                )
                exit()

    async def _register(self) -> None:
        """
        Send register request. Note this can only be called after a keypair
        has been received and stored.
        """
        logger.info("_register.")
        data = {
            "mfg": "bambu",
            "email": self.polar_settings.get("polar.username"),
            "pin": self.pin,
            "publicKey": self.polar_settings.get("polar.public_key"),
            "mfgSn": self.serial_number(),
            "myInfo": {"MAC": self.mac},
        }
        await self.socket.emit("register", data)

    async def _status(self) -> None:
        """
        Should send several times a minute (3? 4?). All fields but serialNumber
        and status are optional.
        {
            "serialNumber": "string",
            "status": integer,
            "progress": "string",
            "progressDetail": "string",
            "estimatedTime": integer,
            "filamentUsed": integer,
            "startTime": "string",
            "printSeconds": integer,
            "bytesRead": integer,
            "fileSize": integer,
            "tool0": floating-point,
            "tool1": floating-point,
            "bed": floating-point,
            "chamber": floating-point,
            "targetTool0": floating-point,
            "targetTool1": floating-point,
            "targetBed": floating-point,
            "targetChamber": floating-point,
            "door": integer,
            "jobId": "string",
            "file": "string",
            "config": "string"
        }
        Possible status codes are:
        0     Ready; printer is idle and ready to print
        1     Serial; printer is printing a local print over its serial connection
        2     Preparing; printer is preparing a cloud print (e.g., slicing)
        3     Printing; printer is printing a cloud print
        4     Paused; printer has paused a print
        5     Postprocessing; printer is performing post-printing operations
        6     Canceling; printer is canceling a print from the cloud
        7     Complete; printer has completed a print job from the cloud
        8     Updating; printer is updating its software
        9     Cold pause; printer is in a "cold pause" state
        10     Changing filament; printer is in a "change filament" state
        11     TCP/IP; printer is printing a local print over a TCP/IP connection
        12     Error; printer is in an error state
        13     Disconnected; controller's USB is disconnected from the printer
        14     Door open; unable to start or resume a print
        15     Clear build plate; unable to start a new print
        """
        while True:
            now = datetime.datetime.now()

            next_work = now + datetime.timedelta(seconds = 20) # Several times a minute.
            if ota_enabled:
                next_work = min((next_work, self.next_check_timestamp,))

            try:
                await asyncio.wait_for(self.ota_task_wake.wait(), timeout = (next_work - now).total_seconds())
            except asyncio.TimeoutError:
                pass
            self.ota_task_wake.clear()

    async def _on_delete(self, response, *args, **kwargs) -> None:
        """
        Printer has been deleted from Polar Cloud. Remove all identifying information
        from card. The current print should finish. Disconnect socket so that
        username and PIN don't keep being requested and printer doesn't reregister.
        """
        if response["serialNumber"] == self.polar_settings.get("polar.sn"):
            self.polar_settings.put("polar.sn", "")
            self.polar_settings.put("polar.username", "")
            self.polar_settings.put("polar.public_key", "")
            self.polar_settings.put("polar.private_key", "")
            self.pin = ""
            self.mac = ""
            self.username = ""
            # Todo: stop status() here?
            self.socket.disconnect()

    async def get_creds(self) -> None:
        """
        If PIN and username are not set, open Polar Cloud interface window and
        get them.
        Todo: This works only during emulation.
        """
        if is_emulating():
            # I need to use actual account creds to connect, so we're using .env
            # for testing, until there's an interface.
            # dotenv isn't installed, so just open the .env file and parse it.
            # This means that .env file must formatted correctly, with var names
            # `username` and `pin`.
            from pathlib import Path
            env_file = Path(__file__).resolve().parents[0] / ".env"
        else:
            # Todo: Fix this for production. Should be from interface!!!
            env_file = os.path.join("/sdcard", ".env")
            if not self.pin:
                # Get it from the interface.
                pass
            if not self.polar_settings.get("polar.username", ""):
                # Get it from the interface.
                pass
        with open(env_file) as env:
            k, v = env.readline.split("=")
            self.username = v
            k, v = env.readline.split("=")
            self.pin = v
            # for line in env:
            #     k, v = line.split("=")
            #     # Because setattr doesn't exist.
            #     self.username = v
            #     # setattr(self, k, v.strip())
        await self.polar_settings.put("polar.username", self.username)

    def set_interface(self) -> None:
        """
        Get IP and MAC addresses and store them in self.settings. This is
        intentionally dynamic as a security measure.
        """
        self.mac = get_MAC()
        self.ip = get_IP()

    def serial_number(self) -> str:
        """
        Return the Bambu serial number—NOT the Polar Cloud SN. If emulating,
        random string.
        """
        if is_emulating:
            return "123456789"
        else:
            return serial_number()
