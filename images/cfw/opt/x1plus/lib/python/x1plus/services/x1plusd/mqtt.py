import os
import json
import ssl
import asyncio
import aiomqtt
import x1plus.utils
from .dbus import *
import logging 
from .handler import load_handlers,  topic_from_handler

access_code = x1plus.utils.access_code()
sn = x1plus.utils.serial_number()
logger = logging.getLogger(__name__)

MQTT_INTERFACE = "x1plus.mqtt"
MQTT_PATH = "/x1plus/mqtt"

class MQTTService(X1PlusDBusService):
    STATUS_DISCONNECTED = "DISCONNECTED"
    STATUS_CONNECTED = "CONNECTED"
    STATUS_DISABLED = "DISABLED"
    
    def __init__(self, settings, **kwargs):
        self.x1psettings = settings
        self.broker_url = '127.0.0.1'
        self.port = 8883
        self.topic = f"device/{sn}/request"
        self.username = 'bblp'
        self.password = access_code
        self.cafile = '/usr/etc/system/certs/ssl-ca-bbl.pem'
        self.client_config = self.build_client_config()
        self.client = aiomqtt.Client(**self.client_config)
        self.status = self.STATUS_DISCONNECTED
        self.topic_handlers = load_handlers(self.publish)
        self.subscribed_topics = set()
        self.message_queue = asyncio.Queue()
        self.default_handler = None
        self.enable = True
        super().__init__(dbus_interface=MQTT_INTERFACE, dbus_path=MQTT_PATH, **kwargs)

    async def task(self):
        asyncio.create_task(self._loop())
        await super().task()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    async def disconnect(self):
        await self.client.disconnect()
        self.status = "DISCONNECTED"

    def _make_status_object(self):
        return {
            "status": self.status,
            "enabled": self.enable
        }


    def build_client_config(self):
        return {
            "hostname": self.broker_url,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "tls_context": ssl.create_default_context(cafile=self.cafile),
            "tls_insecure": True
        }

    async def connect(self):
        try:
            self.enable = True
            config = self.build_client_config()
            self.client = aiomqtt.Client(**config)
            await self.client.__aenter__()
            self.status = self.STATUS_CONNECTED
            logger.info("Connected to MQTT Broker, starting subscription...")
            await self.subscribe_topics()
            asyncio.create_task(self.listen_for_messages())
            asyncio.create_task(self._outgoing())
        except Exception as e:
            logger.error(f"Failed to connect or start initial tasks: {e}")
            await self.handle_disconnect()

    async def subscribe_topics(self):
        if self.status != self.STATUS_CONNECTED:
            logger.warning("Attempted to subscribe while not connected.")
            return

        for topic, handler in self.topic_handlers.items():
            if topic not in self.subscribed_topics:
                try:
                    await self.client.subscribe(topic)
                    self.subscribed_topics.add(topic)
                    logger.info(f"Subscribed to {topic}")
                except Exception as e:
                    logger.error(f"Failed to subscribe to {topic}: {e}")

    async def listen_for_messages(self):
        try:
            async for message in self.client.messages:
                topic = message.topic.value
                handler = topic_from_handler(self.topic_handlers,topic)
                await handler(message)
        except Exception as e:
            logger.error(f"Error in message loop: {e}")
            await self.handle_disconnect()

    async def handle_disconnect(self):
        if self.status == self.STATUS_CONNECTED:
            await self.client.__aexit__(None, None, None)
            self.status = self.STATUS_DISCONNECTED
            logger.info("Attempting to reconnect...")

    def get_subscribed_topics(self):
        return list(self.subscribed_topics)

    def register_topic_handler(self, topic: str, handler: callable):
        if not topic in self.topic_handlers:
            self.topic_handlers[topic] = handler
            if self.status == self.STATUS_CONNECTED:
                asyncio.create_task(self.client.subscribe(topic))

    def remove_topic_handler(self, topic: str):
        if topic in self.topic_handlers:
            del self.topic_handlers[topic]
            logger.info(f"Removed handler for topic {topic}")

    async def publish(self, topic: str, payload: any):
        await self.message_queue.put((topic, payload))
        print(payload)

    async def _outgoing(self):
        while True:
            topic, payload = await self.message_queue.get()
            try:
                await self.client.publish(topic, payload)
            except Exception as e:
                logger.error(f"Failed to publish message: {e}")
                await self.message_queue.put((topic, payload))

    async def dbus_MQTTStatus(self, req):
        return {"status": self._make_status_object()}

    async def dbus_MQTTPublish(self, req):
        try:
            topic = req.get('topic')
            message = req.get('payload')
            if not topic or not message:
                return {"status": "error", "message": "Topic or message missing"}
            await self.publish(topic, json.dumps(message).encode('utf-8'))
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"Failed to publish message: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def dbus_MQTTSubscribe(self, req):
        topic = req.get('topic')
        self.register_topic_handler(topic, self.default_handler)
        return {"status": "ok"}
      
    async def dbus_MQTTUnsubscribe(self, req):
        topic = req.get('topic')
        self.remove_topic_handler(topic)
        return {"status": "ok"}

    async def dbus_MQTTShowSubs(self,req):
        return {"status": self.get_subscribed_topics()}

    async def _loop(self):
        if self.status == self.STATUS_DISABLED:
            await self.disconnect()
        elif self.status == self.STATUS_DISCONNECTED:
            await self.connect()
            
        while True:
            await asyncio.sleep(10)
