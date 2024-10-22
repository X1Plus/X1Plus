import asyncio
import logging, logging.handlers
import os
import setproctitle

from . import X1PlusDaemon, logger

setproctitle.setproctitle(__spec__.name)

logger.setLevel(logging.DEBUG)

slh = logging.handlers.SysLogHandler(address="/dev/log")
slh.setLevel(logging.INFO)
slh.setFormatter(logging.Formatter("%(name)s: %(message)s"))
logger.addHandler(slh)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(logging.Formatter("[%(asctime)s] %(name)s: %(levelname)s: %(message)s"))
logger.addHandler(ch)

PID_FILE = '/var/run/x1plusd.pid'


def exceptions(loop, ctx):
    logger.error(f"exception in coroutine: {ctx['message']} {ctx.get('exception', '')}")
    loop.default_exception_handler(ctx)
    try:
        asyncio.get_running_loop().stop()
    except:
        pass


async def start():
    x1plusd = await X1PlusDaemon.create()
    await x1plusd.start()


def is_already_running():
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)  # Check if the process is still running
        return True
    except (IOError, ValueError, OSError):
        return False


# catchall exception
try:
    # Check if we are already running
    if is_already_running():
        logger.error("x1plusd is already running. Exiting.")
        exit(1)

    # Create the PID file
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))

    loop = asyncio.new_event_loop()
    loop.set_exception_handler(exceptions)
    loop.create_task(start())
    loop.run_forever()
except Exception as e:
    logger.error(f"Exception occurred: {e}")
finally:
    logger.error("x1plusd event loop has terminated!")
    loop.run_until_complete(loop.shutdown_asyncgens())
    os.unlink(PID_FILE)
    loop.close()
