import os
import re
import time
import json
import threading
import subprocess

lock_pattern = re.compile(r'\[MCU\]\[BMC\]owner=1 lock! \[Free\]')
unlock_pattern = re.compile(r'\[MCU\]\[BMC\]owner=1 unlock!')
info_forward_pattern = re.compile(r'info forward\[\d+\]: ')
pattern_pattern = re.compile(r'\[gparser\]\[\d+\]')
timestamp_pattern = re.compile(r'^\w{3} +\d{1,2} \d{2}:\d{2}:\d{2}')
valid_line_pattern = re.compile(r'.*info forward\[\d+\]: \[(MCU\]\[BMC|gparser)\]')


log_path = "/mnt/sdcard/log/syslog.log" if os.path.exists("/tmp/.syslog_to_sd") and os.path.exists("/mnt/sdcard/log/") else "/tmp/syslog.log"
class TailLog:
    def __init__(self, filepath):
        self.filepath = filepath
        self.fd = None
        self.timeout = 5
       	self.last_interaction_time = time.time()
        self.ino = None
        self.running = False
        self.open_file()

    def open_file(self):
        self.fd = open(self.filepath, "r", encoding="utf-8", errors="replace")
        self.ino = os.fstat(self.fd.fileno()).st_ino
        self.fd.seek(0, os.SEEK_END) 
        
    def reset_timeout(self):
        self.last_interaction_time = time.time()
        
    def tail(self, callback):
        self.running = True
        while self.running:
            current_ino = os.fstat(self.fd.fileno()).st_ino
            if current_ino != self.ino: 
                self.fd.close()
                self.open_file()

            new_line = self.fd.readline()
            if new_line:
                callback(new_line)
                if unlock_pattern.search(new_line):
                    self.stop()
            else:
                time.sleep(0.1)

    def stop(self):
        self.running = False
        self.fd.close()
capturing = False
captured_lines = []
def handle_log_output(line):
    global capturing, captured_lines, tailing_thread
    if lock_pattern.search(line):
        capturing = True  # Start capturing log lines
        captured_lines = []
        return

    if capturing:
        if unlock_pattern.search(line):
            output = ''.join(captured_lines).strip() 
            capturing = False
            captured_lines = []
            tailing_thread.stop()
            return

        line = timestamp_pattern.sub('', line)
        line = pattern_pattern.sub('<div>', line)
        line = info_forward_pattern.sub('', line)
        #line = "<font color='#FFF7CC'>" + line + "</font>"
        print(line.replace("[MCU][BMC]", "<div>"), flush=True)


def mqtt_pub(message):
    command = f"source /usr/bin/mqtt_access.sh; mqtt_pub '{message}'"
    try:
        subprocess.run(command, shell=True, check=True, executable='/bin/bash',
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
    except subprocess.CalledProcessError as e:
        print(f"error {e}")

def send_gcode(gcode_line, seq_id):
    json_payload = {
        "print": {
            "command": "gcode_line",
            "sequence_id": seq_id,
            "param": gcode_line
        }
    }
    mqtt_pub(json.dumps(json_payload))
    global tailing_thread
    tailing_thread = TailLog(log_path)
    threading.Thread(target=tailing_thread.tail, args=(handle_log_output,)).start()

def main():
	while True:
		gcode_input = input("\n")
		send_gcode(gcode_input,"0")
	
if __name__ == "__main__":
    main()
