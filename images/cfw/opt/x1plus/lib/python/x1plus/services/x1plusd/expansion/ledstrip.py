import abc
import asyncio
import time
import logging

logger = logging.getLogger(__name__)

ANIMATIONS = {}
DEFAULT_ANIMATIONS = [ 'running', 'finish', 'paused', 'failed', 'rainbow' ]

class BaseLedStripDriver(abc.ABC):
    def __init__(self):
        assert self.daemon, "daemon missing?"
        assert self.config, "config missing?"

        self.n_leds = int(self.config['leds'])
        
        self.put(b'\x00\x00\x00' * 128) # clear out a long strip
        
        self.anim_task = None
        self.curanim = None

        # the 'animations' key is a list that looks like:
        #
        #   [ 'paused', { 'rainbow': { 'brightness': 0.5 } } ]
        self.anim_list = []   
        self.last_gcode_state = None
        self.anim_watcher = None

        for anim in self.config.get('animations', DEFAULT_ANIMATIONS):
            if type(anim) == str and ANIMATIONS.get(anim, None):
                self.anim_list.append(ANIMATIONS[anim](self, {}))
                continue
            elif type(anim) != dict or len(anim) != 1:
                raise ValueError("animation must be either string or dictionary with exactly one key")
            
            (animname, subconfig) = next(iter(anim.items()))
            if ANIMATIONS.get(animname, None):
                self.anim_list.append(ANIMATIONS[animname](self, subconfig))

        self.anim_watcher = asyncio.create_task(self.anim_watcher_task())

    @abc.abstractmethod
    def put(self, bs):
        pass
    
    def disconnect(self):
        if self.anim_task:
            self.anim_task.cancel()
            self.anim_task = None
        self.anim_watcher.cancel()

    async def anim_watcher_task(self):
        with self.daemon.mqtt.report_messages() as report_queue:
            while True:
                msg = await report_queue.get()
                # we do not do anything with it, we just use this to
                # determine if the animation needs to be changed
                if self.daemon.mqtt.latest_print_status.get('gcode_state', None) is not None:
                    self.last_gcode_state = self.daemon.mqtt.latest_print_status['gcode_state']

                wantanim = None
                for anim in self.anim_list:
                    if anim.can_render():
                        wantanim = anim
                        break
                if wantanim != self.curanim:
                    logger.debug(f"switching to animation {wantanim} from {self.curanim}, print state is {self.daemon.mqtt.latest_print_status.get('gcode_state', None)}")
                    if self.anim_task:
                        self.anim_task.cancel()
                        self.anim_task = None
                    self.curanim = wantanim
                    if not wantanim:
                        self.put(b'\x00\x00\x00' * self.n_leds)
                    else:
                        self.anim_task = asyncio.create_task(anim.task())
    


def register_animation(name, clazz = None):
    """
    Register an ledstrip animation by name with the expansion ledstrip subsystem.
    
    If used with clazz == None, then behaves like a decorator.
    """
    def decorator(clazz):
        assert name not in ANIMATIONS
        ANIMATIONS[name] = clazz
        logger.info(f"registered LED strip animation \"{name}\"")
        return clazz

    if clazz is None:
        return decorator
    else:
        decorator(clazz)

