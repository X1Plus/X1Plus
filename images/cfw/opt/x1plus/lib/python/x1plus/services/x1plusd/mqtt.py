import os
import json
import ssl
import asyncio
import aiomqtt
import time
import x1plus.utils
from .dbus import *
import logging 
from .handler import load_handlers,  topic_from_handler
from logging.handlers import RotatingFileHandler
from aiohttp import web

access_code = x1plus.utils.access_code()
sn = x1plus.utils.serial_number()
logger = logging.getLogger(__name__)

class HTTPServer:
    def __init__(self, mqtt_client):
        self.app = web.Application()
        self.mqtt_client = mqtt_client
        self.app.router.add_post('/publish', self.handle_publish)
        self.app.router.add_get('/status', self.handle_status)
    async def handle_status(self, request):
        status = self.mqtt_client._make_status_object()
        return web.json_response(status)
    async def handle_publish(self, request):
        data = await request.json()
        topic = data.get('topic')
        message = data.get('message')
        qos = data.get('qos', 0)
        retain = data.get('retain', False)
            
        if not topic or not message:
            return web.Response(status=400, text='Both topic and message are required')
            
        success = await self.mqtt_client.publish(topic, message, qos=qos)
            
        if success:
            return web.Response(status=200, text='Message queued for publication')
        else:
            return web.Response(status=500, text='Failed to queue message for publication')

    async def run(self, host='0.0.0.0', port=8080):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        print(f"HTTP server started on http://{host}:{port}")

class MQTTService:
    STATUS_DISCONNECTED = "DISCONNECTED"
    STATUS_CONNECTED = "CONNECTED"
    STATUS_DISABLED = "DISABLED"
    
    def __init__(self, **kwargs):
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
        self._message_counter = 0

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
        
    async def start(self):
        """Start the MQTT service."""
        self.running = True
        await self.connect()
        asyncio.create_task(self._loop())
        asyncio.create_task(self._outgoing())
        await self.start_http_server()

    async def stop(self):
        """Stop the MQTT service."""
        self.running = False
        await self.disconnect()    
    def _unique_id(self):
        self._message_counter += 1
        return f"{int(time.time())}_{self._message_counter}"
    
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
        
    async def start_http_server(self, host='0.0.0.0', port=8080):
        http_server = HTTPServer(self)
        await http_server.run(host, port)
        
    def _format_payload(self, payload):
        message_id = self._unique_id()
        if isinstance(payload, dict):
            payload['message_id'] = message_id
            return json.dumps(payload), message_id
        elif isinstance(payload, str):
            try:
                payload_dict = json.loads(payload)
                payload_dict['message_id'] = message_id
                return json.dumps(payload_dict), message_id
            except json.JSONDecodeError:
                return f"{message_id}:{payload}", message_id
        return payload, message_id

    
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
                    await self.client.subscribe(topic, qos=1)
                    self.subscribed_topics.add(topic)
                    logger.info(f"Subscribed to {topic} with QoS {1}")
                except Exception as e:
                    logger.error(f"Failed to subscribe to {topic}: {e}")
                    
    async def listen_for_messages(self):
        processed_messages = set()
        while True:
            try:
                async for message in self.client.messages:
                    topic = message.topic.value
                    payload = message.payload.decode()
                    message_id = None
                    payload_dict = json.loads(payload)
                    message_id = payload_dict.get('message_id')
                    
                    if message_id in processed_messages:
                        logger.warning(f"Skipping duplicate message: {message_id}")
                        continue

                    processed_messages.add(message_id)
                    if len(processed_messages) > 1000:  # Limit the size of the set
                        processed_messages.pop()

                    handler = topic_from_handler(self.topic_handlers, topic)
                    if handler:
                        await handler(message)
                    else:
                        logger.warning(f"No handler found for topic: {topic}")
            except aiomqtt.MqttError as me:
                logger.error(f"MQTT Error in message loop: {me}")
                await self.handle_disconnect()
            except Exception as e:
                logger.error(f"Unexpected error in message loop: {e}")
            finally:
                await asyncio.sleep(5)
                

            
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
                self.subscribed_topics.add(topic)
                asyncio.create_task(self.client.subscribe(topic))

    def remove_topic_handler(self, topic: str):
        if topic in self.topic_handlers:
            del self.topic_handlers[topic]
            logger.info(f"Removed handler for topic {topic}")


    async def publish(self, topic: str, payload: any, qos: int = 1):
        try:
            payload, message_id = self._format_payload(payload)
            
            if isinstance(payload, str):
                payload = payload.encode('utf-8')
            
            await self.message_queue.put((topic, payload, qos))
            logger.debug(f"Queued message {message_id} for topic {topic} with QoS {qos}: {payload}")
            return True
        except Exception as e:
            logger.error(f"Error queueing message for publication: {e}")
            return False

    async def _outgoing(self):
        while self.running:
            try:
                topic, payload, qos = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                try:
                    await self.client.publish(topic, payload, qos)
                except Exception as e:
                    logger.error(f"Failed to publish message: {e}")
                    await self.message_queue.put((topic, payload, qos))
            except asyncio.TimeoutError:
                pass

    async def _loop(self):
        while self.running:
            if self.status == self.STATUS_DISABLED:
                await self.disconnect()
            elif self.status == self.STATUS_DISCONNECTED:
                try:
                    await self.connect()
                except Exception as e:
                    logger.error(f"Failed to connect: {e}")
                    await asyncio.sleep(10)
                    continue
            await asyncio.sleep(10)
            
