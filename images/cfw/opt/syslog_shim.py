import os, time, re, dds, sys
import json, logging
from logging.handlers import RotatingFileHandler
from collections import namedtuple
from logger.tail import TailLog


def make_logger(name, filename):
    formatter = logging.Formatter("%(asctime)s - %(message)s")
    handler = RotatingFileHandler(filename, maxBytes=1048576, backupCount=5)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
    return logger


calibration_log = make_logger(name="calibration", filename="/tmp/calibration.log")

# Define a basic mechanism for "do something when you see some particular
# type of line in the syslog".
RegexHandler = namedtuple("RegexHandler", ["regex", "callback"])

dds_publish_mc_print = dds.publisher("device/report/mc_print")


def RegexCalibrationHandler(regex, format):
    """
    A RegexHandler that takes a reformatter lambda and wraps it in a DDS publisher.
    """

    def fn(match):
        obj = format(match)
        print(f"Publishing matched object: {obj}", file=sys.stderr)
        calibration_log.info(f"[x1p] - {json.dumps(obj)}")
        dds_publish_mc_print(json.dumps(obj))

    return RegexHandler(regex, fn)


# Paired with X1Plus.BedMeshCalibration and X1Plus.ShaperCalibration.
calibration_handlers = [
    # Bed mesh calibration.
    RegexCalibrationHandler(
        regex=re.compile(
            r".*\[BMC\]\s*X(-?\d+\.\d*)\s*Y(-?\d+\.\d*),z_c=\s*(-?\d+\.\d*)"
        ),
        format=lambda match: {
            "command": "mesh_data",
            "param": {
                "x": float(match.group(1)),
                "y": float(match.group(2)),
                "z": float(match.group(3)),
            },
        },
    ),
    # Shaper calibration.
    RegexCalibrationHandler(
        regex=re.compile(
            r".*\[BMC\]\s*f=(-?\d+\.\d*),\s*a=(-?\d+\.\d*),\s*ph=\s*(-?\d+\.\d*),\s*err\s*(\d+)"
        ),
        format=lambda match: {
            "command": "vc_data",
            "param": {
                "f": float(match.group(1)),
                "a": float(match.group(2)),
                "ph": float(match.group(3)),
                "err": int(match.group(4)),
            },
        },
    ),
    RegexCalibrationHandler(
        regex=re.compile(
            r".*\[BMC\]\s*wn(-?\d+\.\d*),ksi(-?\d+\.\d*),\s*pk(-?\d+\.\d*),l(-?\d+\.\d*),h(-?\d+\.\d*)"
        ),
        format=lambda match: {
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
    RegexCalibrationHandler(
        regex=re.compile(r".*\[BMC\]\s*(M975\s*S1)"),
        format=lambda match: {"command": "vc_enable"},
    ),
    # Filament / linear advance calibration.
    RegexCalibrationHandler(
        regex=re.compile(
            r".*\[BMC\]\s*M900\s*power\s*law:K(-?\d+\.?\d*),N(-?\d+\.?\d*)"
        ),
        format=lambda match: {
            "command": "k_values",
            "param": {
                "K": float(match.group(1)),
                "N": float(match.group(2)),
            },
        },
    ),
]


def main():
    log_path = (
        "/mnt/sdcard/log/syslog.log"
        if os.path.exists("/tmp/.syslog_to_sd") and os.path.exists("/mnt/sdcard/log/syslog.log")
        else "/tmp/syslog.log"
    )

    tail_syslog = TailLog(log_path)
    for line in tail_syslog.lines():
        for handler in calibration_handlers:
            match = handler.regex.match(line)
            if match:
                handler.callback(match)


if __name__ == "__main__":
    try:
        main()
    except:
        dds.shutdown()
        raise
