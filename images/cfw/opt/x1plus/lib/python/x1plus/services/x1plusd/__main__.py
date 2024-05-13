from . import main, logger
import asyncio

import setproctitle
setproctitle.setproctitle(__spec__.name)

# TODO: check if we are already running
loop = asyncio.new_event_loop()
loop.create_task(main())
try:
    loop.run_forever()
finally:
    logger.error("x1plusd event loop has terminated!")
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()
