"""Unit tests for camera_keepalive's pure logic; no printer or daemon needed.

Run:  python3 _test_camera_keepalive.py

Run from a PC or on the printer; on the printer, prepend
/opt/x1plus/lib/python to PYTHONPATH so x1plus.utils resolves.  Loaded
straight from the file path (like x1plusd's own loader does) so the
package __init__ chain and its dependencies stay out of the way.  The
leading underscore keeps x1plusd's module loader from treating this as
a module.
"""

import importlib.util
import re
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "_camera_keepalive_under_test",
    Path(__file__).resolve().with_name("camera_keepalive.py"))
_cam = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cam)

MessageFramer = _cam.MessageFramer
RelayConnection = _cam.RelayConnection
_md5 = _cam._md5
INJ = _cam.INJECT_CSEQ_BASE


def _feed(framer, chunks):
    """Push chunks like the relay pumps do, collecting everything that pops."""
    got = []
    for c in chunks:
        framer.buf += c
        while (m := framer.pop()):
            got.append(m)
    return got


class FramerTests(unittest.TestCase):
    RTSP = b"OPTIONS rtsp://x RTSP/1.0\r\nCSeq: 1\r\n\r\n"

    def test_rtsp_message(self):
        self.assertEqual(_feed(MessageFramer(), [self.RTSP]),
                         [("rtsp", self.RTSP)])

    def test_rtsp_with_body_split_across_reads(self):
        head = b"SETUP rtsp://x RTSP/1.0\r\nCSeq: 2\r\nContent-Length: 5\r\n\r\n"
        got = _feed(MessageFramer(), [head + b"hel", b"lo"])
        self.assertEqual(got, [("rtsp", head + b"hello")])

    def test_partial_rtsp_waits(self):
        f = MessageFramer()
        f.buf = self.RTSP[:10]
        self.assertIsNone(f.pop())
        f.buf += self.RTSP[10:]
        self.assertEqual(f.pop(), ("rtsp", self.RTSP))

    def test_interleaved_frame(self):
        frame = b"$\x00\x00\x03abc"
        f = MessageFramer()
        f.buf = frame[:3]
        self.assertIsNone(f.pop())
        f.buf += frame[3:] + self.RTSP
        self.assertEqual([f.pop(), f.pop()],
                         [("interleaved", frame), ("rtsp", self.RTSP)])

    def test_binary_garbage_passes_through(self):
        got = _feed(MessageFramer(), [b"\x00\x01junk"])
        self.assertEqual(got, [("traffic", b"\x00\x01junk")])

    def test_long_letter_stream_without_headers_flushed(self):
        # no CRLFCRLF within MAX_LINE: bounded flush, not a stalled buffer
        got = _feed(MessageFramer(), [b"R" * 9000])
        self.assertEqual(got, [("traffic", b"R" * 9000)])

    def test_interleaved_claimed_length_self_limits(self):
        # the 16-bit length field caps any one interleave frame at 65539,
        # so a bogus claim cannot grow the buffer without bound
        junk = b"$\x00\xff\xff" + b"x" * 70000
        got = _feed(MessageFramer(), [junk])
        self.assertEqual(got[0][0], "interleaved")
        self.assertEqual(len(got[0][1]), 65539)
        self.assertTrue(all(kind == "traffic" for kind, _ in got[1:]))


def _conn():
    c = RelayConnection(upstream_ctx=None, interval=4)
    c.verbose = False
    return c


