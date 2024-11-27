"""
[action-type]
name=syslog
[end]
"""
from ..actions import register_action

import logging

logger = logging.getLogger(__name__)

@register_action("syslog")
async def _action_syslog(handler, subconfig):
    logger.info(f"syslog action: {subconfig}")