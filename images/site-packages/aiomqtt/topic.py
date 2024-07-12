# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import dataclasses
import sys

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias


MAX_TOPIC_LENGTH = 65535


@dataclasses.dataclass(frozen=True)
class Wildcard:
    """MQTT wildcard that can be subscribed to, but not published to.

    A wildcard is similar to a topic, but can optionally contain ``+`` and ``#``
    placeholders. You can access the ``value`` attribute directly to perform ``str``
    operations on a wildcard.

    Args:
        value: The wildcard string.

    Attributes:
        value: The wildcard string.
    """

    value: str

    def __str__(self) -> str:
        return self.value

    def __post_init__(self) -> None:
        """Validate the wildcard."""
        if not isinstance(self.value, str):
            msg = "Wildcard must be of type str"
            raise TypeError(msg)
        if (
            len(self.value) == 0
            or len(self.value) > MAX_TOPIC_LENGTH
            or "#/" in self.value
            or any(
                "+" in level or "#" in level
                for level in self.value.split("/")
                if len(level) > 1
            )
        ):
            msg = f"Invalid wildcard: {self.value}"
            raise ValueError(msg)


WildcardLike: TypeAlias = "str | Wildcard"


@dataclasses.dataclass(frozen=True)
class Topic(Wildcard):
    """MQTT topic that can be published and subscribed to.

    Args:
        value: The topic string.

    Attributes:
        value: The topic string.
    """

    def __post_init__(self) -> None:
        """Validate the topic."""
        if not isinstance(self.value, str):
            msg = "Topic must be of type str"
            raise TypeError(msg)
        if (
            len(self.value) == 0
            or len(self.value) > MAX_TOPIC_LENGTH
            or "+" in self.value
            or "#" in self.value
        ):
            msg = f"Invalid topic: {self.value}"
            raise ValueError(msg)

    def matches(self, wildcard: WildcardLike) -> bool:
        """Check if the topic matches a given wildcard.

        Args:
            wildcard: The wildcard to match against.

        Returns:
            True if the topic matches the wildcard, False otherwise.
        """
        if not isinstance(wildcard, Wildcard):
            wildcard = Wildcard(wildcard)
        # Split topics into levels to compare them one by one
        topic_levels = self.value.split("/")
        wildcard_levels = str(wildcard).split("/")
        if wildcard_levels[0] == "$share":
            # Shared subscriptions use the topic structure: $share/<group_id>/<topic>
            wildcard_levels = wildcard_levels[2:]

        def recurse(tl: list[str], wl: list[str]) -> bool:
            """Recursively match topic levels with wildcard levels."""
            if not tl:
                if not wl or wl[0] == "#":
                    return True
                return False
            if not wl:
                return False
            if wl[0] == "#":
                return True
            if tl[0] == wl[0] or wl[0] == "+":
                return recurse(tl[1:], wl[1:])
            return False

        return recurse(topic_levels, wildcard_levels)


TopicLike: TypeAlias = "str | Topic"
