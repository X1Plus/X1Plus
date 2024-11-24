"""
RTSP Stream parsing module
"""
from abc import abstractmethod
from binascii import hexlify
from io import BytesIO
from typing import Tuple, Iterator

from .errors import RTSPResponseError

CRLF = b'\r\n'


class RTSPMessage:
    """
    Base return class for any parsed object coming from an RTSP connection.
    """

    type = 'unknown'

    @abstractmethod
    def feed(self, data: bytes) -> Tuple[bytes, bool]:
        """
        Feed part with a line.
        :returns remaining bytes and True if done parsing current packet
        """

    @property
    def content(self) -> str:
        """Extract data from buffer as utf-8"""
        raise NotImplementedError

    @property
    def data(self) -> bytes:
        """Extract data from buffer as bytes"""
        raise NotImplementedError

    @property
    def length(self) -> int:
        """Return content length"""
        raise NotImplementedError


class HTTPLikeMsg(RTSPMessage):
    """
    Base class for both RTSP request & reply. Only the first line differs.
    """

    def __init__(self, buffer_size=2**16):
        self.headerlist = []
        self.headers = None
        self._untreated_data = b''
        self._data = None
        self.size = 0
        self._buf = ''
        self.buffer_size = buffer_size
        self.cseq = None
        self.content_type = None
        self.content_length = -1

        self.first_line = None

    @abstractmethod
    def parse_first_line(self, line: str):
        """
        Parse the first line received
        """

    def feed(self, data: bytes) -> Tuple[bytes, bool]:
        """
        Feed part with a line.
        :returns remaining bytes and True if done parsing current packet
        """
        done = False

        # Prepend any leftover from previous message
        data, self._untreated_data = self._untreated_data + data, b''

        while data and not done:
            if not self._data:
                # Still a header
                if b'\r\n' not in data:
                    # We don't have yet a full header: will have next time (hopefully)
                    self._untreated_data = data
                    data = b''
                    break
                line, data = data.split(b'\r\n', 1)
                done = self.parse_header(line.decode('utf-8') + '\r\n')
            else:
                data, done = self.parse_body(data)

        return data, done

    def parse_header(self, line) -> bool:
        """
        Add a header line
        :returns True if message is finished (no content)
        """
        if self.first_line is None:
            self.parse_first_line(line)
            return False

        line = line.strip()
        if not line:  # blank line -> end of header segment
            return self.finish_header()

        if line[0] in ' \t' and self.headerlist:
            name, value = self.headerlist.pop()
            self.headerlist.append((name, value + line.strip()))
        else:
            if ':' not in line:
                raise RTSPResponseError("Syntax error in header: No colon.")
            name, value = line.split(':', 1)
            self.headerlist.append((name.strip().lower(), value.strip()))
        return False

    def parse_body(self, data: bytes) -> Tuple[bytes, bool]:
        """
        Add data to the body.
        :returns (data, done) with:
            - data as leftover bytes after end of body
            - done a boolean True when body is complete
        """
        # Do we have too much data?
        rem_data = self.content_length - self.size
        assert rem_data > 0, 'we should not be here if already done'

        if len(data) > rem_data:
            leftover = data[rem_data:]
            data = data[:rem_data]
        else:
            leftover = b''

        self.size += len(data)
        self._data.write(data)

        if self.size > self.buffer_size:
            raise RTSPResponseError('Size of body exceeds maximum buffer size')

        return leftover, self.size == self.content_length

    def finish_header(self) -> bool:
        """Last header received; create buffer and extra useful info"""
        self.headers = {}
        for k, v in self.headerlist:
            if k in self.headers:
                if not isinstance(self.headers[k], list):
                    self.headers[k] = [self.headers[k]]
                self.headers[k].append(v)
            else:
                self.headers[k] = v
        self.content_type = self.headers.get('content-type', self.content_type)
        self.content_length = int(self.headers.get('content-length', '0'))
        self.cseq = int(self.headers.get('cseq', '-1'))

        has_content = self.content_length > 0

        if has_content:  # soon: if has_content := self.content_length > 0
            self._data = BytesIO()

        return not has_content

    @property
    def length(self) -> int:
        """Data length"""
        return len(self.data)

    @property
    def data(self) -> bytes:
        """Extract data from buffer as bytes"""
        val = b''
        if self._data:
            pos = self._data.tell()
            self._data.seek(0)
            try:
                val = self._data.read()
            finally:
                self._data.seek(pos)
        return val

    @property
    def content(self) -> str:
        """Extract data from buffer as utf-8"""
        return self.data.decode('utf-8')


