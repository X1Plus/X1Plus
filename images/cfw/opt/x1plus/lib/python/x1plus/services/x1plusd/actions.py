"""
Actions trigger mechanism

Many different things on the X1 system need to take actions.  For instance,
the on-board buttons have long been customizable with fixed actions, but
there has been some demand to have them do more interesting things.  The
actions mechanism solves this by adding a command set that can affect
various parts of the system.  Additionally, the G-code interpreter can now
be interrupted and send messages in real-time synchronously with the G-code
stream from a print (see x1plus.mcproto).

The actions trigger mechanism operates on JSON; an action is either a list
of actions, or a dictionary with exactly one key (representing the name of
an action), mapping to a parameter of type depending on the action.  A list
executes each subaction in sequence, waiting for action completion.  For
instance, consider the following JSON objects, that would all be conceivably
valid actions, if their respective keys were implemented:

  { "buzzer": { "duration": 0.2 } }
  
  [ { "shutter": true }, { "delay": 1 }, { "gcode": "M400 W0" } ]
  
  { "led": { "animation": "green", "timeout": 5 } }
  
  [ { "buzzer": { "duration": 0.2 } },
    { "display": { "message": "The nozzle is ready for cold pull.  Apply tension on the filament, then tap OK.", "wait_for_confirmation": true } },
    { "gcode": "M400 W0" } ]

At some point in the future, it probably would be reasonable to write a
predicate mechanism, for actions such as `{"if": {"condition":
PREDICATE_OBJECT, "then": ACTION}}`, or `{"wait_until": {"condition":
PREDICATE_OBJECT}}`.  For now, actions run in a straight line.

It would probably be ergonomic to write action scripts in YAML and convert
them to JSON before embedding them in G-code.
"""

import asyncio
import logging
import json
import yaml

from .dbus import *

logger = logging.getLogger(__name__)

_registered_actions = {}

ACTIONS_INTERFACE = "x1plus.actions"
ACTIONS_PATH = "/x1plus/actions"

class ActionHandler(X1PlusDBusService):
    def __init__(self, daemon, **kwargs):
        self.daemon = daemon
        super().__init__(
            dbus_interface=ACTIONS_INTERFACE, dbus_path=ACTIONS_PATH, **kwargs
        )

    async def dbus_Execute(self, req):
        async def subtask():
            logger.info("starting ExecuteAction from dbus")
            await self.execute(req)
            logger.info("action execution complete")
        asyncio.create_task(subtask())
        return None
    
    # actionobj is a parsed json object.  execute is cancellable!
    async def execute_step(self, actionobj):
        if type(actionobj) == list:
            for obj in actionobj:
                await self.execute_step(obj)
        elif type(actionobj) == dict:
            if len(actionobj) != 1:
                raise ValueError(f"action object {actionobj} had too many keys")
            (action, subconfig) = next(iter(actionobj.items()))
            if action not in _registered_actions:
                raise ValueError(f"action object {actionobj} had invalid action")
            await _registered_actions[action](self, subconfig)
        else:
            raise TypeError(f"action object {actionobj} had incorrect type")
    
    async def execute(self, actionobj):
        try:
            await self.execute_step(actionobj)
        except Exception as e:
            logger.error(f"action execution failed: {e.__class__.__name__}: {e}")

def register_action(name, handler = None):
    """
    Register an action by name with the actions subsystem.
    
    If used with handler == None, then behaves like a decorator.
    """
    def decorator(handler):
        assert name not in _registered_actions
        _registered_actions[name] = handler
        return handler

    if handler is None:
        return decorator
    else:
        decorator(handler)

###

@register_action("syslog")
async def _action_syslog(handler, subconfig):
    logger.info(f"syslog action: {subconfig}")


@register_action("gcode")
async def _action_gcode(handler, subconfig):
    logger.debug(f"gcode action: {subconfig}")
    if type(subconfig) != str:
        raise TypeError(f"gcode parameter {subconfig} was not str")
    await handler.daemon.mqtt.publish_request({ "print": { "command": "gcode_line", "sequence_id": "0", "param": subconfig } })


@register_action("delay")
async def _action_delay(handler, subconfig):
    logger.debug(f"delay action: {subconfig}")
    if type(subconfig) != int and type(subconfig) != float:
        raise TypeError(f"delay parameter {subconfig} was not numberish")
    await asyncio.sleep(subconfig)


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
