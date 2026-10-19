"""
Keeps LAN RTSP camera sessions (OrcaSlicer, Bambu Studio, mpv, ...) alive

The stock camera server (`ipcam`) tears an RTSP session down about ten seconds
after PLAY unless the client keeps chatting to it within that window.  Clients
that speak proper RTSP liveness (mpv, ffplay) survive; the `libBambuSource.so`
blob used by OrcaSlicer/Bambu Studio does not, so its live view picture freezes
ten seconds in and only a slicer restart recovers it.

This module is a transparent RTSP liveness relay: it terminates the LAN TLS
connection on port 322 itself, bridges it (over TLS, verification off) to the
real `ipcam` on loopback, and injects an OPTIONS keepalive into the upstream
session every few seconds (also while the client is chatting, which is
harmless).  Responses to our injected keepalives are swallowed, so clients
see byte-identical traffic apart from not freezing.  LAN client traffic is
redirected here with an
iptables rule in nat/PREROUTING (REDIRECT where the kernel supports it, DNAT
to the printer's own address otherwise, tagged with a comment where the
comment match exists); traffic that originates on the printer itself,
including camera_watchdog's port-322 probe, traverses OUTPUT and is not
touched.

The TLS identity served to clients is this relay's own persistent self-signed
certificate, with the Common Name carrying the printer's serial (from the
platform: OrcaSlicer's Open Bamboo Networking layer verifies
the leaf hostname against the printer serial and pins the leaf against a
cached camera certificate: `OBN_LAN_TLS_PEER_<ip>` points at a trust file
which, holding our relay certificate, makes both its chain check and its
hostname check pass).

Works in cloud, LAN, and Shield modes.  With RTSP off, ipcam is not listening
and client connects to the relay fail just like connections to a closed port.

Settings:
  camera.keepalive.interval - float, seconds between injected RTSP keepalives
    for each session (default: 4; ipcam kills a quiet session after ~10s)
  camera.keepalive.relay_port - int, TCP port the relay listens on
    (default: 1322; LAN TCP traffic to port 322 is redirected here)

[X1PLUS_MODULE_INFO]
module:
  name: camera_keepalive
  default_enabled: true
[END_X1PLUS_MODULE_INFO]
"""

import asyncio
import hashlib
import logging
import os
import random
import re
import socket
import ssl
import subprocess

try:
    from x1plus.utils import is_emulating, serial_number
except ImportError:
    # unit tests load the module by raw path, without the x1plus package
    def is_emulating():
        return False
    def serial_number():
        return None

logger = logging.getLogger(__name__)

UPSTREAM_HOST      = "127.0.0.1"
# mostly a constant on the printer; an env override exists as a testing /
# debugging hook (mock ipcam harnesses run the relay against other ports)
IPCAM_PORT         = int(os.environ.get("X1P_RELAY_UPSTREAM_PORT", "322"))

IPTABLES           = "/usr/sbin/iptables"
IPTABLES_COMMENT   = "x1plus-camera-keepalive"

CERT_DIR           = "/opt/x1plus/etc/camera-keepalive"

ACCESS_TOKEN_FILE  = "/config/device/access_token"

DEFAULT_RELAY_PORT = 1322
DEFAULT_INTERVAL   = 4.0
HANDSHAKE_TIMEOUT  = 10          # s, client TLS accept + upstream dial
INJECT_CSEQ_BASE   = 100000      # a real client only gets up to a few dozen
# keepalives whose responses went unanswered: upstream normally replies well
# under one interval; at the cap it has stopped answering, so stop buffering
INJECT_MAX_OUTSTANDING = 16
BACKLOG_SKIP       = 262144      # B; do not keepalive into a stalled sender

DEFAULT_RTSP_URL   = f"rtsp://{UPSTREAM_HOST}:{IPCAM_PORT}/streaming/live/1"


def _md5(s):
    return hashlib.md5(s.encode()).hexdigest()


