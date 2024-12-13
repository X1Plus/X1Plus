"""
[module]
enabled=true
[end]
"""
from x1plus.services.x1plusd.actions import register_action

import logging

logger = logging.getLogger(__name__)

@register_action("gcode")
async def _action_gcode(handler, subconfig):
    logger.debug(f"gcode action: {subconfig}")
    if type(subconfig) != str:
        raise TypeError(f"gcode parameter {subconfig} was not str")
    await handler.daemon.mqtt.publish_request({ "print": { "command": "gcode_line", "sequence_id": "0", "param": subconfig } })
