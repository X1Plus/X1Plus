"""
Asyncio RTSP Connection module
This is the main interesting part for the user.
"""

import asyncio
import logging
import traceback
from typing import Callable

from aiortsp.__version__ import __version__
from .auth import BasicAuth, DigestAuth
from .errors import RTSPResponseError, RTSPConnectionError, RTSPTimeoutError
from .parser import RTSPParser, RTSPRequest, RTSPResponse, RTSPBinary

_logger = logging.getLogger('rtsp_client')


LINE_SPLIT_STR = '\r\n'
HEADER_END_STR = LINE_SPLIT_STR * 2
USER_AGENT = f'aiortsp/{__version__}'


class RTSPConnection(asyncio.Protocol):
    """
    Creates an RTSP connection for asyncio usage.

    It's as easy as:

    async with RTSPConnection(...) as conn:
          # Here you go, do your RTSP stuff
          resp = await conn.send_request('DESCRIBE', url)
    # Cleans properly the connection before leaving the context

    """

    def __init__(self, host, port, username=None, password=None, accept_auth=None, logger=None, ssl=None, timeout=10):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.accept_auth = [auth.lower() for auth in accept_auth] if accept_auth else ['basic', 'digest']
        self.default_timeout = timeout
        self.logger = logger or _logger
        self.ssl = ssl

        self._transport = None
        self.result = asyncio.Future()
        self.pending_msg = None
        self.active_requests = {}
        self._cseq = 1
        self._auth = None
        self.parser = RTSPParser()
        self.binary_handlers = {}

    async def __aenter__(self):
        await self.prepare()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()

    async def prepare(self):
        """
        Prepare connection
        :return:
        """
        loop = asyncio.get_event_loop()
        try:
            await asyncio.wait_for(
                loop.create_connection(lambda: self, self.host, self.port, ssl = self.ssl),
                self.default_timeout
            )
        except (asyncio.TimeoutError, OSError) as to:
            raise RTSPConnectionError(f'Unable to connect to {self.host}:{self.port}') from to

    def close(self):
        """
        Close connection
        """
        if self._transport:
            self._transport.close()

    def register_binary_handler(self, callback: Callable) -> int:
        """
        Register a binary callback. Return the ID which will be used for given protocol
        """
        idx = next(i for i in range(257) if i not in self.binary_handlers)

        assert idx < 256, 'not any binary handle left'

        self.binary_handlers[idx] = callback

        return idx

    def connection_made(self, transport):
        """Conforms asyncio.Protocol"""
        self._transport = transport

    def connection_lost(self, exc):
        """Conforms asyncio.Protocol"""
        self.logger.info('connection to RTSP server %s:%s closed (error: %s)', self.host, self.port, exc)
        self._transport = None
        if not self.result.done():
            if exc:
                error = RTSPConnectionError(f'RTSP connection lost: {exc}')
                error.__cause__ = exc
                self.result.set_exception(error)
            else:
                self.result.set_result('ok')

        # Close any pending request
        error = self.result.exception() if not self.result.cancelled() else None
        for request in self.active_requests.values():  # type: asyncio.Future
            if not request.done():
                request.set_exception(error or RTSPConnectionError('connection closed'))

    @property
    def running(self) -> bool:
        """
        Tells if currently running, ie if we have an open transport.
        """
        return self._transport is not None

    def on_binary(self, binary: RTSPBinary):
        """Handler for binary data received"""
        if binary.id in self.binary_handlers:
            # Call handler
            self.binary_handlers[binary.id](binary)
        else:
            self.logger.debug('BINARY data (%s bytes): %s', binary.length, binary.content)

    def on_response(self, response: RTSPResponse):
        """Handler for response received"""
        self.logger.debug('RESPONSE received: %s\n%s', response, response.content)

    def on_request(self, request: RTSPRequest):
        """
        Handle a request from server. Override for more fancy controls
        """
        self.logger.warning('request message received during session:\n%s', request.content)
        # @TODO We do not support requests for now: 551
        self.send_response(request, 551, 'Option not supported')

    def data_received(self, data: bytes):
        """Parse and distribute received messages"""
        try:
            # self.logger.debug('<<< receiving data: %s', data)

            for msg in self.parser.parse(data):
                # self.logger.debug('message done: %s', msg)
                if msg.type == 'response':
                    self.on_response(msg)

                    if msg.cseq in self.active_requests:
                        self.active_requests[msg.cseq].set_result(msg)

                elif msg.type == 'binary':
                    self.on_binary(msg)

                elif msg.type == 'request':
                    self.on_request(msg)

            return

        except Exception as ex:  # pylint: disable=broad-except
            self.logger.error('error on received data: %s\n%s', ex.__class__.__name__, data)

            error = RTSPConnectionError('invalid data received from RTSP connection')
            error.__cause__ = ex
            self.result.set_exception(error)

            if self._transport:
                self._transport.close()
            traceback.print_exc()

    def _next_seq(self):
        cseq = self._cseq
        self._cseq += 1
        return cseq

    def handle_401(self, resp: RTSPResponse):
        """
        Handle a 401 (Unauthorized) message.
        :param resp: Response from server containing challenge (digest, basic)
        :return: True if client is authorized to retry
        """
        if not self._auth and self.username and self.password:
            # # No authentication selected yet: use one!
            # if not (self.username and self.password):
            #     raise RTSPResponseError('No valid Authentication provided (username/password)', resp)

            # Check what is supported
            www_auth = resp.headers.get('www-authenticate')

            if not www_auth:
                raise RTSPResponseError('Invalid 401 response received (no www-authenticate)', resp)

            if not isinstance(www_auth, list):
                www_auth = [www_auth]

            self.logger.debug('authorization attempt, allowed: %s, proposed: %s', self.accept_auth, www_auth)

            if any(a.startswith('Basic ') for a in www_auth) and 'basic' in self.accept_auth:
                self.logger.debug('selecting BASIC authentication')
                self._auth = BasicAuth(self.username, self.password)
            elif any(a.startswith('Digest ') for a in www_auth) and 'digest' in self.accept_auth:
                self.logger.debug('selecting DIGEST authentication')
                self._auth = DigestAuth(self.username, self.password)

        if self._auth:
            return self._auth.handle_401(resp.headers)

        return False

    def handle_ok(self, resp: RTSPResponse):
        """
        Handle an OK (in terms of authentication) response.
        There may be extra pieces of information for Auth.
        :param resp:
        :return:
        """
        if self._auth:
            self._auth.handle_ok(resp.headers)

    def send_message(self, msg, cseq, headers, body: bytes = None):
        """
        Send a 'message' (request or reply) with given cseq and headers
        """
        if not self._transport:
            self.logger.error('transport is closed')
            return

        # Always write CSeq first
        msg += f'{LINE_SPLIT_STR}CSeq: {cseq}'

        headers['User-Agent'] = USER_AGENT

        if body:
            headers['Content-Length'] = len(body)

        for k, v in headers.items():
            msg += f'{LINE_SPLIT_STR}{k}: {v}'

        msg += HEADER_END_STR  # End of headers

        data = msg.encode()

        if body:
            data += body

        self._transport.write(data)
        self.logger.debug('>>> sending msg:\n%s\n', msg)

    async def send_request(self, method, url, headers=None, timeout=None, body: bytes = None) -> RTSPResponse:
        """
        Send an RTSP request.
        :param method: RTSP method to be sent
        :param url: URL to be given in the RTSP request header
        :param headers: dict of optional headers to add
        :param timeout: timeout for getting a response
        :param body: Content body. If specified, a 'Content-Type' header should be added.
        :return: RTSPResponse
        """
        request = f'{method} {url} RTSP/1.0'

        if headers is None:
            headers = {}

        if self._auth:
            self._auth.make_auth(method, url, headers)

        cseq = self._next_seq()
        self.active_requests[cseq] = asyncio.Future()

        try:
            self.send_message(request, cseq, headers, body)

            resp = await asyncio.wait_for(self.active_requests[cseq], timeout or self.default_timeout)

            if resp.status == 401:
                self.logger.debug('unauthorized; see if we can try to authenticate')
                retry = self.handle_401(resp)
                if retry:
                    return await self.send_request(method, url, headers, timeout, body)
            else:
                # Response was successful (or at least not unauthorized...)
                self.handle_ok(resp)

            if not 200 <= resp.status < 300:
                raise RTSPResponseError(f'RTSP request error for {method} {url}', resp)

            return resp

        except asyncio.TimeoutError as to:
            raise RTSPTimeoutError('RTSP server failed to answer in time') from to

        finally:
            # Always cleanup the active request we had registered
            self.active_requests.pop(cseq, None)

    def send_response(self, request: RTSPRequest, code, msg, headers=None):
        """
        Send a response message to given request
        """
        if not self._transport:
            self.logger.error('transport is closed')
            return

        response = f'RTSP/1.0 {code} {msg}'

        if headers is None:
            headers = {}

        if 'session' in request.headers:
            headers['Session'] = request.headers['session']

        self.send_message(response, request.cseq, headers)

    def send_binary(self, idx: int, data: bytes):
        """
        Send a binary interleaved packet
        """
        if not self._transport:
            self.logger.error('transport is closed')
            return

        assert 0 <= idx < 256, f'invalid binary index: {idx}'

        m_len = len(data)

        msg = bytearray([ord('$'), idx, (m_len & 0xFF00) >> 8, m_len & 0xFF])
        msg += data

        self._transport.write(msg)
        self.logger.debug('>>> sending binary: %s', msg)