def _hdr(msg, name):
    """Value of the first `name:` header in an RTSP message, or None."""
    m = re.search(rb"(?im)^" + re.escape(name.encode()) + rb":(.*?)\r\n", msg)
    return m.group(1).strip().decode(errors="replace") if m else None


class MessageFramer:
    """Reassembles an RTSP-over-TCP byte stream into framed messages.

    The stream carries either ASCII RTSP messages (CRLF CRLF terminated, plus
    a Content-Length body if present) or RTP frames interleaved into the RTSP
    connection ("$" + channel byte + 16-bit length + payload).  Bytes that do
    not look like either are passed through verbatim as "traffic" rather than
    being dropped, so a stream we cannot parse is relayed, not stranded.
    """

    MAX_LINE = 8192

    def __init__(self):
        self.buf = b""

    def pop(self):
        """Return (kind, message_bytes) for the next complete frame, or None.

        kind is "rtsp", "interleaved", or "traffic" (opaque bytes passed
        through verbatim).  Partial frames remain buffered until complete.
        """
        buf = self.buf
        if not buf:
            return None

        if buf[0:1] == b"$":
            if len(buf) < 4:
                return None
            n = 4 + int.from_bytes(buf[2:4], "big")
            if len(buf) < n:
                return None
            self.buf = buf[n:]
            return ("interleaved", buf[:n])

        if not (0x41 <= buf[0] <= 0x5A):    # neither "$" nor ASCII RTSP msg
            out, self.buf = buf, b""
            return ("traffic", out)

        eoh = buf.find(b"\r\n\r\n")
        if eoh == -1:
            if len(buf) <= self.MAX_LINE:
                return None
            out, self.buf = buf, b""
            return ("traffic", out)

        total = eoh + 4
        m = re.search(rb"(?i)\r\nContent-Length: ?(\d+)\r\n", buf[:total])
        if m:
            total += int(m.group(1))
        if len(buf) < total:
            if total > (1 << 20):           # absurd length; treat as garbage
                out, self.buf = buf, b""
                return ("traffic", out)
            return None

        self.buf = buf[total:]
        return ("rtsp", buf[:total])


