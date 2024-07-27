import os
import subprocess
import asyncio
from pathlib import Path

import aiohttp
from aiohttp import web

import x1plus.utils
from .dbus import *
from jeepney import DBusAddress, new_method_call, MessageType

logger = logging.getLogger(__name__)
access_logger = logging.getLogger(__name__ + ".access")

PROTOCOL_VERSION = 0

class HTTPService():
    def __init__(self, router, daemon, **kwargs):
        self.daemon = daemon
        self.daemon.settings.on("http.enabled", lambda: asyncio.create_task(self.sync_startstop()))
        self.router = router
        self.runner = None
        self.site = None
        self.app = web.Application()
        
        if x1plus.utils.is_emulating():
            static_path = Path(__file__).resolve().parent.parent.parent.parent.parent.parent / 'share' / 'www'
        else:
            static_path = "/opt/x1plus/share/www"
        logger.info(f"x1plus httpd will serve from {static_path}")
        self.app.add_routes([web.get('/hello', self.route_hello), web.get('/ws', self.route_websocket), web.static("/", static_path)])
    
    async def route_hello(self, request):
        return web.Response(text="Hello, world")

    async def websocket_handle_msg(self, ws, msg):
        if msg.type == aiohttp.WSMsgType.ERROR:
            logger.error(f"websocket died with exception {ws.exception()}")
            raise Exception(ws.exception())
            
        # all exceptions here will get handled by the top level exception handler
        assert msg.type == aiohttp.WSMsgType.TEXT
        pkt = msg.json()
            
        # all jsonrpc messages are RPCs here, not notifications, and so they should all have IDs
        assert pkt['jsonrpc'] == '2.0'
        assert pkt['id']
        rv = {'jsonrpc': '2.0', 'id': pkt['id']}
        if pkt['method'] == 'dbus.call':
            try:
                addr = DBusAddress(pkt['params']['object'], bus_name=pkt['params']['bus_name'], interface=pkt['params']['interface'])
                method = pkt['params']['method']
                params = pkt['params']['params']
            except Exception as e:
                pkt['error'] = {'code': -32602, 'message': str(e)}
                await ws.send_json(rv)
                return
            dmsg = new_method_call(addr, method, 's', (json.dumps(params), ))
            reply = await self.router.send_and_get_reply(dmsg)
            if reply.header.message_type == MessageType.error:
                rv['error'] = {'code': 1, 'message': reply.header.fields.get(HeaderFields.error_name, 'unknown-error') }
            else:
                rv['result'] = json.loads(reply.body[0])
        else:
            pkt['error'] = {'code': -32601, 'message': 'method not found'}
        await ws.send_json(rv)

    async def websocket_main(self, ws):
        "Once a websocket has authenticated, this implements the main loop."
        
        with self.daemon.mqtt.request_messages() as requestq, self.daemon.mqtt.report_messages() as reportq:
            ws_future = None
            requestq_future = None
            reportq_future = None
            
            while True:
                # XXX: This is sort of unpleasant and really could use to be
                # refactored...  but it work.

                if ws_future == None:
                    ws_future = asyncio.ensure_future(anext(ws)) # no await!
                if requestq_future == None:
                    requestq_future = asyncio.ensure_future(requestq.get()) # no await!
                if reportq_future == None:
                    reportq_future = asyncio.ensure_future(reportq.get()) # no await!
                
                await asyncio.wait((ws_future, requestq_future, reportq_future, ), return_when=asyncio.FIRST_COMPLETED)

                if ws_future.done():
                    try:
                        msg = ws_future.result()
                    except StopAsyncIteration:
                        break
                    await self.websocket_handle_msg(ws, msg)
                    ws_future = None

                if requestq_future.done():
                    request = requestq_future.result()
                    await ws.send_json({'jsonrpc': '2.0', 'method': 'mqtt.notify', 'params': { 'topic': 'request', 'payload': request } })
                    requestq_future = None

                if reportq_future.done():
                    report = reportq_future.result()
                    await ws.send_json({'jsonrpc': '2.0', 'method': 'mqtt.notify', 'params': { 'topic': 'report', 'payload': report } })
                    reportq_future = None
    
    async def route_websocket(self, request):
        ws = web.WebSocketResponse(autoping=True, heartbeat=10)
        await ws.prepare(request)
        
        access_logger.info("websocket is connecting")
        
        try:
            await ws.send_json({"jsonrpc": "2.0", "method": "hello", "params": { "x1plus_protocol_version": PROTOCOL_VERSION }})
            
            # the first packet should be an auth packet; we just special
            # case this, I suppose
            authpkt = await ws.receive_json()
            try:
                assert authpkt["method"] == "auth"
                assert 'id' in authpkt
                password = authpkt["params"]["password"]
            except Exception as e:
                await ws.send_json({"jsonrpc": "2.0", "error": {"code": -32601, "message": "first packet must be a valid auth packet"}})
                await ws.close()
                return ws
            
            system_password = self.daemon.settings.get('http.password', None)
            if system_password is None: # we have to do it the hard way, I guess
                with open('/config/device/access_token', 'r') as f:
                    system_password = f.read().strip()
            if system_password != "" and password != system_password:
                await ws.send_json({"jsonrpc": "2.0", "error": {"code": -1, "message": "permission denied"}, "id": authpkt['id']})
                await ws.close()
                return ws
            await ws.send_json({"jsonrpc": "2.0", "result": 0, "id": authpkt['id']})
            
            await self.websocket_main(ws)
        except Exception as e:
            logger.error(f"websocket had exception {e}")
            import traceback
            traceback.print_exception(e)
            await ws.close()

        logger.info("goodbye, websocket")
        return ws
    
    async def task(self):
        await self.sync_startstop()

    async def sync_startstop(self):
        enabled = self.daemon.settings.get("http.enabled", False)
        
        if self.site and not enabled:
            await self.site.stop()
            self.site = None
        
        if self.runner and not enabled:
            await self.runner.cleanup()
            self.runner = None
        
        if enabled and not self.runner:
            self.runner = web.AppRunner(self.app, access_log=access_logger, logger=logger)
            await self.runner.setup()
        
        if enabled and not self.site:
            bind_addr = self.daemon.settings.get("http.bind.addr", "0.0.0.0")
            bind_port = self.daemon.settings.get("http.bind.port", 80)
            self.site = web.TCPSite(self.runner, bind_addr, bind_port)
            await self.site.start()
            logger.info(f"X1Plusd httpd is running on {bind_addr}:{bind_port}")
