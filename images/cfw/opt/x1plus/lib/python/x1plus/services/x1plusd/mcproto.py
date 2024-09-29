import re
import json
import asyncio

import struct
import logging
import x1plus.utils
from .dbus import *

logger = logging.getLogger(__name__)

class MCMessage():
    COMMANDS = {}
    DEVICES = {
        3: "MC",
        6: "AP",
        7: "AMS",
        8: "TH",
    	9: "AP2",
        0xE: "AHB",
        0xF: "EXT",
        0x13: "CTC",
    }
    
    @classmethod
    def register(cls, cmd_set, cmd_id, handler = None):
        """
        Can either be used as a simple register function, or as a decorator
        if target is not passed in.
        """
        
        def decorator(handler):
            cls.COMMANDS[(cmd_set, cmd_id)] = handler
            return handler

        if handler is None:
            return decorator
        else:
            decorator(handler)

    def __init__(self, raw):
        if raw[0] != 0x3D:
            raise ValueError("MC message did not start with =")
        self.raw = raw
        self.flags = raw[1]
        self.flags_is_initiator   = self.flags & 0x4
        self.flags_wants_response = self.flags & 0x1
        # i.e., flags == 4 is "posted message"; flags == 5 is "RPC wants response"; flags == 0 is "here is your response"
        self.sequence = raw[2] | (raw[3] << 8)
        packet_len = raw[4] | (raw[5] << 8)
        header_cksm = raw[6] # currently unused
        
        packet_data = raw[7:packet_len-2]
        packet_cksm = (raw[packet_len-1] << 8) | (raw[packet_len-2] << 0) # currently unused, since this always comes from forward
        
        self.addr_to   = (packet_data[0] << 8) | (packet_data[1] << 0)
        self.addr_from = (packet_data[2] << 8) | (packet_data[3] << 0)
        
        self.cmd_id  = packet_data[4]
        self.cmd_set = packet_data[5]
        self.payload = packet_data[6:]
        self.decoded = None

        cmdhandler = self.COMMANDS.get((self.cmd_set, self.cmd_id), None)
        if callable(cmdhandler):
            self.decoded = cmdhandler(self)
        
    def __str__(self):
        return "<MCMessage {} #{} {} -> {}: {}>".format(
            "REQ" if self.flags_is_initiator else "RSP",
            self.sequence,
            self.DEVICES.get(self.addr_from, f"unknown[{self.addr_from}]"),
            self.DEVICES.get(self.addr_to,   f"unknown[{self.addr_to}]"),
            self.decoded if self.decoded else self.COMMANDS.get((self.cmd_set, self.cmd_id), f'unknown cmd ({self.cmd_set}, {self.cmd_id})')
        )


MCMessage.register(1, 1, "ping")
MCMessage.register(1, 3, "get_version")
MCMessage.register(1, 4, "sync_timestamp")
MCMessage.register(1, 6, "mcu_upgrade")
MCMessage.register(1, 8, "mcu_hms")
MCMessage.register(1, 9, "factory_reset")

MCMessage.register(2, 5, "gcode_execute_state")

@MCMessage.register(2, 6)
class MC_gcode_request: # no official name for this one!
    def __init__(self, msg):
        (self.seq, ) = struct.unpack("<L", msg.payload[:4])
        self.buf = msg.payload[4:]
    
    def __str__(self):
        return f"<gcode_request seq {self.seq}, buf {self.buf}>"

    def should_log(self):
        return False

@MCMessage.register(2, 9)
class MC_mcu_display_message:
    def __init__(self, msg):
        self.msg = msg.payload #.decode()
    
    def __str__(self):
        return f"<mcu_display_message: \"{self.msg}\">"

    def should_log(self):
        return False

MCMessage.register(2, 10, "vosync")
MCMessage.register(2, 11, "gcode_ctx")
MCMessage.register(2, 12, "mc_state")
MCMessage.register(2, 15, "link_ams_report")
MCMessage.register(2, 17, "ack_tray_info")
MCMessage.register(2, 22, "gcode_line_handle")
MCMessage.register(2, 23, "ams_mapping")
MCMessage.register(2, 24, "ams_tray_info_write_ack")
MCMessage.register(2, 25, "ams_user_settings")
MCMessage.register(2, 27, "hw_info_voltage")
MCMessage.register(2, 28, "link_ams_tray_consumption_ack")
MCMessage.register(2, 29, "pack_get_part_info_ack")
MCMessage.register(2, 34, "extrusion_result_update")
MCMessage.register(2, 36, "fila_ams_get")
MCMessage.register(2, 37, "mc_get_skipped_obj_list")