class RelayConnection:
    """One proxied RTSPS session: client <-> relay <-> ipcam."""

    def __init__(self, upstream_ctx, interval, verbose=False):
        self.upstream_ctx = upstream_ctx
        self.interval = max(0.5, min(float(interval), 9.0))
        self.verbose = verbose

        self.framer_from_upstream = MessageFramer()   # ipcam -> client

        self.client   = None
        self.upstream = None
        self.peer     = "?"

        self.session_id  = None
        self.url         = None
        self.token       = None
        self.last_401    = None       # latest WWW-Authenticate we have seen

        self.inject       = set()     # outstanding injected CSeqs
        self.inject_n     = INJECT_CSEQ_BASE
        self.auth_nc      = 0
        self.digest_tried = False

        self.bytes_up     = 0         # read from client
        self.bytes_down   = 0         # read from ipcam
        self.keepalives   = 0
        self.swallowed    = 0
        self.saw_rtsp     = False
        self.t0           = None

        self._injector = None
        self._up_lock  = asyncio.Lock()
        self._closed   = False

    async def run(self, client_reader, client_writer):
        self.client = client_writer
        pn = client_writer.get_extra_info("peername")
        self.peer = pn[0] if pn else "?"
        self.t0 = asyncio.get_event_loop().time()
        if self.verbose:
            logger.info(f"keepalive relay: {self.peer}: session "
                        "accepted")
        try:
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(UPSTREAM_HOST, IPCAM_PORT,
                                        ssl=self.upstream_ctx),
                HANDSHAKE_TIMEOUT)
        except Exception as e:
            logger.info(f"keepalive relay: {self.peer}: ipcam dial failed: "
                        f"{e.__class__.__name__}: {e}")
            await self._close()
            return
        self.upstream = upstream_writer

        self._injector = asyncio.create_task(self._injector_loop())
        await asyncio.gather(
            self._pump_from_upstream(upstream_reader),
            self._pump_from_client(client_reader),
            return_exceptions=True)
        await self._close()

    # ---------- ipcam -> client ----------

    async def _pump_from_upstream(self, reader):
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                self.bytes_down += len(data)
                self.framer_from_upstream.buf += data
                while (msg := self.framer_from_upstream.pop()):
                    if msg[0] == "rtsp":
                        self.saw_rtsp = True
                        if self._handle_response(msg[1]):
                            continue          # our keepalive's response
                    self.client.write(msg[1])
                    await self.client.drain()
        except asyncio.CancelledError:
            raise
        except (ConnectionError, ssl.SSLError, OSError, TimeoutError) as e:
            if self.verbose:
                logger.debug(f"keepalive relay: {self.peer}: upstream pump: "
                             f"{e!r}")

    def _handle_response(self, msg):
        """Return True (drop message) if it answers one of our keepalives."""
        auth = _hdr(msg, "WWW-Authenticate")
        if auth:
            self.last_401 = auth

        sess = _hdr(msg, "Session")
        if sess:
            self.session_id = sess.split(";")[0].strip()

        cseq = _hdr(msg, "CSeq")
        if not cseq:
            return False
        try:
            cseq = int(cseq)
        except ValueError:
            return False
        if cseq not in self.inject:
            return False

        self.inject.discard(cseq)
        self.swallowed += 1

        if (auth and not self.digest_tried):
            # The server wants authentication even on liveness chatter; use
            # the same digest credentials real clients use.
            self.digest_tried = True
            asyncio.create_task(self._inject_once(auth=True))
        return True

    # ---------- client -> ipcam ----------

    async def _pump_from_client(self, reader):
        framer = MessageFramer()
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                self.bytes_up += len(data)
                framer.buf += data
                while (msg := framer.pop()):
                    kind, m = msg
                    if kind == "rtsp":
                        self.saw_rtsp = True
                        line = m.split(b"\r\n", 1)[0]
                        first = line.split(None, 2)
                        if (self.url is None and len(first) == 3
                                and not first[0].startswith(b"RTSP/")):
                            self.url = first[1].decode(errors="replace")
                    await self._upstream_send(m)
        except asyncio.CancelledError:
            raise
        except (ConnectionError, ssl.SSLError, OSError, TimeoutError) as e:
            if self.verbose:
                logger.debug(f"keepalive relay: {self.peer}: client pump: "
                             f"{e!r}")

    async def _upstream_send(self, data):
        """Single writer funnel to ipcam, so an injected keepalive can never
        land in the middle of a half-sent client message."""
        async with self._up_lock:
            self.upstream.write(data)
            await self.upstream.drain()

    # ---------- liveness injection ----------

    async def _injector_loop(self):
        while not self._closed:
            await asyncio.sleep(self.interval)
            if self._closed:
                return
            try:
                await self._inject_once()
            except Exception as e:
                if self.verbose:
                    logger.debug(f"keepalive relay: {self.peer}: inject: "
                                 f"{e!r}")

    async def _inject_once(self, auth=False):
        if (self._closed or self.upstream is None or not self.saw_rtsp):
            return
        # A stalled client must not accrete keepalive buffers upstream.
        if self.upstream.transport.get_write_buffer_size() > BACKLOG_SKIP:
            return
        if len(self.inject) >= INJECT_MAX_OUTSTANDING:
            return

        cseq = self.inject_n
        self.inject_n += 1
        self.inject.add(cseq)

        lines = [f"OPTIONS {self.url or DEFAULT_RTSP_URL} RTSP/1.0",
                 f"CSeq: {cseq}"]
        if self.session_id:
            lines.append(f"Session: {self.session_id}")
        if auth:
            hdr = self._digest_header()
            if hdr:
                lines.append(f"Authorization: {hdr}")
        self.keepalives += 1

        await self._upstream_send(("\r\n".join(lines) + "\r\n\r\n").encode())

    def _digest_header(self):
        """An Authorization: Digest header computed from the access code."""
        if self.token is None:
            try:
                with open(ACCESS_TOKEN_FILE) as f:
                    self.token = f.read().strip()
            except OSError:
                self.token = ""
        if not (self.token and self.last_401):
            return None

        chal = self.last_401
        m = re.search(r'realm="([^"]*)"', chal)
        realm = m.group(1) if m else "LIVE555 Streaming Media"
        m = re.search(r'nonce="([^"]*)"', chal)
        nonce = m.group(1) if m else None
        if not nonce:
            return None

        user, pw = "bblp", self.token
        uri = self.url or DEFAULT_RTSP_URL
        ha1 = _md5(f"{user}:{realm}:{pw}")

        # qop negotiation: only claim a qop we can actually compute.  An OPTIONS
        # keepalive has no body, so the auth-int variant just hashes the empty
        # body; anything else offered falls back to the RFC 2069 plain response.
        m = re.search(r'qop="?([^",]+(?: *, *[^",]+)*)"?', chal)
        qops = [q.strip() for q in m.group(1).split(",")] if m else []
        if "auth" in qops:
            qop, ha2 = "auth", _md5(f"OPTIONS:{uri}")
        elif "auth-int" in qops:
            qop, ha2 = "auth-int", _md5(f"OPTIONS:{uri}:{_md5('')}")
        else:
            qop, ha2 = None, _md5(f"OPTIONS:{uri}")

        if qop is None:
            rsp = _md5(f"{ha1}:{nonce}:{ha2}")
            return (f'Digest username="{user}", realm="{realm}", '
                    f'nonce="{nonce}", uri="{uri}", response="{rsp}"')
        self.auth_nc += 1
        nc = f"{self.auth_nc:08X}"
        cnonce = f"{random.getrandbits(64):016x}"
        rsp = _md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}")
        return (f'Digest username="{user}", realm="{realm}", '
                f'nonce="{nonce}", uri="{uri}", response="{rsp}", '
                f'qop={qop}, nc={nc}, cnonce="{cnonce}"')

    # ---------- teardown ----------

    async def _close(self):
        if self._closed:
            return
        self._closed = True

        if self._injector:
            self._injector.cancel()
            await asyncio.gather(self._injector, return_exceptions=True)
        for w in [self.client, self.upstream]:
            if w:
                try:
                    w.close()
                    await w.wait_closed()
                except Exception:
                    pass

        dur = ((asyncio.get_event_loop().time() - self.t0)
               if self.t0 else 0.0)
        if self.verbose:
            logger.info(
                f"keepalive relay: {self.peer}: closed after {dur:.1f}s, "
                f"up {self.bytes_up}B down {self.bytes_down}B, "
                f"keepalives {self.keepalives} swallowed {self.swallowed}")


