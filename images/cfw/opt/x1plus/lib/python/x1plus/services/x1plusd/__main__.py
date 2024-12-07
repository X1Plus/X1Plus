import asyncio
import logging, logging.handlers
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


def exceptions(loop, ctx):
    logger.error(f"exception in coroutine: {ctx['message']} {ctx.get('exception', '')}")
    loop.default_exception_handler(ctx)
    try:
        asyncio.get_running_loop().stop()
    except:
        pass

# TODO: check if we are already running
loop = asyncio.new_event_loop()
loop.set_exception_handler(exceptions)

async def start():
    try:
        x1plusd = await X1PlusDaemon.create()
        for key in x1plusd.watched_keys:
            x1plusd.settings.on(key, lambda: stop())

        await x1plusd.start() 
    except Exception as e:
        logger.error(f"Error starting x1plusd. {e.__class__.__name__}: {e}")
        if loop:
            await stop_loop()

loop.create_task(start())

def stop():
    asyncio.create_task(stop_loop())

async def stop_loop():
    logger.info("Stopping x1plusd after module config change")
    current_task = asyncio.current_task(loop=loop)
    tasks = [task for task in asyncio.all_tasks(loop=loop) if task != current_task]
    for task in tasks:
        task.cancel()
    await asyncio.sleep(5)
    quit()

try:
    loop.run_forever()
finally:
    logger.error("x1plusd event loop has terminated!")
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()
