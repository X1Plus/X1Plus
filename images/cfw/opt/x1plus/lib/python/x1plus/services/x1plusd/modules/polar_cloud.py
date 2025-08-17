"""
Module to allow printing using Polar Cloud service.

[X1PLUS_MODULE_INFO]
module:
  name: polar_cloud
  default_enabled: true
[END_X1PLUS_MODULE_INFO]
"""

import asyncio
import aiohttp
import datetime
import logging
import os
import socketio
import ssl
import subprocess
import time
from enum import Enum, auto
from jeepney import DBusAddress, new_method_call, MessageType
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from base64 import b64encode

from x1plus.aiocamera import AioRtspReceiver
from x1plus.utils import get_MAC, is_emulating, serial_number

from x1plus.services.x1plusd.dbus import X1PlusDBusService

logger = logging.getLogger(__name__)

POLAR_INTERFACE = "x1plus.polar"
POLAR_PATH = "/x1plus/polar"

# Setup SSL for aiohttp and websocket.
ssl_ctx = ssl.create_default_context(capath="/etc/ssl/certs")
connector = aiohttp.TCPConnector(ssl=ssl_ctx)
http_session = aiohttp.ClientSession(connector=connector)
aws_connector = aiohttp.TCPConnector(ssl=ssl_ctx)
aws_http_session = aiohttp.ClientSession(connector=aws_connector)

class _ConnectState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    WAITING_HELLO = auto()
    ESTABLISHED = auto()

class PolarCredentials:
    """
    Encapsulates all persistent state for logging in to Polar Cloud,
    including generated keys and credentials that are used to generate them.
    """
    
    SETTINGS_KEY = "polar.auth"
    
    def __init__(self, daemon):
        self.daemon = daemon
        
        self.username = None
        self.pin = None
        self.public_key = None
        self.private_key = None
        self.polar_sn = None

        self.load_from_envfile()
        self.load_from_settings()
    
    def load_from_envfile(self):
        if is_emulating():
            from pathlib import Path

            env_file = Path(__file__).resolve().parents[0] / "env"
        else:
            env_file = "/sdcard/polar-config.txt"

        try:
            with open(env_file) as env:
                for line in env.readlines():
                    k, v = line.strip().split("=")
                    if k == "username":
                        self.username = v
                    elif k == "pin":
                        self.pin = v
        except:
            pass
    
    def load_from_settings(self):
        try:
            d = self.daemon.settings.get(self.SETTINGS_KEY, {})
            if d.get('printer_sn', None) != serial_number():
                logger.error("settings file serial number does not match actual serial number?")
                return
            self.username = d.get('username', None)
            self.polar_sn = d.get('polar_sn', None)
            self.private_key = d.get('private_key', None)
            self.public_key = d.get('public_key', None)
            # we do not need to load the PIN since that is used only for initial login
        except:
            pass
    
    async def save(self):
        await self.daemon.settings.put(self.SETTINGS_KEY, {
            'printer_sn': serial_number(),
            'username': self.username,
            'polar_sn': self.polar_sn,
            'private_key': self.private_key,
            'public_key': self.public_key,
        })
    
    async def wipe(self):
        self.username = None
        self.pin = None
        self.polar_sn = None
        self.private_key = None
        self.public_key = None
        await self.save()
    
    def ready(self):
        return (self.username and self.polar_sn and self.private_key and self.public_key) or (self.username and self.pin)