@MCMessage.register(3, 1)
class MC_M971:
    # C7 O0 or C8 O0: "offline rgb fusion"
    # C9 O0: offline bgr image
    # xx O0: offline capture image
    # O1: online capture
    #   O1 C1: online cali rgb
    #   O1 C2: online cali laser
    #   O1 C5: online cali adaptive exposure
    #   O1 xx: online capture
    # xx C10 or xx C11: "offline capture timeline image idx="
    # xx C12: "offline capture chamber image"
    #
    # M971 C99 could work, but sometimes the MC reports all M971s as C0 O0,
    # which definitely is not going to fly
    def __init__(self, msg):
        if msg.flags_is_initiator:
            (self.seq, self.sty, self.on, self.num) = struct.unpack("<HBBL", msg.payload)
            self.rv = None
        else:
            (self.seq, self.rv, self.sty, self.on, self.num) = struct.unpack("<HHBBL", msg.payload)
    
    def __str__(self):
        return f"<M971 seq {self.seq}, C{self.sty} O{self.on} P{self.num}, response {self.rv}>"
    
    def should_log(self):
        return True

MCMessage.register(3, 2, "M972")
      # has to do with camera clarity, "calculate intrinsic params"
      # payload_len < 6
      #   0, 1: seq
      #   2: "on"
      #   3: "data_num"
MCMessage.register(3, 5, "M963")
      # during handeye calibration sequence, syntax "M963 S1"
      # "calculate extrinsic params"
MCMessage.register(3, 7, "M969")
      # syntax "M969 S1 N3 A2000" or "M969 S0 ; turn off scanning"
      # "calculate extruder bandwidth"
MCMessage.register(3, 6, "M965_b")
MCMessage.register(3, 9, "M967")
MCMessage.register(3, 11, "M973") # "ctask set camera exposure"
      # M973 S6 P0; use auto exposure for horizontal laser by xcam
      # M973 S6 P1; use auto exposure for vertical laser by xcam
      # M973 S3 P14
      # M973 S3 P1 ; camera start stream
      # M973 S1
      # M973 S2 P0
      # M973 S4 ; turn off scanner
MCMessage.register(3, 14, "M965") # "calculate heatbed height measurement" or "calculate baseline heatbed measurement"

@MCMessage.register(3, 49)
class MC_M976:
    # "detection control"
    # M976 S1 P1 ; scan model before printing 2nd layer
    # S0 = stop scanning inner layer
    # S1 = start scanning normal layer
    # S2 = first layer inspection
    # S3 = void printing detection
    # S4 = enable nozzlecam capture
    # hotbed scan before print: M976 S2 P1
    # register void printing detection: M976 S3 P2
    #
    # M976 S99 does work but could cause a hiccup?
    def __init__(self, msg):
        if msg.flags_is_initiator:
            (self.seq, self.cmd, self.num) = struct.unpack("<HBL", msg.payload)
            self.rv = None
        else:
            (self.seq, self.rv) = struct.unpack("<HL", msg.payload)
            self.cmd = None
            self.num = None
    
    def __str__(self):
        return f"<M976 seq {self.seq}, S{self.cmd} P{self.num}, response {self.rv}>"
    
    def should_log(self):
        return True

MCMessage.register(3, 50, "M977")
      # "detection single layer registration"
MCMessage.register(3, 51, "M978")
      # "calculate continuous layer detection"
MCMessage.register(3, 52, "M981")
      # "calculate spaghetti detection"
      # M981 S1 P20000 ;open spaghetti detector
MCMessage.register(3, 53, "M991")
      # "layer change event"
MCMessage.register(3, 81, "M987")
MCMessage.register(3, 82, "SENSORCHECK")
      # "set sensor detection"

MCMessage.register(4, 1, "set_module_sn")
MCMessage.register(4, 2, "get_module_sn")
MCMessage.register(4, 3, "inject_module_key")
MCMessage.register(4, 4, "get_inject_status")
MCMessage.register(4, 5, "mcu_reboot")
MCMessage.register(4, 6, "send_to_amt_core")
MCMessage.register(4, 7, "set_module_lifecycle")
MCMessage.register(4, 8, "get_module_lifecycle")
MCMessage.register(4, 10, "inject_productcode")
MCMessage.register(4, 11, "get_productcode")

###

