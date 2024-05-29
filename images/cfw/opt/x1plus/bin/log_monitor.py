import os
import re
import time
import json
import sys
import signal
import threading
import subprocess

# Patterns for log parsing
lock_pattern = re.compile(r'\[MCU\]\[BMC\]owner=1 lock! \[Free\]')
unlock_pattern = re.compile(r'\[MCU\]\[BMC\]owner=1 unlock!')
timestamp_pattern = re.compile(r'^\w{3} \d{2} \d{2}:\d{2}:\d{2}')
info_forward_pattern = re.compile(r'info forward\[\d+\]: ')
valid_line_pattern = re.compile(r'^\w{3} \d{2} \d{2}:\d{2}:\d{2} info forward\[\d+\]: \[(MCU\]\[BMC|gparser)\]')
log_path = "/mnt/sdcard/log/syslog.log" if os.path.exists("/tmp/.syslog_to_sd") and os.path.exists("/mnt/sdcard/log/") else "/tmp/syslog.log"

class TailLog:
    def __init__(self, filepath, seek_end=True, interval=1.0):
        self.filepath = filepath
        self.fd = None
        self.ino = None
        self.seek_end = seek_end
        self.buf = ""
        self.interval = interval
        self.running = True
        self._open_file()

    def _open_file(self):
        self.fd = open(self.filepath, "r", encoding="utf-8", errors="replace")
        self.ino = os.fstat(self.fd.fileno()).st_ino
        if self.seek_end:
            self.fd.seek(0, os.SEEK_END)

    def stop(self):
        self.running = False
        self.fd.close()

    def readline(self):
        if os.stat(self.filepath).st_ino != self.ino:
            self.buf += self.fd.read() + "\n"
            self.fd.close()
            self._open_file()

        self.buf += self.fd.read()
        if self.seek_end:
            self.buf = ""
            self.seek_end = False
        
        if "\n" not in self.buf:
            return None
        line, self.buf = self.buf.split("\n", 1)
        return line
    
    def lines(self):
        while self.running:
            line = self.readline()
            if not line:
                time.sleep(self.interval)
            else:
                yield line

def send_gcode(gcode_line):
    json_payload = {
        "print": {
            "command": "gcode_line",
            "sequence_id": "2001",
            "param": gcode_line
        }
    }
    mqtt_pub(json.dumps(json_payload))

def mqtt_pub(message):
    command = f"source /usr/bin/mqtt_access.sh; mqtt_pub '{message}'"
    subprocess.run(command, shell=True, check=True, executable='/bin/bash',
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def log_monitor(tail_syslog):
    capturing = False
    captured_lines = []
    try:
        for line in tail_syslog.lines():
            if lock_pattern.search(line):
                capturing = True
                captured_lines = []
                continue

            if capturing:
                if unlock_pattern.search(line):
                    capturing = False
                    output = ''.join(captured_lines).strip()
                    captured_lines = []
                    continue

                if valid_line_pattern.match(line):
                    line = timestamp_pattern.sub('', line)
                    line = info_forward_pattern.sub('', line)
                    print(line.replace("[MCU][BMC]","<br />"))
                    captured_lines.append(line)
    except Exception as e:
        print(f"Failed to monitor log file: {e}")

def user_interaction():
    gcode_input = input("<div><font color='#CACACA'>enter gcode</font>")
    send_gcode(gcode_input)
    time.sleep(2)

def signal_handler(sig, frame):
    print("Exiting...")
    tail_syslog.stop()
    sys.exit(0)

def main():
	global tail_syslog
	tail_syslog = TailLog(log_path)
	
	signal.signal(signal.SIGINT, signal_handler)
	signal.signal(signal.SIGTERM, signal_handler)
	log_thread = threading.Thread(target=log_monitor, args=(tail_syslog,))
	log_thread.daemon = True
	log_thread.start()
	
	while True:
		user_interaction()

if __name__ == "__main__":
    main()
