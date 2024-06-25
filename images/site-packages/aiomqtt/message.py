# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import sys

import paho.mqtt.client as mqtt
from paho.mqtt.properties import Properties

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from .topic import Topic, TopicLike
from .types import PayloadType


class Message:
    """Wraps the paho-mqtt message class to allow using our own matching logic.

    This class is not meant to be instantiated by the user. Instead, it is yielded by
    the async generator ``Client.messages``.

    Args:
        topic: The topic the message was published to.
        payload: The message payload.
        qos: The quality of service level of the subscription that matched the message.
        retain: Whether the message is a retained message.
        mid: The message ID.
        properties: (MQTT v5.0 only) The properties associated with the message.

    Attributes:
        topic (aiomqtt.client.Topic):
            The topic the message was published to.
        payload (str | bytes | bytearray | int | float | None):
            The message payload.
        qos (int):
            The quality of service level of the subscription that matched the message.
        retain (bool):
            Whether the message is a retained message.
        mid (int):
            The message ID.
        properties (paho.mqtt.properties.Properties | None):
            (MQTT v5.0 only) The properties associated with the message.
    """

    def __init__(  # noqa: PLR0913
        self,
        topic: TopicLike,
        payload: PayloadType,
        qos: int,
        retain: bool,
        mid: int,
        properties: Properties | None,
    ) -> None:
        self.topic = Topic(topic) if not isinstance(topic, Topic) else topic
        self.payload = payload
        self.qos = qos
        self.retain = retain
        self.mid = mid
        self.properties = properties

    @classmethod
    def _from_paho_message(cls, message: mqtt.MQTTMessage) -> Self:
        return cls(
            topic=message.topic,
            payload=message.payload,
            qos=message.qos,
            retain=message.retain,
            mid=message.mid,
            properties=message.properties if hasattr(message, "properties") else None,
        )

    def __lt__(self, other: Self) -> bool:
        return self.mid < other.mid
