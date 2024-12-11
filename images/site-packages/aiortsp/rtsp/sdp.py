"""
 Session Description - RFC 4566
 Very basic SDP parser
 ------------------------------------------------------------------------------------------------------
 type_    Dictionary key          Format of the value
 ======  ======================  ======================================================================
 v       "protocol_version"      version_number
 o       "origin"                ("user", session_id, session_version, "net_type", "addr_type", "addr")
 s       "sessionname"           "session name"
 t & r   "time"                  (starttime, stoptime, [repeat,repeat, ...])
                                    where repeat = (interval,duration,[offset,offset, ...])
 a       "attribute"             "value of attribute"
 b       "bandwidth"             (mode, bitspersecond)
 i       "information"           "value"
 e       "email"                 "email-address"
 u       "URI"                   "uri"
 p       "phone"                 "phone-number"
 c       "connection"            ("net_type", "addr_type", "addr", ttl, groupsize)
 z       "timezone adjustments"  [(adj-time,offset), (adj-time,offset), ...]
 k       "encryption"            ("method","value")
 m       "media"                 [media-description, media-description, ... ]
                                     see next table for media description structure
 ======  ======================  ======================================================================
"""
import re
from typing import Optional


class SDP(dict):
    """
    SDP Parser class.
    Takes an sdp content as an input and split it into various sections,
    including the different available medias.
    """

    def __init__(self, data: str):
        super().__init__()
        self.current_media = None

        self.parsers = {
            'v': self._parse_version,
            'o': self._parse_origin,
            's': self._parse_session_name,
            'i': self._parse_info,
            'u': self._parse_uri,
            'e': self._parse_email,
            'p': self._parse_phone,
            'c': self._parse_connection,
            'k': self._parse_encryption,
            'z': self._parse_timezone,
            'm': self._parse_media,
            'b': self._parse_bandwidth,
            't': self._parse_time,
            'r': self._parse_repeats,
            'a': self._parse_attributes,
        }

        for line in data.splitlines():
            self._parseline(line)

    def _parse_version(self, value):
        value = int(value)
        # Only version 0 allowed
        assert value == 0, 'only SDP version 0 supported'
        self['version'] = int(value)

    def _parse_origin(self, value):
        self['origin'] = value

    def _parse_session_name(self, value):
        self['sessionName'] = value

    def _parse_info(self, value):
        self['information'] = value

    def _parse_uri(self, value):
        self['URI'] = value

    def _parse_email(self, value):
        self['email'] = value

    def _parse_phone(self, value):
        self['phone'] = value

    def _parse_connection(self, value):
        self._element['connection'] = value

    def _parse_encryption(self, value):
        method, value = re.match(r"^(clear|base64|uri|prompt)(?:[:](.*))?$", value).groups()
        self._element["encryption"] = (method, value)

    def _parse_timezone(self, value):
        adjustments = []
        while value.strip() != "":
            adjtime, offset, offsetunit, value = re.match(r"^ *(\d+) +([+-]?\d+)([dhms])? *?(.*)$", value).groups()
            adjtime = int(adjtime)
            offset = int(offset) * {None: 1, "s": 1, "m": 60, "h": 3600, "d": 86400}[offsetunit]
            adjustments.append((adjtime, offset))

        self._element['timezoneAdjustments'] = adjustments

    def _parse_media(self, value):
        media, port, numports, protocol, fmt = re.match(
            r"^(audio|video|text|application|message) +(\d+)(?:[/](\d+))? +([^ ]+) +(.+)$", value).groups()

        port = int(port)

        if numports is None:
            numports = 1
        else:
            numports = int(numports)

        self.current_media = {
            'type': media,
            'port': port,
            'numPorts': numports,
            'protocol': protocol,
            'format': fmt
        }
        self.setdefault('medias', []).append(self.current_media)

    def _parse_bandwidth(self, value):
        mode, rate = \
            re.match(r"^ *((?:AS)|(?:CT)|(?:X-[^:]+)):(\d+) *$", value).groups()
        bitspersecond = int(rate) * 1000

        self._element['bandwidth'] = (mode, bitspersecond)

    def _parse_time(self, value):
        start, stop = [int(x) for x in re.match(r"^ *(\d+) +(\d+) *$", value).groups()]
        self._element['time'] = (start, stop)

    def _parse_repeats(self, value):
        terms = re.split(r"\s+", value)
        parsedterms = []
        for term in terms:
            value, unit = re.match(r"^\d+([dhms])?$", term).groups()
            value = int(value) * {None: 1, "s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
            parsedterms.append(value)

        interval, duration = parsedterms[0], parsedterms[1]
        offsets = parsedterms[2:]
        self._element['repeats'] = (interval, duration, offsets)

    def _parse_attributes(self, value):
        # Attributes are a=<attrname>:<specific content>
        attr, content = value.split(':', 1) if ':' in value else (value, None)
        attributes = self._element.setdefault('attributes', {})

        # # Special cases
        if attr == 'framerate':
            # Content is a framerate as float
            content = float(content)
        elif attr == 'framesize':
            pt, width, height = re.match(r"^ *(\d+) *(\d+)-(\d+) *$", content).groups()
            content = {
                'pt': int(pt),
                'width': int(width),
                'height': int(height)
            }
        elif attr == 'rtpmap':
            pt, enc, clock = re.match(r"^ *(\d+) *(\S+)/(\d+) *$", content).groups()
            content = {
                'pt': int(pt),
                'encoding': enc,
                'clockRate': int(clock)
            }
        elif attr == 'fmtp':
            pt, opts = content.split(None, 1)
            content = {
                'pt': int(pt)
            }
            for opt in opts.split(';'):
                if not opt.strip():
                    # Empty, probably a wrong semicolon at the end...
                    continue
                k, v = opt.split('=', 1)
                content[k.strip()] = v.strip()

        attributes[attr] = content

    def _parse_unknown(self, type_, value):
        self._element.setdefault('unknowns', []).append((type_, value))

    @property
    def _element(self):
        return self if self.current_media is None else self.current_media

    def _parseline(self, line):
        match = re.match("^(.)=(.*)", line)

        if match:
            type_, value = match.group(1), match.group(2)

            if type_ in self.parsers:
                try:
                    self.parsers[type_](value)
                except Exception:  # pylint: disable=broad-except
                    self._parse_unknown(type_, value)
            else:
                self._parse_unknown(type_, value)

    @staticmethod
    def mix_url_control(base: str, ctrl) -> str:
        """
        Given a base URL and a control attribute,
        build an URL to be used during SETUP.
        :param base: Base URL (either from user or returned in Content-Base)
        :param ctrl: Control attributes for given media (or global)
        :return: URL
        """
        if not ctrl or ctrl == '*':
            return base

        if ctrl.startswith('rtsp://') or ctrl.startswith('rtsps://'):
            return ctrl

        if not ctrl.startswith('/') and not base.endswith('/'):
            return base + '/' + ctrl

        return base + ctrl

    def get_media(self, media_type='video', media_idx=0):
        """
        Return the Nth media description matching requested type
        :param media_type:
        :param media_idx:
        :return:
        """
        current_idx = 0

        for media in self.get('medias', []):
            if media['type'] != media_type:
                continue

            if current_idx < media_idx:
                current_idx += 1
                continue

            # Found it!
            return media

        return None

    def setup_url(self, base_url: str, media_type='video', media_idx=0) -> str:
        """
        Return the URL to be used for setup.
        :param base_url: (url requested or returned base url)
        :param media_type: audio|video|text|application|message
        :param media_idx: index if multiple medias are available
        :return: corrected URL
        """
        # Check global control
        base_url = self.mix_url_control(base_url, self.get('attributes', {}).get('control'))

        # Look for media
        media = self.get_media(media_type, media_idx)
        if media:
            return self.mix_url_control(base_url, media.get('attributes', {}).get('control'))

        # Not found in medias
        return base_url

    def media_clock_rate(self, media_type='video', media_idx=0) -> Optional[int]:
        """
        Return clock rate of given media
        """
        media = self.get_media(media_type, media_idx)
        if media:
            return media.get('attributes', {}).get('rtpmap', {}).get('clockRate')
        return None

    def media_payload_type(self, media_type='video', media_idx=0) -> Optional[int]:
        """
        Return clock rate of given media
        """
        media = self.get_media(media_type, media_idx)
        if media:
            return media.get('attributes', {}).get('rtpmap', {}).get('pt')
        return None

    def guess_h264_props(self, media_idx=0):
        """
        Try to guess H264 `sprop-parameter-sets`
        :param media_idx:
        :return: props string
        """
        media = self.get_media(media_type='video', media_idx=media_idx)
        if media:
            return media.get('attributes', {}).get('fmtp', {}).get('sprop-parameter-sets')
        return None
