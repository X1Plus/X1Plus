import json, subprocess, os, time,re

#Input a set temperature and run the script
#Chamber temp is monitored until the set temperature is reached
#The chamber temp you'll reach without active heating is 45-55C depending on 
#the ambient temperature of your workspace
setTemp = 45 #Target chamber temp
logData = True #Save chamber temp values to file
savefile = "/tmp/chamber_temp" #save location for chamber temp data

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
    try:
        subprocess.run(command, shell=True, check=True, executable='/bin/bash')
    except subprocess.CalledProcessError as e:
        print(f"error {e}")
def save_log(strs,sfile):
    with open(sfile, "a") as sf:
        sf.write(strs)
        
def printJson(key):
    try:
        with open('/config/screen/printer.json', 'r') as file:
            data = json.load(file)
         
            return data.get(key, False)
    except FileNotFoundError:
        print("printer.json doesn't exist")
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False
        
def main():
    gcode_str_on = "G28\nG0 Z5 F1200\nM106 P2 S255\nM140 S100"
    gcode_str_off = "M106 P2 S0\nM140 S0"
    persistLog = os.path.exists("/config/x1plus/logsd")
    logPath = "/mnt/sdcard/log/syslog.log" if persistLog else "/tmp/syslog.log"
    rpos = 0
    send_gcode(gcode_str_on)
    ino = -1
    buf = ""
    first = True
    while True:
        with open(logPath, "r") as fd:
            fd.seek(rpos)
            lines = fd.readlines()
            rpos = fd.tell()

        for l in lines:
            m = re.search(r"chamber_temper\s*is\s*(-?\d+\.?\d*)|\"chamber_temper\":(-?\d+\.?\d*)", l)
            if m:
                temp = float(m.group(1))
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                savedata = f"{timestamp} - Chamber temp: {temp}\n"

            
                if temp < setTemp:
                    if logData:
                        save_log(savedata,savefile)
                    print(savedata, end="")
                else:
                    print(f"Reached set temp {setTemp}")
                    if logData:
                        save_log(time.strftime("%H:%M:%S") + " - reached temp",savefile)
                    send_gcode(gcode_str_off)
                    return 

        time.sleep(5)
if __name__ == "__main__":
    main()