class RTSPRequest(HTTPLikeMsg):
    """
    RTSP Request parser.
    """

    type = 'request'
    CLIENT_REQUESTS = (
        b'OPTIONS',
        b'DESCRIBE',
        b'ANNOUNCE',
        b'SETUP',
        b'PLAY',
        b'PAUSE',
        b'TEARDOWN',
        b'GET_PARAMETER',
        b'SET_PARAMETER',
        b'REDIRECT',
        b'RECORD',
    )

    def __init__(self, buffer_size=2 ** 16):
        super().__init__(buffer_size)

        self.request_url = None
        self.method = None

    def parse_first_line(self, line):
        self.first_line = line
        self.method, self.request_url, protocol = line.split(None, 2)
        assert protocol.strip().startswith('RTSP/1.0'), 'RTSP response should start with an RTSP/1.0 protocol marker'

    def __repr__(self):
        return f'<Request ' \
            f'type={self.method} ' \
            f'url={self.request_url} ' \
            f'headers={self.headers} ' \
            f'content-length={self.content_length}>'


class RTSPResponse(HTTPLikeMsg):
    """
    RTSP Response parser.
    """

    type = 'response'

    def __init__(self, buffer_size=2 ** 16):
        super().__init__(buffer_size)

        self.status = None
        self.status_msg = None

    def parse_first_line(self, line):
        assert line.startswith('RTSP/1.0'), 'RTSP response should start with an RTSP/1.0 protocol marker'
        self.first_line = line
        _, status, status_msg = line.split(None, 2)
        self.status = int(status.strip())
        self.status_msg = status_msg.strip()

    def __repr__(self):
        return f'<Response ' \
            f'status={self.status} ' \
            f'msg="{self.status_msg}"" ' \
            f'headers={self.headers} ' \
            f'content-length={self.content_length}>'


class RTSPBinary:
    """
    RTSP inline Binary parser.
    """

    type = 'binary'

    def __init__(self):
        self._buf = b''

    def feed(self, data):
        """
        Feed part with a line.
        :returns a frame if done
        """
        self._buf += data

        # If we did not get enough to read id and length, just return
        if len(self._buf) < 4:
            return b'', False

        if len(self._buf) < (self.length + 4):
            return b'', False

        data = self._buf[self.length + 4:]
        self._buf = self._buf[:self.length + 4]
        return data, True

    @property
    def id(self) -> int:
        """
        RTSP inline binary data all have a reference ID,
        negociated during SETUP.
        """
        assert len(self._buf) >= 1, 'buffer too short'
        return self._buf[1]

    @property
    def length(self) -> int:
        """Return frame length"""
        assert len(self._buf) >= 4, 'buffer too short'
        return (self._buf[2] << 8) + self._buf[3]

    @property
    def content(self) -> str:
        """Return string representation of content"""
        return hexlify(self.data).decode('utf-8')

    @property
    def data(self) -> bytes:
        """Extract data from buffer"""
        return self._buf[4:]

    def __repr__(self):
        return f'<Binary id={self.id} length={self.length}>'


class RTSPParser:
    """
    RTSP Stream parser.
    Keep track if incoming data and yields valid elements upon calls to parse().
    """

    def __init__(self):
        self.pending_msg = None
        self._prev_data = b''

    def parse(self, data: bytes) -> Iterator[RTSPMessage]:
        """
        Receiving data
        :param data:
        :return:
        """
        while data:
            if self.pending_msg is None:
                # Prepend potential leftover from previous data
                data, self._prev_data = self._prev_data + data, b''

                # We need to determine what is coming next
                if data.startswith(CRLF):
                    # Skip empty lines between items
                    data = data[2:]
                    continue

                if data.startswith(b'RTSP'):
                    # This is a reply
                    self.pending_msg = RTSPResponse()

                elif data.startswith(b'$'):
                    self.pending_msg = RTSPBinary()

                elif data.startswith(RTSPRequest.CLIENT_REQUESTS) or any(
                        req.startswith(data) for req in RTSPRequest.CLIENT_REQUESTS):
                    self.pending_msg = RTSPRequest()

                elif len(data) > 13:
                    # That's the longest client request we could expect...
                    raise ValueError

                else:
                    # Received only a chunk of message. Should be better next iteration. Store
                    self._prev_data = data
                    break

            data, done = self.pending_msg.feed(data)

            if done:
                yield self.pending_msg
                self.pending_msg = None
