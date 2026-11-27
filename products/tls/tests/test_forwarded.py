"""Forwarded headers: a web app behind the edge learns the visitor's address, that the visit was HTTPS and the host asked for,
and a client can never supply those headers itself or smuggle a request past the edge."""
import socket
import tempfile
import threading
import unittest
from pathlib import Path

from acxelin_core import tls
from acxelin_core.pki import CA
from acxelin_tls import policies
from acxelin_tls.edge import Edge, Route
from acxelin_tls.forwarded import Forwarder, Refused
from support_tls import REASON, wait


def feed(f, data, step=None):
    """Everything the edge would pass upstream, giving the parser `step` bytes at a time."""
    step = step or len(data) or 1
    return b"".join(f.from_client(data[i:i + step]) for i in range(0, len(data), step))


def heads(upstream):
    """The request heads in what reached the app, as (request line, {lower-case name: [values]})."""
    out = []
    for block in upstream.split(b"\r\n\r\n")[:-1]:
        lines = block.split(b"\r\n")
        fields = {}
        for line in lines[1:]:
            if b":" in line:
                k, v = line.split(b":", 1)
                fields.setdefault(k.strip().lower(), []).append(v.strip())
        out.append((lines[-len(lines)], fields))
    return out


GET = b"GET /landing?x=1 HTTP/1.1\r\nHost: shop.example\r\nAccept: */*\r\n\r\n"