class SwallowTests(unittest.TestCase):
    def test_injected_cseq_is_swallowed(self):
        c = _conn()
        c.inject.add(INJ)
        self.assertTrue(c._handle_response(
            b"RTSP/1.0 200 OK\r\nCSeq: %d\r\n\r\n" % INJ))
        self.assertEqual((c.swallowed, c.inject), (1, set()))

    def test_client_cseq_is_relayed(self):
        c = _conn()
        self.assertFalse(c._handle_response(
            b"RTSP/1.0 200 OK\r\nCSeq: 3\r\n\r\n"))

    def test_missing_cseq_is_relayed(self):
        c = _conn()
        self.assertFalse(c._handle_response(b"HTTP/1.0 200 OK\r\n\r\n"))

    def test_session_header_captured_even_from_relayed_response(self):
        c = _conn()
        self.assertFalse(c._handle_response(
            b"RTSP/1.0 200 OK\r\nCSeq: 5\r\nSession: deadbee;timeout=30\r\n\r\n"))
        self.assertEqual(c.session_id, "deadbee")

    def test_401_challenge_captured_from_swallowed_response(self):
        c = _conn()
        c.digest_tried = True          # keeps _handle_response from spawning
        c.inject.add(INJ)
        chal = b'Digest realm="LIVE555 Streaming Media", nonce="abc"'
        self.assertTrue(c._handle_response(
            (b"RTSP/1.0 401 Unauthorized\r\nCSeq: %d\r\n"
             b"WWW-Authenticate: " % INJ) + chal + b"\r\n\r\n"))
        self.assertIn("nonce=", c.last_401)


URI = "rtsp://192.168.50.125:322/streaming/live/1"
EMPTY_MD5 = _cam._md5("")


class DigestTests(unittest.TestCase):
    def _conn(self, qop=None):
        c = _conn()
        c.token = "tok"
        c.url = URI
        c.last_401 = ('Digest realm="LIVE555 Streaming Media", nonce="non"'
                      + (f', qop="{qop}"' if qop else ""))
        return c

    def test_no_qop_response_is_rfc2069_plain(self):
        h = self._conn()._digest_header()
        ha1 = _md5("bblp:LIVE555 Streaming Media:tok")
        ha2 = _md5(f"OPTIONS:{URI}")
        exp = _md5(ha1 + ":non:" + ha2)
        self.assertEqual(
            h, 'Digest username="bblp", realm="LIVE555 Streaming Media", '
               'nonce="non", uri="' + URI + '", response="' + exp + '"')

    def test_qop_auth_response_verifies(self):
        h = self._conn(qop="auth")._digest_header()
        cn = re.search(r'cnonce="([0-9a-f]+)"', h).group(1)
        ha1 = _md5("bblp:LIVE555 Streaming Media:tok")
        ha2 = _md5(f"OPTIONS:{URI}")
        exp = _md5(ha1 + ":non:00000001:" + cn + ":auth:" + ha2)
        self.assertIn(f'response="{exp}"', h)
        self.assertIn("qop=auth, nc=00000001", h)

    def test_qop_auth_only_choice_from_combined_offer(self):
        # server offered "auth, auth-int": must answer auth, not auth-int
        h = self._conn(qop="auth, auth-int")._digest_header()
        self.assertIn("qop=auth,", h)
        self.assertNotIn("auth-int", h.rsplit("qop=", 1))

    def test_qop_auth_int_response_verifies(self):
        h = self._conn(qop="auth-int")._digest_header()
        cn = re.search(r'cnonce="([0-9a-f]+)"', h).group(1)
        ha1 = _md5("bblp:LIVE555 Streaming Media:tok")
        # an OPTIONS keepalive carries no body, so auth-int burns the empty
        # body hash into ha2
        ha2 = _md5(f"OPTIONS:{URI}:{EMPTY_MD5}")
        exp = _md5(ha1 + ":non:00000001:" + cn + ":auth-int:" + ha2)
        self.assertIn(f'response="{exp}"', h)
        self.assertIn("qop=auth-int, nc=00000001", h)

    def test_unknown_qop_falls_back_to_plain_response(self):
        h = self._conn(qop="sasnobody")._digest_header()
        self.assertNotIn("qop=", h)
        ha1 = _md5("bblp:LIVE555 Streaming Media:tok")
        ha2 = _md5(f"OPTIONS:{URI}")
        self.assertIn(_md5(ha1 + ":non:" + ha2), h)

    def test_no_token_no_header(self):
        c = self._conn(qop="auth")
        c.token = ""
        self.assertIsNone(c._digest_header())


class _StubUpstream:
    def __init__(self):
        self.sent = []
        self.transport = type("T", (), {
            "get_write_buffer_size": staticmethod(lambda: 0)})()

    def write(self, data):
        self.sent.append(data)

    async def drain(self):
        pass