class MCProtoParser():
    """
    MC protocol parser service.
    
    MCProtoParser handles DBus signals sent over by forward, as glued in by
    forward_shim.  It parses all outbound messages to the MC, as well as
    inbound messages, and parcels out things that it needs to care about --
    for instance, it does its own parsing on all outbound Gcode (to find
    x1plus metadata), and listens for M976s to trigger X1Plus-specific
    behavior.
    
    This comes at a cost -- about 15% of a core of CPU (ugh!).  But luckily
    we seem to have a fair bit of that to spare.  Some day, some of this
    parsing may want to move to forward_shim to filter only the packets that
    we want...
    """
    
    def __init__(self, daemon):
        self.daemon = daemon
        self.rdbuf = bytearray()
        self.gcode_last_seq = None
        self.gcode_remaining = b''
        self.gcode_x1plus_defs = {}
        self.active_action = None
    
    GCODE_X1PLUS_DEF_RE = re.compile(rb";\s*x1plus define\s*(\d+)\s+(.+)")

    async def trigger_action(self, action):
        """
        Trigger an action to execute in the background, with only one MC protocol action allowed to run at a time.
        """
        if self.active_action:
            if not self.active_action.done():
                logger.warning("new mcproto action being triggered, but the previous action is not complete; canceling it!")
            self.active_action.cancel()
            self.active_action = None
        self.active_action = asyncio.create_task(self.daemon.actions.execute(action))

    async def handle_msg(self, msg):
        if msg.decoded and msg.decoded.should_log():
            logger.info(f"MC message: {msg}")

        if type(msg.decoded) == MC_gcode_request:
            if msg.flags_is_initiator:
                # request from MC to AP for Gcode
                return
            # AP is sending Gcode to MC

            if msg.decoded.seq == 0:
                # this is the first Gcode chunk, clear all Gcode parsing state
                self.gcode_last_seq = None
                self.gcode_remaining = b''
                self.gcode_x1plus_defs = {}
            
            if msg.decoded.seq == self.gcode_last_seq:
                # retransmission, ignore
                return
            
            lines = (self.gcode_remaining + msg.decoded.buf).split(b'\n')
            self.gcode_remaining = lines[-1]
            for line in lines[:-1]:
                m = self.GCODE_X1PLUS_DEF_RE.match(line)
                if not m:
                    continue
                id = int(m[1])
                try:
                    val = json.loads(m[2])
                except Exception as e:
                    logger.error(f"x1plus define {id} (\"{m[2]}\") had invalid JSON: {e.__class__.__name__}: \"{e}\"")
                    continue
                logger.info(f"found x1plus define {id} -> {val}")
                self.gcode_x1plus_defs[id] = val
        
        if type(msg.decoded) == MC_M976:
            if msg.decoded.cmd != 99:
                return
            if msg.decoded.num not in self.gcode_x1plus_defs:
                logger.error(f"M976 {msg.decoded.num} did not have corresponding x1plus define")
                return
            logger.info(f"M976 X1Plus event triggered {self.gcode_x1plus_defs[msg.decoded.num]}")
            await self.trigger_action(self.gcode_x1plus_defs[msg.decoded.num])

    async def handle_serial_port_write(self, data):
        try:
            await self.handle_msg(MCMessage(data))
        except Exception as e:
            logger.error(f"exception parsing outgoing MC message: {e.__class__.__name__}: \"{e}\"")
    
    async def handle_serial_port_read(self, data):
        self.rdbuf += data
        while len(self.rdbuf) > 0:
            if self.rdbuf[0] != 0x3D:
                try:
                    first_byte = self.rdbuf.index(b'\x3d')
                    logger.warning(f"incoming MC protocol desync; skipped {first_byte} bytes, {self.rdbuf[:first_byte]}")
                    self.rdbuf = self.rdbuf[first_byte:]
                except:
                    logger.warning(f"incoming MC protocol desync; skipping at least {len(self.rdbuf)} bytes, {self.rdbuf}")
                    self.rdbuf = bytearray()
                    break
            
            assert self.rdbuf[0] == 0x3D
            if len(self.rdbuf) < 7:
                # not enough data to even read the packet header
                break
            packet_len = self.rdbuf[4] | (self.rdbuf[5] << 8)
            if len(self.rdbuf) < packet_len:
                # we do not have a full packet yet
                break

            # XXX: should check CRC on packet header to more quickly recover
            # from certain types of desync
            
            if packet_len < 1:
                # if packet_len were *zero*, we definitely were desynced;
                # consume the first byte in the hopes of getting back in
                # sync ASAP (maybe the sync was inside of the stuff that we
                # otherwise would consume if we consumed more than that). 
                # otherwise, since we consume packet_len bytes, we would end
                # up consuming no bytes at all and ending up in an infinite
                # loop!
                packet_len = 1
            
            packet = self.rdbuf[:packet_len]
            del self.rdbuf[:packet_len]

            if packet_len < 15:
                logger.warning(f"incoming MC protocol desync (packet too short); skipping a header")
                continue
            
            try:
                await self.handle_msg(MCMessage(packet))
            except Exception as e:
                logger.error(f"exception parsing incoming MC message: {e.__class__.__name__}: \"{e}\"")

    async def task(self):
        match = MatchRule(
            interface="x1plus.forward.mc", type="signal"
        )
        
        await Proxy(message_bus, self.daemon.router).AddMatch(match)
        with self.daemon.router.filter(match, bufsize=0) as queue:
            while True:
                dbus_msg = await queue.get()
                try:
                    if dbus_msg.header.fields[HeaderFields.member] == "SerialPortWrite":
                        await self.handle_serial_port_write(dbus_msg.body[0])
                    elif dbus_msg.header.fields[HeaderFields.member] == "SerialPortRead":
                        await self.handle_serial_port_read(dbus_msg.body[0])
                except Exception as e:
                    logger.error(f"exception handling signal {dbus_msg.header.fields[HeaderFields.member]}: {e.__class__.__name__}: \"{e}\"")
                