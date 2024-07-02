import os
import json
import logging
import subprocess

logger = logging.getLogger(__name__)

# Handles callbacks and topic handlers for X1Plus MQTT topics
# Note - this is just a starting point, quite a bad one, so I plan on rewriting this
#
# custom topics and handlers so far:
# 1) x1plus/settings: x1plus settings set/get
# 2) x1plus/update: x1plus ota check_now(), etc

class MQTTHandlers:
    def __init__(self, publisher):
        self.publisher = publisher
        
    async def x1plus_default(self, message):
        topic = message.topic.value
        logger.info(f"Received message on {topic} - {message.payload.decode('utf-8')}")
    
    # this is pure dogshit and I am going to delete it as soon as it's clear how we want to set this up
    async def x1plus_update(self, message):
        topic = message.topic.value
        logger.info(f"Received update message on {topic}")
        try:
            cmd = message.payload.decode('utf-8').strip().split(" ")
            resp = self.subproc(["x1plus", "ota", cmd[0]] + cmd[1:])
            await self.publisher("x1plus/update", resp)
        except Exception as e:
            logger.error(f"Error handling update command: {e}")

    async def x1plus_settings(self, message): 
        topic = message.topic.value
        logger.info(f"Settings modification request received on {topic}")
        try:
            cmd = message.payload.decode('utf-8').strip().split(" ")
            resp = self.subproc(["x1plus", "settings", cmd[0]] + cmd[1:])
            await self.publisher("x1plus/settings", resp)
        except Exception as e:
            logger.error(f"Error handling settings command: {e}")
            
    def subproc(self, cmd):
        try:
            return subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
        except subprocess.CalledProcessError as e:
            return f"Command error: {e.output.decode('utf-8')}"
        
def load_handlers(publisher):
    handlers = MQTTHandlers(publisher)
    return {
        "x1plus/update": handlers.x1plus_update,
        "x1plus/settings": handlers.x1plus_settings,
        "x1plus/print": handlers.x1plus_default,
    }
    
def topic_from_handler(handlers, topic):
    if topic in handlers:
        return handlers[topic]

    for pattern, handler in handlers.items():
        if pattern.endswith('*') and topic.startswith(pattern[:-1]):
            return handler

    return handlers["x1plus/default"]