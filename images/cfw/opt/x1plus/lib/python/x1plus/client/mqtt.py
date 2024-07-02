from .base import call
from jeepney import DBusAddress
import json
import time 
import logging


logger = logging.getLogger(__name__)
MQTT_DBUS_ADDRESS = DBusAddress('/x1plus/mqtt', bus_name='x1plus.x1plusd', interface='x1plus.mqtt')

def publish_message(topic, payload):
    for attempt in range(5):
        try:
            return call(MQTT_DBUS_ADDRESS, 'MQTTPublish', {"topic": topic, "payload":json.loads(payload)})
        except RuntimeError as e:
            if 'ServiceUnknown' in str(e):
                if attempt < 4:
                    logger.warning(f"Service not available, retrying in 1 second... (Attempt {attempt + 1}/5)")
                    time.sleep(1)
                else:
                    logger.error("Service remains unavailable after several attempts.")
            else:
                logger.error(f"An error occurred: {e}")
                break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            break
    return None

# Subscribes to a topic over command line, however it's not possible to define a callback so this option is probably useless
# I considered making this print output directly to the console, but is that actually useful? Doesn't seem so 
def subscribe_topic(topic):
    logger.info(f"Attempting to subscribe to topic: {topic}")
    try:
        response = call(MQTT_DBUS_ADDRESS, 'MQTTSubscribe', {'topic': topic})
        logger.info(f"Subscribed to topic: {topic} with response: {response}")
        return response
    except RuntimeError as e:
        logger.error(f"Failed to subscribe to topic {topic}: {e}")
        if 'ServiceUnknown' in str(e):
            logger.info("Service not available, check DBus service status.")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during subscription: {e}")
        return None

def unsubscribe_topic(topic):
    logger.info(f"Attempting to unsubscribe from topic: {topic}")
    try:
        response = call(MQTT_DBUS_ADDRESS, 'MQTTUnsubscribe', {'topic': topic})
        logger.info(f"Unsubscribed from topic: {topic} with response: {response}")
        return response
    except Exception as e:
        logger.error(f"Failed to unsubscribe from topic {topic}: {e}")
        return None

def get_status():
    return call(MQTT_DBUS_ADDRESS, 'MQTTStatus')

def list_subscriptions():
    return call(MQTT_DBUS_ADDRESS, 'MQTTShowSubs')

###
import x1plus.utils
from .payloads import *

sn = x1plus.utils.serial_number()

def _cmd_status(args=None):
    status = get_status()
    if status:
        print(json.dumps(status, indent=2))
    else:
        print("Failed to retrieve MQTT service status")
        
# Payload-formatting publisher
# CLI example: x1plus mqtt publish gcode_line "M106 P1 S200"
def _cmd_publish(args):
    command_to_function = {
        'get_version': (get_version, []),
        'upgrade_confirm': (upgrade_confirm, []),
        'consistency_confirm': (consistency_confirm, []),
        'start_upgrade': (start_upgrade, ['url', 'module', 'version']),
        'get_upgrade_history': (get_upgrade_history, []),
        'print_action': (print_action, ['action']),
        'ams_change_filament': (ams_change_filament, ['target', 'curr_temp', 'tar_temp']),
        'ams_control': (ams_control, ['param']),
        'unload_filament': (unload_filament, []),
        'get_access_code': (get_access_code, []),
        'ipcam_record_set': (ipcam_record_set, ['control']),
        'ipcam_timelapse': (ipcam_timelapse, ['control']),
        'xcam_control_set': (xcam_control_set, ['module_name', 'control', 'print_halt']),
        'send_project': (send_project, ['plate_number', 'url']),
        'gcode_file': (gcode_file, ['file_path']),
        'gcode_line': (gcode_line, ['command'])
    }

    command = args.command
    if command in command_to_function:
        func, param_keys = command_to_function[command]
        if len(args.payload) != len(param_keys):
            print(f"Error: Expected {len(param_keys)} arguments for {command}, got {len(args.payload)}")
            return

        kwargs = dict(zip(param_keys, args.payload))

        try:
            payload = func(**kwargs)
            print(payload)
            topic = f"device/{sn}/request"
            result = publish_message(topic,payload)
            if result:
                print(f"Successfully published to topic {topic}. Payload: {json.loads(payload)}")
            else:
                print("Failed to publish message")
        except Exception as e:
            print(f"Error generating payload for {command}: {e}")
    else:
        print(f"No handler defined for command: {command}")

    