def _lan_ip():
    """Address of the primary LAN interface, for DNAT back to ourselves.
    The catch-all probe rides the default route; the private guesses cover
    routers with no default route configured."""
    probes = ["1.1.1.1", "192.168.1.1", "192.168.50.1", "10.0.0.1",
              "172.16.0.1"]
    for t in probes:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((t, 9))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127."):
                return ip
        except OSError:
            continue
    return None


class CameraKeepaliveRelay:

    def __init__(self, daemon=None):
        self.daemon      = daemon
        self._use_tables = not is_emulating()
        self._rule_style = None      # redir_tagged|redir_bare|dnat once picked
        self._rule_ip    = None      # for the dnat style
        self.server      = None
        self._up_ctx     = None

    @property
    def port(self):
        return self.daemon.settings.get("camera.keepalive.relay_port",
                                        DEFAULT_RELAY_PORT)

    @property
    def interval(self):
        return self.daemon.settings.get("camera.keepalive.interval",
                                        DEFAULT_INTERVAL)

    @property
    def bind(self):
        return "127.0.0.1" if is_emulating() else "0.0.0.0"

    # ---------- TLS identity ----------

    def _ensure_identity(self):
        """Return (certfile, keyfile) loadable by load_cert_chain(); creates
        the generated identity once."""
        certfile = os.path.join(CERT_DIR, "cert.pem")
        keyfile = os.path.join(CERT_DIR, "key.pem")
        # the serial is fused to the board; a surviving cert implies it
        if (os.path.exists(certfile) and os.path.exists(keyfile)):
            return certfile, keyfile

        # serial unavailable (PC standalone or broken bbl_3dpsn) -> placeholder CN
        try:
            serial = serial_number()
        except Exception:
            serial = None

        os.makedirs(CERT_DIR, exist_ok=True)
        subj = f"/CN={serial or 'Bambu Lab Camera Relay'}/O=Bambu Lab/C=CN"
        logger.info(f"keepalive relay: generating TLS identity ({subj})")
        subprocess.run(
            ["openssl", "req", "-x509",
             "-newkey", "rsa:2048", "-sha256", "-days", "3650", "-nodes",
             "-keyout", keyfile, "-out", certfile, "-subj", subj],
            check=True, capture_output=True)
        os.chmod(keyfile, 0o600)
        return certfile, keyfile

    def _client_connected(self, reader, writer):
        verbose = self.daemon.settings.get("camera.keepalive.verbose",
                                           False) is True
        conn = RelayConnection(upstream_ctx=self._up_ctx,
                               interval=self.interval,
                               verbose=verbose)
        return conn.run(reader, writer)

    # ---------- iptables ----------

    def _rule_spec(self, style=None):
        style = style or self._rule_style or "redir_tagged"
        common = ["PREROUTING", "-p", "tcp", "-m", "tcp",
                  "--dport", str(IPCAM_PORT)]
        if style == "redir_tagged":
            return common + ["-m", "comment", "--comment", IPTABLES_COMMENT,
                             "-j", "REDIRECT", "--to-ports", str(self.port)]
        if style == "redir_bare":
            return common + ["-j", "REDIRECT", "--to-ports", str(self.port)]
        # dnat: back to ourselves on the LAN address (REDIRECT and comment
        # matches are missing on the kernels out in the field)
        return common + ["-j", "DNAT", "--to-destination",
                         f"{self._rule_ip or _lan_ip()}:{self.port}"]

    def _iptable(self, verb, spec):
        return subprocess.run([IPTABLES, "-t", "nat", verb] + spec,
                              capture_output=True)

    def _rules_list(self):
        r = subprocess.run([IPTABLES, "-t", "nat", "-S", "PREROUTING"],
                           capture_output=True)
        return r.stdout.decode(errors="replace").splitlines()

    def _rule_add(self):
        """Install the redirect; picks a working style and reports errors.
        Retries the known-working style first, then the rest of the ladder."""
        if not self._use_tables:
            return True
        ladder = ["redir_tagged", "redir_bare", "dnat"]
        if self._rule_style in ladder:
            ladder = [self._rule_style] + \
                [s for s in ladder if s != self._rule_style]
        for style in ladder:
            if style == "dnat":
                ip = _lan_ip()
                if not ip:
                    logger.error("keepalive relay: no LAN address found for "
                                 "the dnat rule; clients keep speaking to "
                                 "ipcam directly")
                    return False
                self._rule_ip = ip
            r = self._iptable("-I", self._rule_spec(style))
            if r.returncode == 0:
                self._rule_style = style
                how = {"redir_tagged": "redirected (tagged rule)",
                       "redir_bare": "redirected (untagged rule)",
                       "dnat": f"dnatted via {self._rule_ip}"}[style]
                logger.info(f"keepalive relay: LAN tcp/{IPCAM_PORT} is now "
                            f"{how} to this relay on tcp/{self.port}")
                return True
            if style != "dnat":
                logger.info("keepalive relay: rule variant "
                            f"{style} rejected "
                            f"({r.stderr.decode(errors='replace').strip()})")
        self._rule_style = None
        self._rule_ip = None
        logger.error("keepalive relay: could not install any redirect rule; "
                     "clients keep speaking to ipcam directly")
        return False

    def _rule_present(self):
        """True iff THE rule we would install is in effect.  When it is not
        (flushed nat table, or a dnat rule left pointing at a stale DHCP
        address), our rules are removed and a fresh one installed.  The
        caller keeps a watchful 30s cadence for either outcome."""
        if not self._use_tables:
            return True
        if self._rule_style is None:
            return False
        if self._iptable("-C", self._rule_spec()).returncode == 0:
            return True
        self._rule_del()
        self._rule_add()
        return self._iptable("-C", self._rule_spec()).returncode == 0

    def _rule_del(self):
        """Best-effort removal of anything of ours left on dport 322; a stray
        rule after a restart would strand clients on a dead listener."""
        if not self._use_tables:
            return
        dport, rport = str(IPCAM_PORT), str(self.port)
        for line in self._rules_list():
            m = re.match(r"^-A (\S+) (.+)$", line.strip())
            if not m or m.group(1) != "PREROUTING":
                continue
            rest = m.group(2)
            if dport not in re.findall(r"--dport (\d+)", rest):
                continue
            if (re.search(rf"\bREDIRECT\b.*--to-ports {rport}\b", rest)
                    or re.search(rf"\bDNAT\b.*--to-destination"
                                 rf" \S+:{rport}(?:\s|$)", rest)):
                self._iptable("-D", ["PREROUTING", *rest.split()])

    # ---------- main task ----------

    async def task(self):
        accept_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        upstream_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        upstream_ctx.check_hostname = False
        upstream_ctx.verify_mode = ssl.CERT_NONE
        self._up_ctx = upstream_ctx

        try:
            certfile, keyfile = await asyncio.to_thread(self._ensure_identity)
            accept_ctx.load_cert_chain(certfile, keyfile)
        except Exception as e:
            logger.error(f"keepalive relay: no usable TLS identity, staying "
                         f"down ({e.__class__.__name__}: {e})")
            return

        try:
            self.server = await asyncio.start_server(
                self._client_connected, self.bind, self.port,
                ssl=accept_ctx, ssl_handshake_timeout=HANDSHAKE_TIMEOUT)
        except Exception as e:
            logger.error(f"keepalive relay: cannot listen on "
                         f"{self.bind}:{self.port} ({e.__class__.__name__}: "
                         f"{e})")
            return

        try:
            # a killed daemon leaves its rule behind; clear ours before adding
            await asyncio.to_thread(self._rule_del)
            await asyncio.to_thread(self._rule_add)
        except Exception as e:
            logger.error(f"keepalive relay: iptables setup failed "
                         f"({e.__class__.__name__}: {e})")

        logger.info(f"keepalive relay listening on {self.bind}:{self.port} "
                    f"-> rtsps ipcam tcp/{IPCAM_PORT} "
                    f"(keepalive interval {self.interval}s)")

        try:
            while True:
                await asyncio.sleep(30)
                # If the rule evaporated (something flushed nat), put it back
                # for as long as we are the ones serving; _rule_present
                # reinstalls it and reports whether it stuck.
                if (self.server is not None and self.server.is_serving()
                        and not await asyncio.to_thread(self._rule_present)):
                    logger.error("keepalive relay: redirect rule is missing; "
                                 "clients keep speaking to ipcam directly")
        except asyncio.CancelledError:
            pass
        finally:
            await self._shutdown()
            await asyncio.to_thread(self._rule_del)

    async def _shutdown(self):
        if self.server:
            self.server.close()
            try:
                await self.server.wait_closed()
            except Exception:
                pass
            self.server = None
            logger.info("keepalive relay: stopped")


# x1plusd wiring ---------------------------------------------------------------

_service = None


def load(daemon):
    global _service
    _service = CameraKeepaliveRelay(daemon=daemon)
    daemon.camera_keepalive = _service


def start():
    asyncio.create_task(_service.task())
