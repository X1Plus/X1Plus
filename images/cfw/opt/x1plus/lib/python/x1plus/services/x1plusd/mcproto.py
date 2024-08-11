import os
import copy
from pathlib import Path
import json

import struct
import logging
import x1plus.utils
from .dbus import *

logger = logging.getLogger(__name__)

class MCMessage():
    COMMANDS = None # to be overridden below
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

    def __init__(self, msg):
        if msg.flags_is_initiator:
            (self.seq, self.sty, self.on, self.num) = struct.unpack("<HBBL", msg.payload)
            self.rv = None
        else:
            (self.seq, self.rv, self.sty, self.on, self.num) = struct.unpack("<HHBBL", msg.payload)
    
    def __str__(self):
        return f"<M971 seq {self.seq}, C{self.sty} O{self.on} P{self.num}, response {self.rv}>"

class MC_gcode_request:
    def __init__(self, msg):
        (self.seq, ) = struct.unpack("<L", msg.payload[:4])
        self.buf = msg.payload[4:]
    
    def __str__(self):
        return f"<gcode_request seq {self.seq}, buf {self.buf}>"

MCMessage.COMMANDS = {
    (1, 1): "ping",
    (1, 3): "get_version",
    (1, 4): "sync_timestamp",
    (1, 6): "mcu_upgrade",
    (1, 8): "mcu_hms",
    (1, 9): "factory_reset",
    (2, 5): "gcode_execute_state",
    (2, 6): MC_gcode_request, # no official name for this
    (2, 9): "mcu_display_message",
    (2, 10): "vosync",
    (2, 11): "gcode_ctx",
    (2, 12): "mc_state",
    (2, 15): "link_ams_report",
    (2, 17): "ack_tray_info",
    (2, 22): "gcode_line_handle",
    (2, 23): "ams_mapping",
    (2, 24): "ams_tray_info_write_ack",
    (2, 25): "ams_user_settings",
    (2, 27): "hw_info_voltage",
    (2, 28): "link_ams_tray_consumption_ack",
    (2, 29): "pack_get_part_info_ack",
    (2, 34): "extrusion_result_update",
    (2, 36): "fila_ams_get",
    (2, 37): "mc_get_skipped_obj_list",
    (3, 1): MC_M971,
    (3, 2): "M972",
      # has to do with camera clarity, "calculate intrinsic params"
      # payload_len < 6
      #   0, 1: seq
      #   2: "on"
      #   3: "data_num"
    (3, 5): "M963",
      # during handeye calibration sequence, syntax "M963 S1"
      # "calculate extrinsic params"
    (3, 7): "M969",
      # syntax "M969 S1 N3 A2000" or "M969 S0 ; turn off scanning"
      # "calculate extruder bandwidth"
    (3, 6): "M965_b",
    (3, 9): "M967",
    (3, 11): "M973", # "ctask set camera exposure"
      # M973 S6 P0; use auto exposure for horizontal laser by xcam
      # M973 S6 P1; use auto exposure for vertical laser by xcam
      # M973 S3 P14
      # M973 S3 P1 ; camera start stream
      # M973 S1
      # M973 S2 P0
      # M973 S4 ; turn off scanner
    (3, 14): "M965", # "calculate heatbed height measurement" or "calculate baseline heatbed measurement"
    (3, 49): "M976",
      # "detection control"
      # M976 S1 P1 ; scan model before printing 2nd layer
      # hotbed scan before print: M976 S2 P1
      # register void printing detection: M976 S3 P2
      # publishes a topic_ctasks to xcam/ctask_request, passed through directly as:
      #   b0_cmd = 3
      #   b0_id = 49
      #   ctask_cmd = 3
      #   ctask_cmd = 1
      #   seq = payload[0]
      #   data = payload
    (3, 50): "M977",
      # "detection single layer registration"
    (3, 51): "M978",
      # "calculate continuous layer detection"
    (3, 52): "M981",
      # "calculate spaghetti detection"
      # M981 S1 P20000 ;open spaghetti detector
    (3, 53): "M991",
      # "layer change event"
    (3, 81): "M987",
    (3, 82): "SENSORCHECK",
      # "set sensor detection"
    (4, 1): "set_module_sn",
    (4, 2): "get_module_sn",
    (4, 3): "inject_module_key",
    (4, 4): "get_inject_status",
    (4, 5): "mcu_reboot",
    (4, 6): "send_to_amt_core",
    (4, 7): "set_module_lifecycle",
    (4, 8): "get_module_lifecycle",
    (4, 10): "inject_productcode",
    (4, 11): "get_productcode",
}
 

class MCProtoParser():
    def __init__(self, daemon):
        self.daemon = daemon

    async def task(self):
        match = MatchRule(
            interface="x1plus.forward", member="MCSerialPortWrite", type="signal"
        )
        await Proxy(message_bus, self.daemon.router).AddMatch(match)
        with self.daemon.router.filter(match, bufsize=0) as queue:
            while True:
                dbus_msg = await queue.get()
                try:
                    msg = MCMessage(dbus_msg.body[0])
                    if msg.decoded:
                        logger.info(f"MC message: {msg}")
                except Exception as e:
                    logger.error(f"exception parsing MC message: {e.__class__.__name__}: \"{e}\"")
                