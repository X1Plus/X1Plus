import json

def create_payload(category, command, **kwargs):
    payload = {
        category: {
            "sequence_id": "0",
            "command": command,
            **kwargs
        }
    }
    return json.dumps(payload)

def get_version():
    return create_payload("info", "get_version")

def upgrade_confirm():
    return create_payload("upgrade", "upgrade_confirm", src_id=1)

def consistency_confirm():
    return create_payload("upgrade", "consistency_confirm", src_id=1)

def start_upgrade(url, module, version):
    return create_payload("upgrade", "start", src_id=1, url=url, module=module, version=version)

def get_upgrade_history():
    return create_payload("upgrade", "get_history")

def print_action(action):
    return create_payload("print", action, param="")

def ams_change_filament(target, curr_temp, tar_temp):
    return create_payload("print", "ams_change_filament", target=target, curr_temp=curr_temp, tar_temp=tar_temp)

def ams_control(param):
    return create_payload("print", "ams_control", param=param)

def unload_filament():
    return create_payload("print", "unload_filament")

def get_access_code():
    return create_payload("system", "get_access_code")

def ipcam_record_set(control):
    return create_payload("camera", "ipcam_record_set", control=control)

def ipcam_timelapse(control):
    return create_payload("camera", "ipcam_timelapse", control=control)

def xcam_control_set(module_name, control, print_halt):
    return create_payload("xcam", "xcam_control_set", module_name=module_name, control=control, print_halt=print_halt)

def send_project(plate_number, url, timelapse=True, bed_type="auto", bed_levelling=True, flow_cali=True, vibration_cali=True, layer_inspect=True, use_ams=False):
    return create_payload("print", "project_file", param=f"Metadata/plate_{plate_number}.gcode", project_id="0", profile_id="0", task_id="0", subtask_id="0", subtask_name="", file="", url=f"file://{url}", md5="", timelapse=timelapse, bed_type=bed_type, bed_levelling=bed_levelling, flow_cali=flow_cali, vibration_cali=vibration_cali, layer_inspect=layer_inspect, ams_mapping="", use_ams=use_ams)

def gcode_file(file_path):
    return create_payload("print", "gcode_file", param=file_path)

def gcode_line(command):
    return create_payload("print", "gcode_line", param=command)
