from .base import call
from jeepney import DBusAddress
import json
import time 
import requests
import x1plus.utils
import logging
sn = x1plus.utils.serial_number()

logger = logging.getLogger(__name__)
MQTT_DBUS_ADDRESS = DBusAddress('/x1plus/printer', bus_name='x1plus.x1plusd', interface='x1plus.printer')

#PrinterService

def http_publish_message(topic, payload, qos=1):
    url = "http://localhost:8080/publish"  # just a test
    data = {
        "topic": topic,
        "message": payload,
        "qos": qos
    }
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            logger.info(f"Successfully published message to topic: {topic}")
            return {"status": "ok", "message_id": response.text}
        else:
            logger.warning(f"Failed to publish message. Status code: {response.status_code}")
            return None
    except requests.RequestException as e:
        logger.error(f"HTTP request failed: {e}")
        return None
    
def publish_message(topic, payload, qos=1):
    return http_publish_message(topic, payload, qos)

def get_status():
    url = "http://localhost:8080/status"  #just a test
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Failed to get status. Status code: {response.status_code}")
            return None
    except requests.RequestException as e:
        logger.error(f"HTTP request failed: {e}")
        return None


###
import x1plus.utils

sn = x1plus.utils.serial_number()

def _cmd_status(args=None):
    status = get_status()
    if status:
        print(json.dumps(status, indent=2))
    else:
        print("Failed to retrieve MQTT service status")
  
  
def _cmd_gcode_line(args):
    topic = f"device/{sn}/request"
    gcode_string = " ".join(args.command)
    gcode_commands = gcode_string.split("\\n")
    gcode_commands = [cmd.strip() for cmd in gcode_commands if cmd.strip()]
    gcode_param = "\n".join(gcode_commands)
    
    payload = {
        "print": {
            "command": "gcode_line",
            "sequence_id": 0,
            "param": gcode_param
        }
    }

    result = publish_message(topic, json.dumps(payload), 1)
    
    if result:
        print(f"Successfully published G-code commands:")
        for cmd in gcode_commands:
            print(f"  {cmd}")
    else:
        print("Failed to publish G-code commands")

def _cmd_gcode_file(args):
    topic = f"device/{sn}/request"
    file_path = args.path
    
    payload = {
        "print": {
            "command": "gcode_file",
            "sequence_id": 0,
            "param": file_path
        }
    }

    result = publish_message(topic, json.dumps(payload), 1)
            
    if result:
        print(f"Starting print from {file_path}")
    else:
        print("Failed to start print")

def _cmd_publish_custom(args):
    topic = args.topic
    if len(args.keyvalues) % 2 != 0:
        logger.error("You must provide an even number of arguments for key-value pairs.")
        return
        
    payload = dict(zip(args.keyvalues[0::2], args.keyvalues[1::2]))
    qos = args.qos if hasattr(args, 'qos') else 1 
        
    result = publish_message(topic, json.dumps(payload), qos)
    if result:
        print(f"Successfully published to topic: {topic} with QoS: {qos}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
    else:
        print("Failed to publish message")        

    
def add_subparser(subparsers):
    mqtt_parser = subparsers.add_parser('printer', help="Control print functions")
    mqtt_subparsers = mqtt_parser.add_subparsers(title='subcommands', required=True)

    mqtt_status_parser = mqtt_subparsers.add_parser('status', help="Current printer status")
    mqtt_status_parser.set_defaults(func=_cmd_status)

    mqtt_publish_parser = mqtt_subparsers.add_parser('pub', help="publish a custom MQTT payload")
    mqtt_publish_parser.add_argument('topic', type=str, help="MQTT topic to publish to")
    mqtt_publish_parser.add_argument('keyvalues', nargs='+', help="Key-value pairs for the message payload")
    mqtt_publish_parser.set_defaults(func=_cmd_publish_custom)


    publish_parser = mqtt_subparsers.add_parser('gcode_line', help="Publish Gcode commands")
    publish_parser.add_argument('command', nargs='*', help="Type of command to publish (e.g., 'M106 P1 S255')")
    publish_parser.set_defaults(func=_cmd_gcode_line)

    gcode_file_parser = mqtt_subparsers.add_parser('gcode_file', help="Start print from file")
    gcode_file_parser.add_argument('path', type=str, help="Filepath of .3mf or .gcode file")
    gcode_file_parser.set_defaults(func=_cmd_gcode_file)
    
