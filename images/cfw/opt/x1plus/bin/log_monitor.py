import os
import re
import time
import json
import threading
import subprocess

lock_pattern = re.compile(r'\[MCU\]\[BMC\]owner=1 lock! \[Free\]')
unlock_pattern = re.compile(r'\[MCU\]\[BMC\]owner=1 unlock!')
timestamp_pattern = re.compile(r'^\w{3} +\d{1,2} \d{2}:\d{2}:\d{2}')
info_forward_pattern = re.compile(r'info forward\[\d+\]: ')
valid_line_pattern = re.compile(r'.*info forward\[\d+\]: \[(MCU\]\[BMC|gparser)\]')


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
        self.fd = open(self.filepath, "r", encoding="utf-8", errors="replace")
        self.ino = os.fstat(self.fd.fileno()).st_ino
        if self.seek_end:
            self.fd.seek(0, os.SEEK_END)

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
        while True:
            line = self.readline()
            if not line:
                time.sleep(self.interval)
            else:
                yield line

log_path = "/mnt/sdcard/log/syslog.log" if os.path.exists("/tmp/.syslog_to_sd") and os.path.exists("/mnt/sdcard/log/") else "/tmp/syslog.log"

def send_gcode(gcode_line):
    json_payload = {
        "print": {
            "command": "gcode_line",
            "sequence_id": "2001",
            "param": gcode_line
        }
    }
    mqtt_pub(json.dumps(json_payload))
    time.sleep(1)

def mqtt_pub(message):
    command = f"source /usr/bin/mqtt_access.sh; mqtt_pub '{message}'"
    try:
        subprocess.run(command, shell=True, check=True, executable='/bin/bash',
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
    except subprocess.CalledProcessError as e:
        print(f"error {e}")

def log_monitor(tail_log):
	capturing = False
	captured_lines = []
	try:
		for line in tail_log.lines():
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

def gcode_prompt():
	while True:
		try:
			time.sleep(2)
			gcode_input = input("<div><font color='#CACACA'>enter a gcode command</font><div>")
			send_gcode(gcode_input)
			
		except EOFError:
			break

def main():
    tail_syslog = TailLog(log_path)
    log_thread = threading.Thread(target=log_monitor, args=(tail_syslog,), daemon=True)
    log_thread.start()
    p_thread = threading.Thread(target=gcode_prompt, daemon=True)
    p_thread.start()
    log_thread.join()
    p_thread.join()


if __name__ == "__main__":
    main()