# Publisher for custom payloads - arguments are required in pairs to create a JSON serializablolol payload
# for example, to send "gcode_line" you would enter the following: 
#   x1plus mqtt pub "device/serial/request" command gcode_line sequence_id 0 param "M106 P1 S200"
def _cmd_publish_custom(args):
    topic = args.topic
    if len(args.keyvalues) % 2 != 0:
        logger.error("You must provide an even number of arguments for key-value pairs.")
        return
        
    payload = dict(zip(args.keyvalues[0::2], args.keyvalues[1::2]))
        
    result = publish_message(topic, json.dumps(payload))
    if result:
        print(f"Successfully published to topic: {topic}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
    else:
        print("Failed to publish message")

# Subscribes to a topic over command line, however it's not possible to define a callback so this option is probably useless
def _cmd_subscribe(args):
    subscribe_topic(args.topic)
    logger.info(f"Subscribed to topic: {args.topic} with result")

def _cmd_unsubscribe(args):
    unsubscribe_topic(args.topic)
    logger.info(f"Unsubscribed from topic: {args.topic}")

# List all topics subscribed to
def _cmd_list_subs(args=None):
    subs = list_subscriptions()
    print(f"Currently subscribed topics: {subs}")
    

    
def add_subparser(subparsers):
    # still not finished here... 
    mqtt_parser = subparsers.add_parser('mqtt', help="Publish and subscribe to MQTT")
    mqtt_subparsers = mqtt_parser.add_subparsers(title='subcommands', required=True)

    mqtt_status_parser = mqtt_subparsers.add_parser('status', help="current status of MQTTService")
    mqtt_status_parser.set_defaults(func=_cmd_status)

    mqtt_publish_parser = mqtt_subparsers.add_parser('pub', help="publish a custom MQTT payload")
    mqtt_publish_parser.add_argument('topic', type=str, help="MQTT topic to publish to")
    mqtt_publish_parser.add_argument('keyvalues', nargs='+', help="Key-value pairs for the message payload")
    mqtt_publish_parser.set_defaults(func=_cmd_publish_custom)

    mqtt_subscribe_parser = mqtt_subparsers.add_parser('sub', help="subscribe to a local MQTT topic")
    mqtt_subscribe_parser.add_argument('topic', type=str, help="topic to subscribe to (or use wildcard *)")
    mqtt_subscribe_parser.set_defaults(func=_cmd_subscribe)

    mqtt_unsubscribe_parser = mqtt_subparsers.add_parser('unsub', help="unsubscribe from a local MQTT topic")
    mqtt_unsubscribe_parser.add_argument('topic', type=str, help="topic to unsubscribe from")
    mqtt_unsubscribe_parser.set_defaults(func=_cmd_unsubscribe)

    mqtt_list_subs_parser = mqtt_subparsers.add_parser('show', help="show all subscribed topics")
    mqtt_list_subs_parser.set_defaults(func=_cmd_list_subs)

    publish_parser = mqtt_subparsers.add_parser('publish', help="Publish messages for pre-defined payloads")
    publish_parser.add_argument('command', type=str, help="Type of command to publish (e.g., 'send_project')")
    publish_parser.add_argument('payload', nargs='*', help="Additional arguments for the command")
    publish_parser.set_defaults(func=_cmd_publish)

