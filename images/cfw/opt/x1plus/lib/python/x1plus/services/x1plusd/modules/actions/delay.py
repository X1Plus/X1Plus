"""
[module]
enabled=true
[end]
"""
from x1plus.services.x1plusd.actions import register_action

import asyncio
import logging

logger = logging.getLogger(__name__)

@register_action("delay")
async def _action_delay(handler, subconfig):
    logger.debug(f"delay action: {subconfig}")
    if type(subconfig) != int and type(subconfig) != float:
        raise TypeError(f"delay parameter {subconfig} was not numberish")
    await asyncio.sleep(subconfig)