class PolarPrintService(X1PlusDBusService):
    STATE_TIMEOUTS = {
        _ConnectState.DISCONNECTED: 60, # retry every minute
        _ConnectState.CONNECTING: 30,
        _ConnectState.WAITING_HELLO: 30,
        _ConnectState.ESTABLISHED: 60, # time since we've seen a keepalive PING
    }

    """
    status_lookup will be used in _status_update() to interpret job states
    coming from mqtt and translate them into self.status. Values of printer
    status enums are in in-line comments.

    TODO: in the future, FAILED and FINISH should actually report 15, which is
    Clear build plate; unable to start a new print.
    """
    STATE_TO_POLAR_STATUS = {
        "IDLE": 0,
        "SLICING": 1,  # 1
        "PREPARE": 2,
        "RUNNING": 3,
        "FINISH": 7,  # 4
        "FAILED": 12,  # 5
        "PAUSE": 4,  # 6
    }

    def __init__(self, daemon, **kwargs):
        """
        The MAC is stored here, but on restart will always generated dynamically
        in an attempt to discourage movement of SD cards.
        """
        logger.info("Polar __init__")
        self.daemon = daemon
        self.enabled = self.daemon.settings.get("polar.enabled", False)
        self.mac = get_MAC()
        
        self.creds = PolarCredentials(self.daemon)
        
        self.server_url = "https://printer4.polar3d.com" # "http://status-dev.polar3d.com/"
        self.socket = None
        self.status = 0  # Idle
        # job_id defaults to "0" when not printing. See _status_update for logic
        # on changes to this value.
        self.job_id = "0"
        self.file_name = ""
        """
        last_ping will hold time of last ping, so we're not sending status
        more than once every 10 seconds.
        """
        self.last_ping = datetime.datetime.now() - datetime.timedelta(seconds=10)
        self.start_time = datetime.datetime.now()  # Start time for each print job.
        self.time_finished = datetime.datetime.now()  # Used in _status_update().
        # How long the job will take in seconds. This is set in _status_() and
        # reset in _job().
        self.estimated_print_time = 0
        """
        Next two variables are for sending camera images to Polar Cloud. None of
        this should be persistent, especially the urls, since they expire, so all
        saved as instance vars. The first set is for sending images while printing,
        the second set for printing when idle.
        """
        self.printing_cam_stream = {
            "expiration_time": time.time(),
            "form_data": {},
            "curl_call": "",
        }
        self.idle_cam_stream = {
            "expiration_time": time.time(),
            "form_data": {},
            "curl_call": "",
        }
        
        # Create the socket.io client, but don't connect yet: the
        # watchdog_task will do that work for us.
        self.socket = socketio.AsyncClient(
            reconnection=False, # we don't want Socket.io to reconnect for us, since we need to know if something has gone wrong and we need to do the 'welcome' dance again
            http_session=http_session,
            logger=logger,
            engineio_logger=logger,
        )
 
        self.socket.on("connect", self._on_connect)
        self.socket.on("connect_error", self._on_connect_error)
        self.socket.on("disconnect", self._on_disconnect)
        
        self.socket.on("registerResponse", self._on_register_response)
        self.socket.on("keyPair", self._on_keypair_response)
        self.socket.on("helloResponse", self._on_hello_response)
        self.socket.on("welcome", self._on_welcome)
        self.socket.on("delete", self._on_delete)
        self.socket.on("print", self._on_print)
        self.socket.on("pause", self._on_pause)
        self.socket.on("resume", self._on_resume)
        self.socket.on("cancel", self._on_cancel)
        self.socket.on("getUrlResponse", self._on_url_response)

        # Watch for settings changes
        self.daemon.settings.on("polar.enabled", self._on_enabled_changed)

        self.status_task = None
        
        self.watchdog_task = None
        self.watchdog_signal = asyncio.Event()
        self.reconnect_now = False
        
        self.connect_state = _ConnectState.DISCONNECTED
        self.connect_state_ts = 0
        self.last_connection_error = None
        
        self.last_status_object = None
        
        super().__init__(
            router=daemon.router,
            dbus_interface=POLAR_INTERFACE,
            dbus_path=POLAR_PATH,
            **kwargs,
        )

    async def task(self) -> None:
        # It will shut itself down if we are not enabled.
        self.watchdog_task = asyncio.create_task(self._watchdog_task())
        await super().task()

    def _on_enabled_changed(self):
        """Handle when polar.enabled setting changes."""
        self.enabled = self.daemon.settings.get("polar.enabled", False)
        if self.enabled and not self.watchdog_task:
            self.watchdog_task = asyncio.create_task(self._watchdog_task())
        else:
            # ... which will cause the watchdog to shut down
            asyncio.create_task(self._force_reconnect())
        asyncio.create_task(self._maybe_publish_status_object())

    def _make_dbus_status_object(self):
        return {
            'enabled': self.enabled,
            'connect_state': self.connect_state.name,
            'last_connection_error': self.last_connection_error,
            'username': self.creds.username,
            'logged_in': self.creds.polar_sn is not None,
            'serial_number': self.creds.polar_sn,
        }
    
    async def dbus_GetStatus(self, req):
        return self._make_dbus_status_object()
    
    async def dbus_Login(self, req):
        if self.creds.polar_sn:
            return {'status': 'failure', 'reason': 'already logged in'}
        self.creds.username = str(req['username'])
        self.creds.pin = str(req['pin'])
        # no need to save here -- nothing useful has actually happened
        await self._force_reconnect()
        if self.enabled and not self.watchdog_task:
            self.watchdog_task = asyncio.create_task(self._watchdog_task())
        return {}
    
    async def dbus_Logout(self, req):
        try:
            await self.socket.emit("unregister", self.creds.polar_sn)
        except:
            pass
        
        await self.creds.wipe()
        
        # Shut down the watchdog thread.
        await self._force_reconnect()
        return {}

    async def _maybe_publish_status_object(self):
        "Publish a new _make_status_object as a DBus signal iff something has changed."
        
        status_object = self._make_dbus_status_object()
        if status_object != self.last_status_object:
            # equality on a dict is object-equality, not reference-equality
            self.last_status_object = status_object
            await self.emit_signal("StatusChanged", status_object)
            logger.debug(f"polar status changed to {status_object}")
    
    async def _watchdog_task(self):
        self.connect_state = _ConnectState.DISCONNECTED
        self.connect_state_ts = 0

        while True:
            connect_state_timeout = self.connect_state_ts + self.STATE_TIMEOUTS[self.connect_state]
            if time.time() > connect_state_timeout or self.reconnect_now:
                self.reconnect_now = False
                logger.warning(f"hit timeout or forced reconnect in state {self.connect_state.name}; reconnecting")
                try:
                    await self.socket.disconnect()
                except:
                    pass
                
                if self.status_task:
                    self.status_task.cancel()
                    self.status_task = None
                
                if not self.enabled:
                    logger.info("Polar Cloud is not enabled; shutting down watchdog")
                    self.watchdog_task = None
                    return
                
                if not self.creds.ready():
                    logger.info("Polar Cloud does not have credentials; shutting down watchdog")
                    self.watchdog_task = None
                    return
                
                try:
                    self._update_state(_ConnectState.CONNECTING)
                    await self.socket.connect(self.server_url, transports=["websocket"], wait_timeout = 5)
                except Exception as e:
                    logger.warning(f"failed to connect: {e}")
                    self._update_state(_ConnectState.DISCONNECTED)
            
            next_work = self.connect_state_ts + self.STATE_TIMEOUTS[self.connect_state]
            now = time.time()
            if next_work > now:
                try:
    	            await asyncio.wait_for(self.watchdog_signal.wait(), timeout = next_work - now)
                except asyncio.TimeoutError:
                    pass
            self.watchdog_signal.clear()
    
    def _update_state(self, st):
        if st != self.connect_state:
            logger.debug(f"transitioning from {self.connect_state} to {st}")
        self.connect_state = st
        self.connect_state_ts = time.time()
        self.watchdog_signal.set()
        asyncio.create_task(self._maybe_publish_status_object())
    
    async def _force_reconnect(self):
        try:
            await self.socket.disconnect()
        except:
            pass
        self.reconnect_now = True
        self._update_state(_ConnectState.DISCONNECTED)
    
    async def _on_connect(self, *args, **kwargs) -> None:
        self._update_state(_ConnectState.WAITING_HELLO)
    
    async def _on_connect_error(self, *args, **kwargs) -> None:
        self._update_state(_ConnectState.DISCONNECTED)

    async def _on_disconnect(self, *args, **kwargs) -> None:
        self._update_state(_ConnectState.DISCONNECTED)

    async def _on_welcome(self, response, *args, **kwargs) -> None:
        """
        Check to see if printer has already been registered. If it has, we can
        ignore this. Otherwise, must get a key pair, then call register.
        """
        if self.connect_state != _ConnectState.WAITING_HELLO:
            logger.warning(f"_on_welcome in unexpected state {self.connect_state}?")
            return
        logger.info("Polar _on_welcome.")

        if not self.creds.public_key:
            # We need to get an RSA key pair before we can go further.
            # TODO: This needs to be moved locally rather than being remote, so
            # private key isn't transmitted.

            if self.creds.polar_sn:
                logger.warning(f"for some reason, we have a serial number, but no key; creating a new key, and wiping the serial number")
                await creds.wipe()
            await self.socket.emit("makeKeyPair", {"type": "RSA", "bits": 2048})
            
            return

        if not self.creds.polar_sn:
            # We have a key, but no serial number: register (and we'll reconnect once again once we have a serial number).
            await self._register()
            
            return

        # We have everything we need to log in; go for it.

        logger.debug(f"Polar challenge: {response['challenge']}")
        # The printer has been registered.
        # First, encode challenge string with the private key.
        rsa_key = RSA.import_key(self.creds.private_key.encode("utf-8"))
        hashed_challenge = SHA256.new(response["challenge"].encode("utf-8"))
        key = pkcs1_15.new(rsa_key)
        data = {
            "serialNumber": self.creds.polar_sn,
            "signature": b64encode(key.sign(hashed_challenge)).decode("utf-8"),
            "MAC": self.mac,
            "protocol": "2.0",
            "mfgSn": serial_number(),
            "printerMake": "Bambu Lab X1 Carbon",
        }
        """
        Note that the following optional fields might be used in future.
        "version": "currently installed software version", // string, optional
        "localIP": "printer's local IP address",           // string, optional
        "rotateImg": 0 | 1,                                // integer, optional
        "transformImg": 0 - 7,                             // integer, optional
        "camOff": 0 | 1,                                   // integer, optional
        "camUrl": "URL for printer's live camera feed"     // string, optional
        """
        logger.info("Polar emitting hello")
        await self.socket.emit("hello", data)

    async def _on_hello_response(self, response, *args, **kwargs) -> None:
        """
        If printer is previously registered, a successful hello response means
        the printer is connected and ready to print.
        """
        if response["status"] != "SUCCESS":
            if response["message"] == "Printer has been deleted":
                logger.error(f"_on_hello_response failure: {response['message']}")
                self.last_connection_error = "Printer removed from cloud"
                self._maybe_publish_status_object()
                await self.creds.wipe()
                await self._force_reconnect()
            else:
                logger.error(f"_on_hello_response failure: {response['message']}")
                self.last_connection_error = f"Hello response error: {response['message']}"
            return

        logger.info("Polar _on_hello_response success")
        logger.info("Polar Cloud connected.")
        self._update_state(_ConnectState.ESTABLISHED)
        await self._get_url("idle")
        await self._get_url("printing") # can result in "failed wrong serial number"; that's fine, if nothing is printing

        if self.status_task:
            logger.error("leftover status_task?? somebody did not clean up, but I'm killing it anyway")
            self.status_task.cancel()
            self.status_task = None
        self.status_task = asyncio.create_task(self._status())

    async def _on_keypair_response(self, response, *args, **kwargs) -> None:
        """
        Request a keypair from the server. On success register. On failure kick
        out to interface for new email or pin.
        """
        if response["status"] != "SUCCESS":
            error_msg = response.get('message', 'Key pair request failed')
            logger.error(f"_on_keypair_response failure: {error_msg}")
            self.last_connection_error = f"Key error: {error_msg}"
            self._maybe_publish_status_object()
            return
        
        self.creds.public_key = response['public']
        self.creds.private_key = response['private']
        await self.creds.save()
        # We have keys, but still need to register. First disconnect.  After the next request, the server willr espond with `welcome`.
        logger.info("Polar _on_keypair_response success. Disconnecting.")
        await self._force_reconnect()

    async def _on_register_response(self, response, *args, **kwargs) -> None:
        """
        Get register response from status server and save serial number.
        When this fn completes, printer will be ready to receive print calls.
        """
        if response["status"] != "SUCCESS":
            error_msg = response.get('reason', 'Registration failed')
            logger.error(f"_on_register_response failure: {error_msg}")
            self.last_connection_error = f"Registration error: {error_msg}"
            await self._maybe_publish_status_object()
            # TODO: deal with various failure modes here. Most can be dealt
            # with in interface. First three report as server erros? Modes are
            # "SERVER_ERROR": Report this?
            # "MFG_UNKNOWN": Again, should be impossible.
            # "INVALID_KEY": Ask for new key. Maybe have a counter and fail after two?
            # "MFG_MISSING": This should be impossible.
            # "EMAIL_PIN_ERROR": Send it to the interface.
            # "FORBIDDEN": There's an issue with the MAC address.
            if response["reason"].lower() == "forbidden":
                # TODO: Must communicate with screen to debug this!
                logger.error(
                    f"Forbidden. Duplicate MAC problem!\nTerminating MAC: "
                    f"{self.mac}\n\n"
                )

            if response["reason"].lower() == "email_pin_error":
                self.creds.pin = None
                self.force_reconnect = True # kill the watchdog thread right away
            
            await self.socket.disconnect()
            self._update_state(_ConnectState.DISCONNECTED)
            return

        logger.info("Polar _on_register_response success.")
        logger.debug(f"Polar serial number: {response['serialNumber']}")
        self.creds.polar_sn = response["serialNumber"]
        await self.creds.save()
        self.last_connection_error = None
        await self._maybe_publish_status_object()
        logger.info(f"Successfully registered with Polar Cloud. Serial: {self.creds.polar_sn}")
        await self._force_reconnect()

    async def _register(self) -> None:
        """
        Send register request. Note this can only be called after a keypair
        has been received and stored.
        """
        logger.info("Polar _register.")
        data = {
            "mfg": "bambu",
            "email": self.creds.username,
            "pin": self.creds.pin,
            "publicKey": self.creds.public_key,
            "mfgSn": serial_number(),
            "myInfo": {"MAC": self.mac},
        }
        await self.socket.emit("register", data)

    async def _status_update(self):
        """
        Translate status code from printer into status code to return. Set
        self.status appropriately.

        Codes from the printer:
        TaskStage: We'll ignore this; just here for completeness.
          0: INITING
          1: WAITING
          2: WORKING
          3: PAUSED
        TaskState
          0: IDLE
          1: SLICING
          2: PREPARE
          3: RUNNING
          4: FINISH
          5: FAILED
          6: PAUSE

        Codes to return to the server:
        0   Ready; printer is idle and ready to print
        1   Serial; printer is printing a local print over its serial connection
        2   Preparing; printer is preparing a cloud print (e.g., slicing)
        3   Printing; printer is printing a cloud print
        4   Paused; printer has paused a print
        5   Postprocessing; printer is performing post-printing operations
        6   Canceling; printer is canceling a print from the cloud
        7   Complete; printer has completed a print job from the cloud
        8   Updating; printer is updating its software
        9   Cold pause; printer is in a "cold pause" state
        10  Changing filament; printer is in a "change filament" state
        11  TCP/IP; printer is printing a local print over a TCP/IP connection
        12  Error; printer is in an error state
        13  Disconnected; controller's USB is disconnected from the printer
        14  Door open; unable to start or resume a print
        15  Clear build plate; unable to start a new print

        For now, states 5, 6, 8, 9, 10, 11, 13, 14, and 15 will be ignored.
        There's no equivalent to "canceling", so forget 6.
        11 is the same as 1
        TODO: 14 should soon be capturable?
        TODO: 15 **really, really** needs to be dealt with.

        When a print is cancelled it goes to FAILED or if there's an error we'll
        report an error for 2 mins. then return to IDLE.

        Likewise, FINISHED returns to IDLE after two mins.
        """
        prev_status = self.status
        task_state = self.daemon.mqtt.latest_print_status.get("gcode_state", "IDLE")
        # task_stage = self.daemon.mqtt.latest_print_status.get("mc_print_stage", "0")
        # logger.debug(f"Polar  *** job id: {self.job_id}, status: {task_state}")
        logger.info(
            f"Polar prev status: {self.status}; "
            f"task_state: {task_state}; "
            f"time finished: {datetime.datetime.now() - self.time_finished}"
        )
        # Note we don't change self.status until after we've determined the printer
        # state because we're tracking the previous status.
        match self.STATE_TO_POLAR_STATUS[task_state]:
            case 0: # IDLE
                if self.status != 0:
                    logger.info(
                        f"Polar calling _job; prev status: {self.status}; "
                        f"task_state: {task_state}"
                    )
                    await self._job("completed")
                self.status == 0
            case 1 | 2 | 3: # SLICING, PREPARING, RUNNING
                # Printing or preparing
                if self.job_id in {"0", "123"}:
                    """
                    This is a local job.
                    _on_print() sets job_id to BAMBUxxxx. If it wasn't set, then
                    it's a local job. Set job_id to "123" bc eventually _job() will
                    need to send back a job_id. job_id will be reset to "0" in _job().
                    """
                    self.status = 1  # Local print
                    self.job_id = "123"
                else:
                    self.status = 3  # Cloud print
            case 4: # FINISHING
                # Printer is paused.
                self.status = 4
            case 7 | 12: # FINISH, FAIL
                if self.status not in {0, 6, 7, 12}:
                    # We just switched to an error or finished state from printing.
                    # Recall the error could be from cancelling, in which case
                    # status 6 is set in `_cancel()`.
                    # In that case track when we made the switch.
                    # Switch status to match current.
                    # Note that 0 is a special case, where we're reporting IDLE
                    # but the printer thinks it's failed.
                    self.time_finished = datetime.datetime.now()
                    self.status = self.STATE_TO_POLAR_STATUS[task_state]
                    logger.info(
                        "Polar: just switched to failed. "
                        f"{self.time_finished}"
                    )
                elif (
                    self.status in {6, 7, 12}
                    and datetime.datetime.now() - self.time_finished
                    > datetime.timedelta(seconds=120)
                ):
                    # We've been in an error or finished state for two mins. Send
                    # job completed and switch status to idle.
                    logger.info(
                        "Polar: end failed state. "
                        f"{datetime.datetime.now() - self.time_finished}"
                    )
                    self.status = 0
                    await self._job("completed")
                elif self.status == 0:
                    # Printer has been returning IDLE even though its internal
                    # state is FAILED or FINISHED. Remain in IDLE.
                    if self.STATE_TO_POLAR_STATUS[task_state] == 7:
                        logger.info("Polar: printer in FINISHED; remain in IDLE.")
                    else:
                        logger.info("Polar: printer in FAILED; remain in IDLE.")
                # Do nothing if we're in 6, 7, or 12 and time isn't yet elapsed.

    async def _status(self) -> None:
        """
        Send a status message every 10 seconds when printing. Also trigger
        sending of image every 20 seconds.

        All fields but serialNumber and status are optional.
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
        """
        capture_image = True
        while True:

            await self._status_update()

            if self.daemon.mqtt.latest_print_status.get("mc_percent", 0) < 5:
                # At this point we can guess the total print time. It'll possibly
                # be off by a little. But the mqtt doesn't have a value for total
                # time that I can find.
                self.estimated_print_time = self.daemon.mqtt.latest_print_status.get(
                    "mc_remaining_time", 0
                )
            # Notes: The logic around time is complicated. Maybe I should move
            # this to another fn? All these weird things that rely on the status
            # bug me. There's got to be a better way.
            time_used = datetime.datetime.now() - self.start_time
            if self.status == 0:
                # In this case there's no print so these numbers should be reset.
                self.estimated_print_time = 0
                self.start_time = datetime.datetime.now()
                time_used = datetime.timedelta(seconds=0)
            if (datetime.datetime.now() - self.last_ping).total_seconds() <= 5:
                # Don't do extra status updates.
                return
            data = {
                "tool0": self.daemon.mqtt.latest_print_status.get("nozzle_temper", 0),
                "bed": self.daemon.mqtt.latest_print_status.get("bed_temper", 0),
                "chamber": self.daemon.mqtt.latest_print_status.get(
                    "chamber_temper", 0
                ),
                "targetTool0": self.daemon.mqtt.latest_print_status.get(
                    "nozzle_target_temper", 0
                ),
                "targetBed": self.daemon.mqtt.latest_print_status.get(
                    "bed_target_temper", 0
                ),
                # TODO: targetChamber isn't in mqtt?
                # "targetChamber": self.daemon.mqtt.latest_print_status.get("", "0"),
                "serialNumber": self.creds.polar_sn,
                "status": self.status,
                "startTime": self.start_time.isoformat(),
                "estimatedTime": int(self.estimated_print_time) * 60,
                "printSeconds": time_used.total_seconds(),
                "jobId": self.job_id,
                "progressDetail": (
                    f"Printing Job: {self.file_name} "
                    "Percent Complete: "
                    f"{self.daemon.mqtt.latest_print_status.get('mc_percent', 0)}%"
                ),
            }
            try:
                await self.socket.emit("status", data)
                # logger.info(
                #     f"Polar status update {self.status} {datetime.datetime.now()}"
                # )
                self.last_ping = datetime.datetime.now()

                if capture_image:
                    # Capture and upload a new image every other status
                    # update -- but swallow this exception if it goes wrong.
                    try:
                        cam = AioRtspReceiver()
                        jpeg = await cam.receive_jpeg()

                        if self.status in [0, 8, 9, 10, 15]:
                            # In these cases send idle image.
                            # (TODO: are these all the cases for idle?)
                            await self._upload_jpeg("idle", jpeg)
                        elif self.status != 11:
                            await self._upload_jpeg("printing", jpeg)
                    except Exception as e:
                        logger.error(f"failed to capture camera image: {e}")
                # Next time through loop it will capture (or not).
                capture_image = not capture_image

                if self.connect_state != _ConnectState.ESTABLISHED:
                    return
                # We only feed the watchdog here if we successfully sent status.
                self._update_state(_ConnectState.ESTABLISHED)
            except Exception as e:
                logger.error(f"emit status failed: {e}")
                if str(e) == "/ is not a connected namespace.":
                    # This seems to be a python socketio bug/feature?
                    # In any case, recover by reconnecting.
                    logger.info("reconnecting to attempt to recover connected namespaces")
                    await self._force_reconnect()
                    return  # Or else we'll starting sending too many updates.
            if self.status != "0":
                await asyncio.sleep(10)
            else:
                # Longer pause when idle.
                await asyncio.sleep(30)
        logger.debug("Polar status ending.")

    async def _upload_jpeg(self, which_state, jpeg) -> None:
        """
        Upload an image to Polar Cloud's S3. The url varies for idle or printing
        images. All the connection info is stored in self.printing_cam_stream
        and self.idle_cam_stream.
        """
        logger.info("Polar _upload_jpeg")
        if which_state not in ["idle", "printing"]:
            return
        if which_state == "idle":
            this_vars = self.idle_cam_stream
        else:
            this_vars = self.printing_cam_stream

        if this_vars["expiration_time"] - time.time() < 300:
            # There are fewer than five mins before the upload url expires;
            # get a new one.
            await self._get_url(which_state)

        if 'url' not in this_vars:
            logger.warning("no URL yet to upload jpeg")
            return

        # Now do actual upload.
        # logger.debug(f"Polar AWS form data {this_vars['form_data']}")
        
        data = aiohttp.FormData()
        for k,v in this_vars['form_data'].items():
            data.add_field(k, str(v))
        data.add_field('file', jpeg, filename='frame_0.jpg', content_type='image/jpeg')
        
        async with aws_http_session.post(this_vars["url"], data=data) as response:
            # Process the response
            # logger.debug(f"upload response: {response}")
            response_data = await response.text()
        logger.debug(f"Attempted image uploaded: {response_data}")

    async def _on_delete(self, response, *args, **kwargs) -> None:
        """
        Printer has been deleted from Polar Cloud. Remove all identifying information
        from card. The current print should finish. Disconnect socket so that
        username and PIN don't keep being requested and printer doesn't reregister.
        """
        logger.info("Polar _on_delete")
        if response["serialNumber"] != self.creds.polar_sn:
            return

        await self.creds.wipe()
            
        # we are done; disconnect and shut down the watchdog so that we do not reconnect
        await self._force_reconnect()

    async def _job(self, status):
        """
        Send job response to Polar Cloud, letting it know a job has finished.
        Also reset job_id to "0", which is the default when nothing's printing.
        """
        logger.info(f"\n\n*** Polar _job {status} {self.job_id} ***\n")
        data = {
            "serialNumber": self.creds.polar_sn,
            "jobId": self.job_id,
            "state": status,  # "completed" | "canceled"
            # Next two when we get more features implemented
            # "printSeconds": integer,              // integer, optional
            # "filamentUsed": integer               // integer, optional
        }
        self.start_time = datetime.datetime.now()
        self.estimated_print_time = 0
        # I can reset job_id here because I only call _job() when a job
        # has completed.
        self.job_id = "0"
        self.file_name = ""
        await self.socket.emit("job", data)

    async def _on_print(self, data, *args, **kwargs):
        """Download file to printer, then send to print."""
        logger.info("Polar _on_print")
        self.job_id = data["jobId"]
        if data.get("serialNumber", None) != self.creds.polar_sn:
            logger.debug("Polar serial numbers don't match.")
            await self._job("canceled")
            return
        # TODO: add recovery here if still printing?

        logger.info(f"Polar print incoming data: {data}")
        path = "/tmp/x1plus" if is_emulating() else "/sdcard"
        # Get extension from url, then make sure the file name has the correct
        # extension. If extension is missing print will fail.
        self.file_name = data["jobName"]
        extension = os.path.splitext(data["gcodeFile"])[1]
        logger.info(f"Polar print file extension: {extension}")
        printer_action = "gcode_file"
        if extension == ".3mf":
            printer_action = "3mf_file"
        # if not self.file_name.endswith(extension):
        #     self.file_name += extension
        await self._download_file(path, self.file_name, data["gcodeFile"])
        location = os.path.join(path, self.file_name)
        self.start_time = datetime.datetime.now()
        await self._printer_action(printer_action, location)

    async def _download_file(self, path, file_name, url):
        """
        Adapted/stolen from ota.py. Maybe could move to utils?
        `path` is the path where `file_name` will exist. `file_name` is the
        file name of the saved file. `url` is the url of the upstream S3 file.
        """
        try:
            os.makedirs(path, mode=0o755, exist_ok = True)
            dest = os.path.join(path, file_name)
            logger.info("Polar _download_file")
            logger.debug(f"Polar downloading {url} to {dest}")
            with open(dest, "wb") as f:
                timeout = aiohttp.ClientTimeout(connect=5, total=900, sock_read=10)
                async with aiohttp.ClientSession(
                    connector=aiohttp.TCPConnector(ssl=ssl_ctx), timeout=timeout) as session:
                    async with session.get(url) as response:
                        response.raise_for_status()
                        async for chunk in response.content.iter_chunked(131072):
                            f.write(chunk)
        except:
            try:
                os.unlink(dest)
            except:
                pass
            raise
        logger.info(f"Polar _download_file success: {os.path.getsize(dest)}")

    async def _on_pause(self, data, *args, **kwargs) -> None:
        logger.info("Polar _on_pause")
        await self._printer_action("pause")

    async def _on_resume(self, data, *args, **kwargs) -> None:
        logger.info("Polar _on_resume")
        await self._printer_action("resume")

    async def _on_cancel(self, data, *args, **kwargs) -> None:
        logger.info("Polar _on_cancel")
        self.status = 6
        await self._printer_action("stop")

    async def _on_url_response(self, data, *args, **kwargs) -> None:
        """
        Upon receiving url response set appropriate instance variables. Response
        object is as follows:
        {
            "serialNumber": "printer-serial-number",
            "type": "idle" | "printing" | "timelapse",
            "expires": seconds-until-url-expires,
            "maxSize": max-file-size-in-bytes,
            "contentType": "image/jpeg" | "video/mp4",
            "method": "post",
            "url": "string",
            "fields": { // POST form data
                "bucket": "S3-bucket-name",
                "key": "bucket-key-name",
                "acl": "public-read",
                "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
                "X-Amz-Credential": "AWS-credential",
                "X-Amz-Date": "time-stamp",
                "Policy": "encrypted-policy",
                "X-Amz-Signature": "policy-signature"
            }
        }
        """
        logger.info(f"Polar _on_url_response")
        if data["status"] != "SUCCESS":
            logger.error(f"Polar get_url failed: {data['message']}")
            return
        
        if data["serialNumber"] != self.creds.polar_sn:
            logger.error("Polar get_url failed wrong serial number.")
            return

        if data["type"] == "idle":
            cam_dict = self.idle_cam_stream
        elif data["type"] == "printing":
            cam_dict = self.printing_cam_stream
        cam_dict["expiration_time"] = time.time() + int(data["expires"])
        cam_dict["url"] = data["url"]
        cam_dict["form_data"] = data["fields"].copy()
        # cam_dict["form_data"]["X-Amz-Expires"] = data["expires"]

    async def _get_url(self, idle_or_print="printing"):
        """
        Request the image upload url from Polar Cloud. `idle_or_print` _must_
        be either "printing" or "idle".
        """
        logger.info(f"Polar _get_url {idle_or_print}")
        if idle_or_print not in ["idle", "printing"]:
            logger.error("Neither idle not printing was specified in getUrl request.")
        request_data = {
            "serialNumber": self.creds.polar_sn,
            "method": "post",
            "type": idle_or_print,
            "jobId": self.job_id,
        }
        await self.socket.emit("getUrl", request_data)

    async def _printer_action(self, which_action, print_file="") -> None:
        """
        Make dbus call to print, pause, cancel, resume. If printing a 3mf file
        we need the print_file name and the plate to print.
        """
        logger.info(f"Polar _printer_action {which_action} {print_file}")
        request_json = {}
        if which_action == "3mf_file":
            request_json = {
                "print": {
                    "sequence_id": "0",
                    "command": "project_file",
                    "param": "Metadata/plate_1.gcode",
                    "project_id": "0",
                    "profile_id": "0",
                    "task_id": "0",
                    "subtask_id": "0",
                    "subtask_name": "",
                    "url": f"file:///mnt{print_file}",
                    "md5": "",
                    "timelapse": False,
                    "bed_type": "auto",
                    "bed_levelling": True,
                    "flow_cali": True,
                    "vibration_cali": True,
                    "layer_inspect": True,
                    "ams_mapping": "",
                    "use_ams": False,
                }
            }
        else:
            request_json = {
                "print": {
                    "sequence_id": "0",
                    "command": f"{which_action}",
                    "param": f"{print_file}",
                }
            }
        await self.daemon.mqtt.publish_request(request_json)

_daemon = None
def load(daemon):
    global _daemon
    _daemon = daemon
    setattr(daemon, "polar_cloud", PolarPrintService(daemon=daemon))

def start():
    asyncio.create_task(_daemon.polar_cloud.task())
