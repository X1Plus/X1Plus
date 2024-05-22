import os
import re
import time
import json
import sys
import signal
import threading
import subprocess
'''
Interactive Gcode console for X1 Printers

Publishes Gcode with an MQTT command while tailing syslog in a background thread

The regex patterns match to extract the gcode "output" which appears between an 
'owner=1 lock! [Free]' line and an 'owner=1 unlock!' line. 

Usage: Save this script to your SD card and run it via SSH:
 python3 /sdcard/log_monitor.py
'''

lock_pattern = re.compile(r'\[MCU\]\[BMC\]owner=1 lock! \[Free\]')
unlock_pattern = re.compile(r'\[MCU\]\[BMC\]owner=1 unlock!')
timestamp_pattern = re.compile(r'^\w{3} \d{2} \d{2}:\d{2}:\d{2}')
info_forward_pattern = re.compile(r'info forward\[\d+\]: ')
valid_line_pattern = re.compile(r'^\w{3} \d{2} \d{2}:\d{2}:\d{2} info forward\[\d+\]: \[(MCU\]\[BMC|gparser)\]')

    
class TailLog:
    def __init__(self, filepath, seek_end=True, interval=1.0):
        self.filepath = filepath
        self.fd = None
        self.ino = None
        self.seek_end = seek_end
        self.buf = ""
        self.interval = interval
        self._open_file()

    def _open_file(self):
        """Open the file and seek to the end if necessary."""
        self.fd = open(self.filepath, "r", encoding="utf-8", errors="replace")
        self.ino = os.fstat(self.fd.fileno()).st_ino
        if self.seek_end:
            self.fd.seek(0, os.SEEK_END)

    def readline(self):
        """Read a line, non-blocking (returns None if no line is ready)."""
        # Check if the inode has changed (i.e., the logs have rotated)
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
        """Generator to infinitely tail a log file."""
        while True:
            line = self.readline()
            if not line:
                time.sleep(self.interval)
            else:
                yield line

log_path = "/mnt/sdcard/log/syslog.log" if os.path.exists("/tmp/.syslog_to_sd") and os.path.exists("/mnt/sdcard/log/") else "/tmp/syslog.log"

def send_gcode(gcode_line):
	print(f"Gcode sent: {gcode_line}")
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
    try:
        subprocess.run(command, shell=True, check=True, executable='/bin/bash',
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f"error {e}")

def log_monitor():
	capturing = False
	captured_lines = []
	tail_syslog = TailLog(log_path)
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
					print(f"{line}<div>")
					captured_lines.append(line)
	except Exception as e:
		print(f"Failed to monitor log file: {e}")

def user_interaction():
	gcode_input = input("<br><font color='green'>[root@BL-P001]: </font>")
	send_gcode(gcode_input)


def main():
	log_thread = threading.Thread(target=log_monitor)
	log_thread.start()
	user_interaction()

if __name__ == "__main__":
	main()
