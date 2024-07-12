import os
import aiomqtt
import asyncio
import logging
import ssl
import json

logger = logging.getLogger(__name__)

class MQTTClient():
    def __init__(self, settings, **kwargs):
        self.x1psettings = settings
        
        self.x1psettings.on("mqtt.override.host", lambda: self._trigger_reconnect())
        self.x1psettings.on("mqtt.override.password", lambda: self._trigger_reconnect())
        self.x1psettings.on("mqtt.override.sn", lambda: self._trigger_reconnect())
        
        self.mqttc = None
        self.reconnect_event = asyncio.Event()
    
    def _trigger_reconnect(self):
        self.reconnect_event.set()
    
    async def mqtt_message_loop(self):
        async for message in self.mqttc.messages:
            print(message.topic, json.loads(message.payload))
    
    async def task(self):
        while True:
            try:
                logger.info("connecting to MQTT broker")
                
                password = None
                if os.path.isfile("/config/device/access_token"):
                    password = open("/config/device/access_token", "r").read()
                password = self.x1psettings.get("mqtt.override.password", password)
                
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE

                client = aiomqtt.Client(
                    hostname = self.x1psettings.get("mqtt.override.host", "127.0.0.1"),
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
                    await asyncio.wait([loop_task, self.reconnect_event.wait()], return_when=asyncio.FIRST_COMPLETED)
                    loop_task.cancel()
            except aiomqtt.MqttError as e:
                self.mqttc = None
                logger.warning(f"MQTT connection lost: {e}")
                await asyncio.sleep(5)
            finally:
                self.mqttc = None

    async def publish_request(self, obj):
        pass
    
    async def publish_report(self, obj):
        pass
    
    async def on_request(self, fn):
        pass
    
    async def on_report(self, fn):
        pass
