import os
import aiomqtt
import asyncio
import logging
import ssl
import json
import contextlib

import x1plus.utils

logger = logging.getLogger(__name__)

class MQTTClient():
    def __init__(self, daemon, **kwargs):
        self.daemon = daemon
        
        self.daemon.settings.on("mqtt.override.host", lambda: self._trigger_reconnect())
        self.daemon.settings.on("mqtt.override.password", lambda: self._trigger_reconnect())
        self.daemon.settings.on("mqtt.override.sn", lambda: self._trigger_reconnect())
        
        self.mqttc = None
        self.reconnect_event = asyncio.Event()
        
        self.request_message_handlers = set()
        self.report_message_handlers = set()
        
        self.latest_print_status = {}
    
    def _trigger_reconnect(self):
        self.reconnect_event.set()
    
    async def mqtt_message_loop(self):
        async for message in self.mqttc.messages:
            try:
                payload = json.loads(message.payload)
            except Exception as e:
                logger.warning(f"unparseable message on topic {message.topic}: {message.payload}")
                continue
            if "/request" in message.topic.value:
                for handler in self.request_message_handlers.copy(): # avoid problems if this gets mutated out from under us mid handler
                    await handler(payload)
            elif "/report" in message.topic.value:
                if 'print' in payload and payload['print'].get('command', None) == "push_status":
                    self.latest_print_status = payload['print']
                for handler in self.report_message_handlers.copy(): # avoid problems if this gets mutated out from under us mid handler
                    await handler(payload)
            else:
                logger.warning(f"message on unexpected topic {message.topic}?")
    
    async def task(self):
        while True:
            try:
                logger.info("connecting to MQTT broker")
                
                password = None
                if os.path.isfile("/config/device/access_token"):
                    password = open("/config/device/access_token", "r").read()
                password = self.daemon.settings.get("mqtt.override.password", password)
                
                self.sn = self.daemon.settings.get("mqtt.override.sn", None)
                if not self.sn:
                    self.sn = x1plus.utils.serial_number()
                
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE

                client = aiomqtt.Client(
                    hostname = self.daemon.settings.get("mqtt.override.host", "127.0.0.1"),
                    port = 8883,
                    username = "bblp",
                    password = password,
                    tls_context = ssl_ctx,
                    tls_insecure = True)
                self.reconnect_event.clear()
                async with client:
                    await client.subscribe("device/+/request")
                    await client.subscribe("device/+/report")
                    self.mqttc = client
                    loop_task = asyncio.create_task(self.mqtt_message_loop())
                    await asyncio.wait([loop_task, asyncio.ensure_future(self.reconnect_event.wait())], return_when=asyncio.FIRST_COMPLETED)
                    loop_task.cancel()
                    try:
                        await loop_task
                    except asyncio.CancelledError:
                        pass
            except aiomqtt.MqttError as e:
                self.mqttc = None
                logger.warning(f"MQTT connection lost: {e}")
                await asyncio.sleep(5)
            finally:
                self.mqttc = None

    async def publish_request(self, obj):
        if not self.mqttc:
            logger.warning("publish_request, but mqtt client not connected")
            return
        await self.mqttc.publish(f"device/{self.sn}/request", payload=json.dumps(obj))

    async def publish_report(self, obj):
        if not self.mqttc:
            logger.warning("publish_report, but mqtt client not connected")
            return
        await self.mqttc.publish(f"device/{self.sn}/report", payload=json.dumps(obj))
    
    @contextlib.contextmanager
    def request_messages(self):
        q = asyncio.Queue()
        async def handle(msg):
            await q.put(msg)
        self.request_message_handlers.add(handle)
        try:
            yield q
        finally:
            self.request_message_handlers.remove(handle)

    @contextlib.contextmanager
    def report_messages(self):
        q = asyncio.Queue()
        async def handle(msg):
            await q.put(msg)
        self.report_message_handlers.add(handle)
        try:
            yield q
        finally:
            self.report_message_handlers.remove(handle)
    
    # for long-lived callbacks; fn should be async!!
    def on_request_message(self, fn):
        self.request_message_handlers.add(fn)
    
    def on_report_message(self, fn):
        self.report_message_handlers.add(fn)
