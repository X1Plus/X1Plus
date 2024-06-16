from .base import call
from jeepney import DBusAddress
import json

MQTT_DBUS_ADDRESS = DBusAddress('/x1plus/mqtt', bus_name='x1plus.x1plusd', interface='x1plus.mqtt')

def publish_message(payload):
    for attempt in range(5):
        try:
            return call(MQTT_DBUS_ADDRESS, 'MQTTPublish', json.dumps(payload))
        except RuntimeError as e:
            if 'ServiceUnknown' in str(e) and attempt < 5 - 1:
                print(f"Service not available, retrying in {1} seconds...")
                time.sleep(1)
            else:
                raise

def subscribe_topic(topic):
    return call(MQTT_DBUS_ADDRESS, 'MQTTSubscribe', topic)

def get_status():
    return call(MQTT_DBUS_ADDRESS, 'MQTTStatus')

def get_messages():
    return call(MQTT_DBUS_ADDRESS, 'MQTTGetMessages')

###
import time

def _cmd_status(args=None):
    status = get_status()
    print(f"MQTT service status: {status}")

def _cmd_publish(args):
    try:
        payload = json.loads(args.payload)
        print("Attempting to publish message...")
        publish_message(payload)
        print(f"Published payload: {args.payload}")
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON payload: {e}")

def _cmd_subscribe(args):
    subscribe_topic(args.topic)
    print(f"Subscribed to topic: {args.topic}")
    while True:
        try:
            messages = get_messages()['messages']
            for message in messages:
                print(f"Received message: {message}")
            time.sleep(3)
        except KeyboardInterrupt:
            print("Stopping subscription...")
            break

def add_subparser(subparsers):
    mqtt_parser = subparsers.add_parser('mqtt', help="Publish and subscribe to MQTT")
    mqtt_subparsers = mqtt_parser.add_subparsers(title='subcommands', required=True)

    mqtt_status_parser = mqtt_subparsers.add_parser('status', help="print current status of MQTTService")
    mqtt_status_parser.set_defaults(func=_cmd_status)

    mqtt_publish_parser = mqtt_subparsers.add_parser('publish', help="publish a local MQTT message")
    mqtt_publish_parser.add_argument('payload', type=str, help="payload to publish")
    mqtt_publish_parser.set_defaults(func=_cmd_publish)

    mqtt_subscribe_parser = mqtt_subparsers.add_parser('subscribe', help="subscribe to a local MQTT topic")
    mqtt_subscribe_parser.add_argument('topic', type=str, help="topic to subscribe to")
    mqtt_subscribe_parser.set_defaults(func=_cmd_subscribe)
    