class ParserTest(unittest.TestCase):
    def test_the_app_learns_the_visitor_address_https_and_the_host(self):
        up = feed(Forwarder("203.0.113.7"), GET)
        line, h = heads(up)[0]
        self.assertEqual(line, b"GET /landing?x=1 HTTP/1.1")
        self.assertEqual(h[b"x-forwarded-for"], [b"203.0.113.7"])
        self.assertEqual(h[b"x-forwarded-proto"], [b"https"])
        self.assertEqual(h[b"x-forwarded-host"], [b"shop.example"])
        self.assertEqual(h[b"accept"], [b"*/*"])

    def test_headers_a_client_sends_to_pose_as_someone_else_are_removed(self):
        spoof = (b"GET / HTTP/1.1\r\nHost: shop.example\r\nX-Forwarded-For: 10.0.0.1\r\nx-forwarded-proto: http\r\n"
                 b"X-FORWARDED-HOST: admin.internal\r\nForwarded: for=10.0.0.1;proto=http\r\nX-Real-IP: 10.0.0.1\r\n\r\n")
        _, h = heads(feed(Forwarder("198.51.100.9"), spoof))[0]
        self.assertEqual(h[b"x-forwarded-for"], [b"198.51.100.9"])
        self.assertEqual(h[b"x-forwarded-proto"], [b"https"])
        self.assertEqual(h[b"x-forwarded-host"], [b"shop.example"])
        self.assertNotIn(b"forwarded", h)
        self.assertNotIn(b"x-real-ip", h)

    def test_every_request_on_a_kept_alive_connection_is_rewritten_however_the_bytes_arrive(self):
        two = GET + b"POST /form HTTP/1.1\r\nHost: shop.example\r\nX-Forwarded-For: 10.6.6.6\r\nContent-Length: 3\r\n\r\nabc" + GET
        for step in (1, 7, 64, None):
            up = feed(Forwarder("192.0.2.4"), two, step)
            got = heads(up.replace(b"abc", b"", 1))
            self.assertEqual(len(got), 3, step)
            self.assertTrue(all(h[b"x-forwarded-for"] == [b"192.0.2.4"] for _, h in got), step)
            self.assertIn(b"\r\n\r\nabc", up)

    def test_a_body_that_looks_like_headers_reaches_the_app_unchanged(self):
        body = b"x\r\n\r\nGET /admin HTTP/1.1\r\nX-Forwarded-For: 127.0.0.1\r\n\r\n"
        req = b"POST /upload HTTP/1.1\r\nHost: a\r\nContent-Length: %d\r\n\r\n" % len(body) + body
        up = feed(Forwarder("192.0.2.4"), req, 5)
        self.assertTrue(up.endswith(body))
        self.assertEqual(up.count(b"X-Forwarded-For: 192.0.2.4"), 1)

    def test_a_chunked_body_with_extensions_and_trailers_passes_and_the_next_request_is_rewritten(self):
        chunked = (b"POST /api HTTP/1.1\r\nHost: a\r\nTransfer-Encoding: chunked\r\n\r\n"
                   b"5;note=x\r\nhello\r\n0\r\nChecksum: 1\r\n\r\n")
        up = feed(Forwarder("192.0.2.4"), chunked + GET, 3)
        self.assertIn(b"5;note=x\r\nhello\r\n0\r\nChecksum: 1\r\n\r\n", up)
        self.assertEqual(up.count(b"X-Forwarded-For: 192.0.2.4"), 2)

    def test_http_1_0_without_a_host_still_gets_the_address_and_scheme(self):
        _, h = heads(feed(Forwarder("192.0.2.4"), b"GET / HTTP/1.0\r\n\r\n"))[0]
        self.assertEqual(h[b"x-forwarded-for"], [b"192.0.2.4"])
        self.assertEqual(h[b"x-forwarded-proto"], [b"https"])
        self.assertNotIn(b"x-forwarded-host", h)

    def test_request_smuggling_shapes_are_refused_not_guessed_at(self):
        bad = {
            "length and chunked": b"POST / HTTP/1.1\r\nHost: a\r\nContent-Length: 4\r\nTransfer-Encoding: chunked\r\n\r\n",
            "two different lengths": b"POST / HTTP/1.1\r\nHost: a\r\nContent-Length: 4\r\nContent-Length: 5\r\n\r\n",
            "a length that is not a number": b"POST / HTTP/1.1\r\nHost: a\r\nContent-Length: +4\r\n\r\n",
            "an encoding other than chunked": b"POST / HTTP/1.1\r\nHost: a\r\nTransfer-Encoding: gzip, chunked\r\n\r\n",
            "chunked twice": b"POST / HTTP/1.1\r\nHost: a\r\nTransfer-Encoding: chunked, chunked\r\n\r\n",
            "a folded header": b"GET / HTTP/1.1\r\nHost: a\r\nX-Note: one\r\n two\r\n\r\n",
            "space before the colon": b"GET / HTTP/1.1\r\nHost: a\r\nX-Forwarded-For : 10.0.0.1\r\n\r\n",
            "a bare line feed": b"GET / HTTP/1.1\nHost: a\n\n",
            "not HTTP/1.x": b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n",
            "a tunnel": b"CONNECT db.internal:5432 HTTP/1.1\r\nHost: db.internal:5432\r\n\r\n",
            "a bad chunk size": b"POST / HTTP/1.1\r\nHost: a\r\nTransfer-Encoding: chunked\r\n\r\nzz\r\n",
            "two hosts": b"GET / HTTP/1.1\r\nHost: a\r\nHost: b\r\n\r\n",
        }
        for why, data in bad.items():
            with self.subTest(why), self.assertRaises(Refused) as e:
                feed(Forwarder("192.0.2.4"), data)
            self.assertTrue(e.exception.response.startswith(b"HTTP/1.1 400 "), why)
            self.assertIn(b"Connection: close", e.exception.response)

    def test_a_request_head_too_large_is_refused(self):
        with self.assertRaises(Refused) as e:
            feed(Forwarder("192.0.2.4"), b"GET / HTTP/1.1\r\nHost: a\r\nX-Big: " + b"a" * 70000, 4096)
        self.assertTrue(e.exception.response.startswith(b"HTTP/1.1 431 "))

    def test_a_websocket_is_relayed_raw_only_after_the_app_switches_protocols(self):
        f = Forwarder("192.0.2.4")
        up = feed(f, b"GET /ws HTTP/1.1\r\nHost: a\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n")
        self.assertIn(b"X-Forwarded-For: 192.0.2.4", up)
        frame = b"\x81\x85\x00\x00\x00\x00X-Forwarded-For: spoof\r\n\r\n"
        self.assertEqual(f.from_client(frame), b"")  # held until the app answers
        self.assertEqual(f.from_server(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n\r\n"), frame)
        self.assertEqual(f.from_client(b"raw bytes"), b"raw bytes")

    def test_when_the_app_refuses_an_upgrade_nothing_more_from_the_client_reaches_it_unparsed(self):
        f = Forwarder("192.0.2.4")
        feed(f, b"GET /ws HTTP/1.1\r\nHost: a\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n")
        held = f.from_client(b"GET /admin HTTP/1.1\r\nHost: a\r\nX-Forwarded-For: 127.0.0.1\r\n\r\n")
        self.assertEqual(held, b"")
        self.assertEqual(f.from_server(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n"), b"")
        self.assertEqual(f.from_client(b"anything"), b"")
        self.assertTrue(f.closed)

    def test_an_upgrade_after_other_requests_on_the_connection_is_refused(self):
        with self.assertRaises(Refused):
            feed(Forwarder("192.0.2.4"), GET + b"GET /ws HTTP/1.1\r\nHost: a\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n")


class RouteTest(unittest.TestCase):
    def test_forwarded_headers_are_for_terminate_routes_only(self):
        Route("web", "terminate", "127.0.0.1:0", "127.0.0.1:1", cert="c", key="k", forwarded_headers=True).validate()
        with self.assertRaisesRegex(ValueError, "forwarded_headers"):
            Route("t", "originate", "127.0.0.1:0", "127.0.0.1:1", ca="c", forwarded_headers=True).validate()

    def test_off_by_default(self):
        self.assertFalse(Route("web", "terminate", "127.0.0.1:0", "127.0.0.1:1").forwarded_headers)


@unittest.skipIf(REASON, REASON)
class EdgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        cls.ca = CA.init(d / "pki", "Forwarded Root")
        cls.srv, _ = cls.ca.issue("localhost", "server", ["127.0.0.1"], out=d / "srv")
        cls.cafile = str(d / "pki" / "ca.crt")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def app(self):
        """A plain HTTP app that records every byte it receives and answers each request."""
        seen, srv = [], socket.create_server(("127.0.0.1", 0))
        self.addCleanup(srv.close)

        def serve():
            while True:
                try:
                    c, _ = srv.accept()
                except OSError:
                    return
                with c:
                    data = c.recv(65536)
                    seen.append(data)
                    c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
        threading.Thread(target=serve, daemon=True).start()
        return srv.getsockname()[1], seen

    def edge(self, port, **kw):
        e = Edge(Route("web", "terminate", "127.0.0.1:0", f"127.0.0.1:{port}", cert=str(self.srv / "chain.pem"),
                       key=str(self.srv / "key.pem"), **kw)).start()
        self.addCleanup(e.stop, 1)
        return e

    def visit(self, edge, request):
        with tls.connect("127.0.0.1", edge.port, tls.client_context(policies.policy("strict"), self.cafile), "localhost", 5) as c:
            c.sendall(request)
            return c.recv(timeout=5)

    def test_the_app_sees_the_visitor_and_https_and_never_the_client_supplied_headers(self):
        port, seen = self.app()
        e = self.edge(port, forwarded_headers=True)
        reply = self.visit(e, b"GET / HTTP/1.1\r\nHost: shop.example\r\nX-Forwarded-For: 10.9.9.9\r\nX-Forwarded-Proto: http\r\n\r\n")
        self.assertTrue(reply.startswith(b"HTTP/1.1 200"))
        self.assertTrue(wait(lambda: seen))
        self.assertIn(b"X-Forwarded-For: 127.0.0.1\r\n", seen[0])
        self.assertIn(b"X-Forwarded-Proto: https\r\n", seen[0])
        self.assertNotIn(b"10.9.9.9", seen[0])

    def test_a_smuggling_attempt_gets_400_and_never_reaches_the_app(self):
        port, seen = self.app()
        e = self.edge(port, forwarded_headers=True)
        reply = self.visit(e, b"POST / HTTP/1.1\r\nHost: a\r\nContent-Length: 4\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\nGET /admin HTTP/1.1\r\n\r\n")
        self.assertTrue(reply.startswith(b"HTTP/1.1 400"))
        self.assertFalse(any(b"/admin" in s for s in seen))
        self.assertEqual(e.stats.snapshot().get("forwarded_refused"), 1)

    def test_without_the_setting_the_edge_still_relays_bytes_untouched(self):
        port, seen = self.app()
        e = self.edge(port)
        raw = b"GET / HTTP/1.1\r\nHost: a\r\nX-Forwarded-For: 10.9.9.9\r\n\r\n"
        self.visit(e, raw)
        self.assertTrue(wait(lambda: seen))
        self.assertEqual(seen[0], raw)
