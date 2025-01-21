"""
[X1PLUS_MODULE_INFO]
module:
  name: actions.syslog
  default_enabled: true
[END_X1PLUS_MODULE_INFO]
"""
from x1plus.services.x1plusd.actions import register_action

import logging

logger = logging.getLogger(__name__)

@register_action("syslog")
async def _action_syslog(handler, subconfig):
    logger.info(f"syslog action: {subconfig}")