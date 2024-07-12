# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.reasoncodes import ReasonCode


class MqttError(Exception):
    pass


class MqttCodeError(MqttError):
    def __init__(self, rc: int | ReasonCode | None, *args: Any) -> None:
        super().__init__(*args)
        self.rc = rc

    def __str__(self) -> str:
        if isinstance(self.rc, ReasonCode):
            return f"[code:{self.rc.value}] {self.rc!s}"
        if isinstance(self.rc, int):
            return f"[code:{self.rc}] {mqtt.error_string(self.rc)}"
        return f"[code:{self.rc}] {super().__str__()}"


class MqttConnectError(MqttCodeError):
    def __init__(self, rc: int | ReasonCode) -> None:
        if isinstance(rc, ReasonCode):
            super().__init__(rc)
            return
        msg = "Connection refused"
        try:
            msg += f": {_CONNECT_RC_STRINGS[rc]}"
        except KeyError:
            pass
        super().__init__(rc, msg)


class MqttReentrantError(MqttError): ...


_CONNECT_RC_STRINGS: dict[int, str] = {
    # Reference: https://github.com/eclipse/paho.mqtt.python/blob/v1.5.0/src/paho/mqtt/client.py#L1898
    # 0: Connection successful
    # 1: Connection refused - incorrect protocol version
    1: "Incorrect protocol version",
    # 2: Connection refused - invalid client identifier
    2: "Invalid client identifier",
    # 3: Connection refused - server unavailable
    3: "Server unavailable",
    # 4: Connection refused - bad username or password
    4: "Bad username or password",
    # 5: Connection refused - not authorised
    5: "Not authorised",
    # 6-255: Currently unused.
}
