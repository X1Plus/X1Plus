# Always invoke this with python3 -m x1plus.services.syslog_shim.

import os
import sys
import re
import json
from collections import namedtuple
import x1plus.dds
import logging


log_path = (
    "/mnt/sdcard/log/"
    if os.path.exists("/tmp/.syslog_to_sd") and os.path.exists("/mnt/sdcard/log/")
    else "/tmp/"
)
shim_log = logging.getLogger(__name__)
log_path = os.path.join(log_path,"syslog.log")


# Define a basic mechanism for "do something when you see some particular
# type of line in the syslog".
RegexHandler = namedtuple("RegexHandler", ["regex", "callback"])

dds_publish_mc_print = x1plus.dds.publisher("device/report/mc_print")

class TailLog:
    def __init__(self, filepath, seek_end = True, interval = 1.0):
        self.filepath = filepath
        self.fd = None
        self.ino = None
        self.seek_end = seek_end
        self.buf = ""
        self.interval = interval

    def readline(self):
        """
        Read a line, non-blocking (returns None if no line is ready).
        """
            
        # Has the inode changed (i.e., the logs have rotated?)
        if os.stat(self.filepath).st_ino != self.ino:
            if self.fd:
                self.buf += self.fd.read() + "\n"
                self.fd.close()
            print(f"TailLog: reopened {self.filepath} and finished up {len(self.buf)} bytes", file = sys.stderr)
            self.fd = open(self.filepath, "r", encoding="utf-8", errors="replace")
            self.ino = os.fstat(self.fd.fileno()).st_ino

        # Grab some data from the buffer; if it's the first go-around, throw
        # all the data out, though.
        self.buf += self.fd.read()
        if self.seek_end:
            self.buf = ""
            self.seek_end = False
            
        # Grab the first line if there is one, and leave everything else
        # behind.
        if "\n" not in self.buf:
            return None
        line, self.buf = self.buf.split("\n", 1)
        return line
        
    def lines(self):
        """
        Generator to infinitely tail a log file.
        """
        while True:
            line = self.readline()
            if not line:
                time.sleep(self.interval)
            else:
                yield line
                
def RegexParser(regex, format):
    """
    A RegexHandler that takes a reformatter lambda and wraps it in a DDS publisher.
    """

    def fn(match):
        obj = format(match)
        print(f"Publishing matched object: {obj}", file=sys.stderr)
        shim_log.info(f"[x1p] - {json.dumps(obj)}")
        dds_publish_mc_print(json.dumps(obj))

    return RegexHandler(re.compile(regex), fn)

# Paired with X1Plus.BedMeshCalibration and X1Plus.ShaperCalibration.
syslog_data = [
    # Bed Mesh data
    RegexParser(
            r".*\[BMC\]\s*X(-?\d+\.\d*)\s*Y(-?\d+\.\d*),z_c=\s*(-?\d+\.\d*)",
        lambda match: {
            "command": "mesh_data",
            "param": {
                "x": float(match.group(1)),
                "y": float(match.group(2)),
                "z": float(match.group(3)),
            },
        },
    ),
    # Vibration compensation
    RegexParser(
            r".*\[BMC\]\s*f=(-?\d+\.\d*),\s*a=(-?\d+\.\d*),\s*ph=\s*(-?\d+\.\d*),\s*err\s*(\d+)",
        lambda match: {
            "command": "vc_data",
            "param": {
                "f": float(match.group(1)),
                "a": float(match.group(2)),
                "ph": float(match.group(3)),
                "err": int(match.group(4)),
            },
        },
    ),
    # Vibration compensation
    RegexParser(
            r".*\[BMC\]\s*wn(-?\d+\.\d*),ksi(-?\d+\.\d*),\s*pk(-?\d+\.\d*),l(-?\d+\.\d*),h(-?\d+\.\d*)",
        lambda match: {
            "command": "vc_params",
            "param": {
                "wn": float(match.group(1)),
                "ksi": float(match.group(2)),
                "pk": float(match.group(3)),
                "l": float(match.group(4)),
                "h": float(match.group(5)),
            },
        },
    ),
    # Vibration compensation
    RegexParser(
        r".*\[BMC\]\s*(M975\s*S1)",
        lambda match: {"command": "vc_enable"},
    ),
	# K values
    RegexParser(
            r".*\[BMC\]\s*M900\s*power\s*law:K(-?\d+\.?\d*),N(-?\d+\.?\d*)",
        lambda match: {
            "command": "k_values",
            "param": {
                "K": float(match.group(1)),
                "N": float(match.group(2)),
            },
        },
    ),
   # z offset
    RegexParser(
        r".*z_trim:(-?\d+\.\d*)",
        lambda match: {
            "command": "z_offset",
            "param": {
                "z_offset": float(match.group(1)),
            },
        },
    ),
    # detected build plate id
    RegexParser(
        r".*detected\s*build\s*plate\s*id:\s*(-?\d)",
        lambda match: {
            "command": "build_plate_id",
            "param": {
                "id": int(match.group(1)),
            },
        },
    ),
    # bed strain sensitivity
    RegexParser(
        r".*strain\s*(\d)*\s*sensitivity\s*=\s*(-?\d+\.?\d*),p=(-?\d+\.\d*),Vs=(-?\d+\.\d*)",
        lambda match: {
            "command": "bed_strain",
            "param": {
                "sensitivity": float(match.group(1)),
                "p": float(match.group(2)),
                "Vs": float(match.group(3)),
            },
        },
    ),
    # M1005 skew factor
    RegexParser(
        r".*M1005:(new|current)\s*XY_comp_ang\s*=\s*(-?\d+\.?\d*)",
        lambda match: {
            "command": "M1005",
            "param": {
                "skew":  match.group(1),
                "XY_comp_ang":  float(match.group(2)),
            },
        },
    ),
]


def main():
    tail_syslog = TailLog(log_path)
    for line in tail_syslog.lines():
        for handler in syslog_data:
            match = handler.regex.match(line)
            if match:
                handler.callback(match)


if __name__ == "__main__":
    import setproctitle
    setproctitle.setproctitle(__spec__.name)
    try:
        main()
    except:
        x1plus.dds.shutdown()
        raise
