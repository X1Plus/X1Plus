import logging

logger = logging.getLogger(__name__)

ANIMATIONS = {}
DEFAULT_ANIMATIONS = [ 'running', 'finish', 'paused', 'failed', 'rainbow' ]

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

