import os
import json
import ssl
import asyncio
import aiomqtt
import x1plus.utils
from .dbus import *

access_code = x1plus.utils.access_code()
sn = x1plus.utils.serial_number()
logger = logging.getLogger(__name__)

MQTT_INTERFACE = "x1plus.mqtt"
MQTT_PATH = "/x1plus/mqtt"

class MQTTService(X1PlusDBusService):
    STATUS_DISCONNECTED = "DISCONNECTED"
    STATUS_CONNECTED = "CONNECTED"
    
    def __init__(self, **kwargs):
        self.broker_url = '127.0.0.1'
        self.port = 8883
        self.topic = f"device/{sn}/request"
        self.username = 'bblp'
        self.password = access_code
        self.cafile = '/usr/etc/system/certs/ssl-ca-bbl.pem'
        self.client = None
        self.status = MQTTService.STATUS_DISCONNECTED
        self.mqtt_task_wake = asyncio.Event()
        self.last_status_object = None
        self.publish_payload = None
        self.subscribe_topic = None
        self.received_messages = []
        
        super().__init__(
            dbus_interface=MQTT_INTERFACE, dbus_path=MQTT_PATH, **kwargs
        )

    async def task(self):
        asyncio.create_task(self._mqtt_task())
        await super().task()

    def _make_status_object(self):
        return {
            "status": self.status,
        }

    async def dbus_MQTTStatus(self, req):
        return self._make_status_object()

    async def dbus_MQTTPublish(self, payload):
        self.publish_payload = payload
        self.mqtt_task_wake.set()
        return {"status": "ok"}

    async def dbus_MQTTSubscribe(self, topic):
        self.subscribe_topic = topic
        self.mqtt_task_wake.set()
        return {"status": "ok"}
    
    async def dbus_MQTTGetMessages(self, req):
        messages = self.received_messages.copy()
        self.received_messages.clear()
        return {"messages": messages}
    
    async def connect(self):
        try:
            self.client = aiomqtt.Client(
                hostname=self.broker_url,
                port=self.port,
                username=self.username,
                password=self.password,
                tls_insecure=True,
                tls_context=ssl.create_default_context(cafile=self.cafile)
            )
            await self.client.__aenter__()
            self.status = MQTTService.STATUS_CONNECTED
            logger.info("Connected to local MQTT")
            self.mqtt_task_wake.set()
        except Exception as e:
            logger.error(f"Failed to connect to local MQTT: {e}")
            self.status = MQTTService.STATUS_DISCONNECTED

    async def disconnect(self):
        if self.client:
            await self.client.__aexit__(None, None, None)
            self.status = MQTTService.STATUS_DISCONNECTED
            self.mqtt_task_wake.set()

    async def publish(self):
        if self.publish_payload:
            if self.status == MQTTService.STATUS_DISCONNECTED:
                logger.info("Client disconnected, attempting to reconnect")
                await self.connect()
            
            if self.status == MQTTService.STATUS_CONNECTED:
                try:
                    await self.client.publish(self.topic, self.publish_payload)
                    logger.info(f"Published payload: {self.publish_payload}")
                except Exception as e:
                    logger.error(f"Failed to publish payload: {e}")
            else:
                logger.error("Failed to publish payload: Client is not connected")
            self.publish_payload = None

    async def subscribe(self):
        if self.subscribe_topic:
            try:
                await self.client.subscribe(self.subscribe_topic)
                logger.info(f"Subscribed to topic: {self.subscribe_topic}")
                
                async for message in self.client.messages:
                    await self.on_message(message)
            except Exception as e:
                logger.error(f"Failed to subscribe to topic {self.subscribe_topic}: {e}")
                raise
            self.subscribe_topic = None
    
    async def on_message(self, message):
        try:
            topic = message.topic.value
            payload = message.payload.decode('utf-8')
            logger.info(f"Received message on {topic}: {payload}")
            self.received_messages.append({"topic": topic, "payload": payload})
            await self.emit_signal("MQTTReceived", {"topic": topic, "payload": payload})
        except Exception as e:
            logger.error(f"Failed to process message: {e}")

    async def _mqtt_task(self):
        while True:
            if self.status == MQTTService.STATUS_DISCONNECTED:
                await self.connect()

            await self.mqtt_task_wake.wait()
            self.mqtt_task_wake.clear()

            if self.publish_payload:
                await self.publish()

            if self.subscribe_topic:
                await self.subscribe()