class InjectionCapTests(unittest.IsolatedAsyncioTestCase):
    async def test_unanswered_keepalives_stop_after_cap(self):
        c = _conn()
        c.upstream = _StubUpstream()
        c.saw_rtsp = True
        c.session_id = "sess"
        for _ in range(2 * _cam.INJECT_MAX_OUTSTANDING):
            await c._inject_once()     # ipcam never answers any of them
        self.assertEqual(len(c.inject), _cam.INJECT_MAX_OUTSTANDING)
        self.assertEqual(len(c.upstream.sent), _cam.INJECT_MAX_OUTSTANDING)

    async def test_cap_frees_as_soon_as_upstream_answers(self):
        c = _conn()
        c.upstream = _StubUpstream()
        c.saw_rtsp = True
        for _ in range(_cam.INJECT_MAX_OUTSTANDING + 3):
            await c._inject_once()
            c._handle_response(        # ipcam answers each one
                b"RTSP/1.0 200 OK\r\nCSeq: %d\r\n\r\n"
                % max(c.inject))
            await c._inject_once()
        self.assertGreater(len(c.upstream.sent), _cam.INJECT_MAX_OUTSTANDING)


class RuleTests(unittest.TestCase):
    """_rule_add/_rule_del against a stubbed iptables, no kernel needed."""

    def _svc(self, port=1400):
        # daemon only needs settings.get(key, default); a bare dict does that
        d = type("D", (), {"settings": {
            "camera.keepalive.relay_port": port}})()
        svc = _cam.CameraKeepaliveRelay(d)
        svc._use_tables = True
        svc._rule_style = None
        return svc

    def test_del_removes_only_our_rules(self):
        svc = self._svc()
        tagged = ("-A PREROUTING -p tcp -m tcp --dport 322 -m comment "
                  f"--comment {_cam.IPTABLES_COMMENT} "
                  "-j REDIRECT --to-ports 1400")
        stale_dnat = ("-A PREROUTING -p tcp -m tcp --dport 322 -j DNAT "
                      "--to-destination 192.168.50.9:1400")
        svc._rules_list = lambda: [
            tagged, stale_dnat,
            # somebody else's dport: not ours to touch
            "-A PREROUTING -p tcp -m tcp --dport 554 "
            "-j REDIRECT --to-ports 1400",
            # our dport, but not our relay port
            "-A PREROUTING -p tcp -m tcp --dport 322 "
            "-j REDIRECT --to-ports 9999",
        ]
        calls = []
        def ipt(verb, spec):
            calls.append((verb, list(spec)))
            return type("R", (), {"returncode": 0})()
        svc._iptable = ipt
        svc._rule_del()
        self.assertEqual(calls, [
            ("-D", ["PREROUTING", *tagged.split(None, 2)[2].split()]),
            ("-D", ["PREROUTING", *stale_dnat.split(None, 2)[2].split()]),
        ])

    def test_add_inserts_the_tagged_redirect(self):
        svc = self._svc()
        calls = []
        def ipt(verb, spec):
            calls.append((verb, list(spec)))
            return type("R", (), {"returncode": 0})()
        svc._iptable = ipt
        self.assertTrue(svc._rule_add())
        self.assertEqual(svc._rule_style, "redir_tagged")
        self.assertEqual(calls, [("-I", svc._rule_spec())])

    def test_add_falls_through_the_ladder_to_dnat(self):
        svc = self._svc()
        ok = []
        def ipt(verb, spec):
            # kernels in the field reject REDIRECT: only the dnat spec lands
            if "DNAT" not in " ".join(spec):
                return type("R", (), {"returncode": 1,
                                      "stderr": b"no match"})()
            ok.append((verb, list(spec)))
            return type("R", (), {"returncode": 0})()
        svc._iptable = ipt
        orig = _cam._lan_ip
        _cam._lan_ip = lambda: "192.168.50.9"
        self.addCleanup(setattr, _cam, "_lan_ip", orig)
        self.assertTrue(svc._rule_add())
        self.assertEqual((svc._rule_style, svc._rule_ip),
                         ("dnat", "192.168.50.9"))
        self.assertEqual(ok, [("-I", svc._rule_spec())])


if __name__ == "__main__":
    unittest.main()
