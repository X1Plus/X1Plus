"""
RTSP Media Session setup and control
"""
import asyncio
import calendar
import json
import logging
import math
import re
from datetime import datetime
from typing import Set
from urllib.parse import urlparse

from aiortsp.rtcp.stats import RTCPStats
from aiortsp.transport import RTPTransport
from .errors import RTSPError
from .parser import RTSPResponse
from .sdp import SDP

default_logger = logging.getLogger(__name__)


def sanitize_rtsp_url(url: str) -> str:
    """
    Sanitize an RTSP url, removing exotic scheme and authentication.
    """
    p_url = urlparse(url)
    scheme = p_url.scheme
    if scheme != 'rtsp' and scheme != 'rtsps':
        scheme = 'rtsp'
    return p_url._replace(
        scheme=scheme,
        netloc=f'{p_url.hostname}' if p_url.port is None else f'{p_url.hostname}:{p_url.port}'
    ).geturl()


class RTSPMediaSession:
    """
    RTSP Media Session
    TODO Refactor to support multiple medias
    """

    def __init__(self, connection, media_url, transport: RTPTransport, media_type='video', logger=None):
        self.connection = connection
        self.media_url = sanitize_rtsp_url(media_url)
        self.transport = transport
        self.media_type = media_type
        self.logger = logger or default_logger

        self.is_setup = False
        self.sdp = None
        self.server_rtp = None
        self.server_rtcp = None

        self.session_id = None
        self.session_keepalive = 60
        self.session_options: Set[str] = set()

    async def __aenter__(self):
        """
        At entrance of env, we expect the stream to be ready for playback
        """
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_val and exc_type != asyncio.CancelledError:
            self.logger.error('exception during session: %s %s', exc_type, exc_val)
        await self.teardown()

    async def setup(self):
        """
        Perform SETUP
        """
        # Get supported options
        resp = await self._send('OPTIONS', url=self.media_url)
        self.save_options(resp)

        # Get SDP
        resp = await self._send('DESCRIBE', headers={
            'Accept': 'application/sdp'
        })

        if 'content-base' in resp.headers:
            self.media_url = resp.headers['content-base']
            self.logger.info('using base url: %s', self.media_url)

        self.logger.debug('received SDP:\n%s', resp.content)
        self.sdp = SDP(resp.content)
        self.logger.debug('parsed SDP:\n%s', json.dumps(self.sdp, indent=2))

        setup_url = self.sdp.setup_url(self.media_url, media_type=self.media_type)
        self.logger.info('setting up using URL: %s', setup_url)

        # --- SETUP <url> RTSP/1.0 ---
        headers = {}
        self.transport.on_transport_request(headers)
        resp = await self.connection.send_request('SETUP', url=setup_url, headers=headers)
        self.transport.on_transport_response(resp.headers)
        self.logger.info('stream correctly setup: %s', resp)

        # Store session ID
        self.save_session(resp)

        # Warm up transport
        await self.transport.warmup()

    @property
    def stats(self) -> RTCPStats:
        """Stats convenient accessor"""
        return self.transport.stats

    def save_options(self, resp: RTSPResponse):
        """
        Extract method lists from OPTIONS response
        """
        # Extract session Id
        if 'public' not in resp.headers:
            raise RTSPError('error on OPTIONS: `Public` not found')

        self.session_options = {o.strip().upper() for o in resp.headers['public'].split(',')}
        self.logger.info('session options: %s', self.session_options)

    def save_session(self, resp: RTSPResponse):
        """
        Extract session ID and timeout
        """
        # Extract session Id
        if 'session' not in resp.headers:
            raise RTSPError('error on SETUP: session not found')

        # Get session id
        session_params = resp.headers['session'].split(';')
        self.session_id = session_params[0].strip()
        timeout = 60
        if len(session_params) > 1:
            for option in session_params[1:]:
                option = option.strip()
                if not option.startswith('timeout'):
                    continue

                _, timeout_ = option.split('=', 1)
                timeout = int(timeout_)

        self.session_keepalive = int(timeout * 0.9)
        self.logger.info(
            'session id: %s, timeout: %s, keep_alive: %s',
            self.session_id, timeout, self.session_keepalive
        )

    async def teardown(self):
        """
        Perform TEARDOWN
        """
        if self.connection.running:
            self.logger.info('stopping session/playback...')
            resp = await self._send('TEARDOWN')
            self.logger.debug('response to teardown: %s', resp)
            return resp

        self.logger.info('session closed (no transport)')

    async def _send(self, method, url=None, headers=None):
        if headers is None:
            headers = {}
        if self.session_id:
            headers['Session'] = self.session_id
        return await self.connection.send_request(method, url or self.media_url, headers)

    @staticmethod
    def ts_to_clock(seek: float) -> str:
        """
        Must return a string in the following format:
            20190322T043720.003Z
        :param seek: utc timestamp
        """
        res = datetime.utcfromtimestamp(seek).strftime('%Y%m%dT%H%M%S')
        rem = seek - math.floor(seek)
        if rem:
            res += str(round(rem, 3))[1:]
        res += 'Z'
        return res

    @staticmethod
    def response_to_ts(resp, default_ts):
        """
        Try to return real play time, or default if not found
        """
        try:
            res = re.match(r'^ *clock *= *(?P<date>\d{8})T(?P<time>\d{6})(\.(?P<milli>\d+))?Z *-', resp.headers.get('range'))

            if not res:
                return default_ts

            content = res.groupdict()
            dt = datetime.strptime(content['date'] + content['time'], '%Y%m%d%H%M%S')

            ts = calendar.timegm(dt.timetuple())

            if content["milli"]:
                ts += float(f'0.{content["milli"]}')

            return ts
        except Exception:  # pylint: disable=broad-except
            # @TODO Should we log anything?
            return default_ts

    async def play(self, seek=None, speed=1):
        """
        Send a PLAY request
        :param seek: UTC timestamp where to ask to start. By default, uses 'now'.
        :param speed: Replay speed. Could be used for fast forward playing.
        """
        if seek:
            start = self.ts_to_clock(seek)
            range_ = f'clock={start}-'
        else:
            start = 'now'
            range_ = 'npt=now-'

        self.logger.info(
            'start playing %s at time `%s` and speed `%s`...',
            self.media_url, start, speed
        )

        resp = await self._send('PLAY', headers={
            'Scale': speed,
            'Range': range_
        })
        self.logger.debug('response to play: %s', resp)
        return resp

    async def pause(self):
        """
        Send a PAUSE, temporarily stopping RTP flow but keeping session alive.
        """
        self.logger.debug('sending keep alive')
        resp = await self._send('PAUSE')
        self.logger.debug('response to pause: %s', resp)
        return resp

    async def keep_alive(self):
        """
        Send a GET_PARAMETER or OPTIONS message in order to keep session alive.
        """
        self.logger.debug('sending keep alive')

        # We must send a supported command
        if 'GET_PARAMETER' in self.session_options:
            resp = await self._send('GET_PARAMETER')
        elif 'OPTIONS' in self.session_options:
            resp = await self._send('OPTIONS')
        else:
            self.logger.info('Does not support GET_PARAMETER or OPTIONS: not sending keep alive.')
            resp = None

        self.logger.debug('response to keep_alive: %s', resp)
        return resp
