"""
[module]
default_enabled=true
[end]
"""
from x1plus.services.x1plusd.actions import register_action

import logging
import json
import yaml

logger = logging.getLogger(__name__)

@register_action("file")
async def _action_file(handler, subconfig):
    if type(subconfig) != str:
        raise TypeError(f"parameter {subconfig} to 'file' action was not a string")
    if subconfig[0] != "/":
        subconfig = f"/sdcard/{subconfig}"
    with open(subconfig) as f:
        contents_raw = f.read()
    
    contents = None
    if contents is None:
        try:
            contents = json.loads(contents_raw)
        except:
            pass
    if contents is None:
        try:
            contents = yaml.safe_load(contents_raw)
        except:
            pass
    if contents is None:
        raise ValueError(f"file {subconfig} seemed to be neither a yaml file nor a json file")
    return await handler.execute_step(contents)
