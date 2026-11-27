"""Forwarded headers for web apps behind the edge (a route's `forwarded_headers = true`).

The edge reads each HTTP/1.x request the visitor sends, removes any Forwarded, X-Forwarded-* and X-Real-IP header the visitor
supplied, and adds X-Forwarded-For (the visitor's address), X-Forwarded-Proto (https) and X-Forwarded-Host (the Host asked
for). Bodies pass unchanged, framed by their own Content-Length or chunked encoding. Anything ambiguous, the shapes behind
request smuggling, is refused with 400 rather than guessed at. A WebSocket is relayed raw only after the app answers 101, and
only as the first request on a connection; if the app refuses the upgrade, nothing more from the visitor reaches it.
"""
import re

MAX_HEAD = 64 * 1024
TOKEN = re.compile(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
REQUEST = re.compile(rb"(" + TOKEN.pattern + rb") (\S+) HTTP/1\.([01])")
CHUNK = re.compile(rb"[0-9A-Fa-f]{1,16}")
STATUS = re.compile(rb"HTTP/1\.[01] (\d{3})")
STRIP = {b"forwarded", b"x-forwarded-for", b"x-forwarded-proto", b"x-forwarded-host", b"x-real-ip"}
REASONS = {400: b"Bad Request", 431: b"Request Header Fields Too Large"}


class Refused(Exception):
    """A request the edge will not pass on; `response` is what the visitor is told before the connection closes."""

    def __init__(self, status, why):
        super().__init__(why)
        body = why.encode() + b"\n"
        self.response = (b"HTTP/1.1 %d %s\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: %d\r\nConnection: close\r\n\r\n"
                         % (status, REASONS[status], len(body)) + body)


class Forwarder:
    """One visitor connection: `from_client` turns what the visitor sends into what the app receives; `from_server` watches
    the app's answer to an upgrade and returns any visitor bytes it may now pass on."""

    def __init__(self, client_ip):
        self.ip = client_ip.encode()
        self.buf, self.held, self.answer = b"", b"", b""
        self.state, self.left, self.requests = "head", 0, 0

    @property
    def closed(self):
        return self.state == "closed"

    def from_client(self, data):
        if self.state == "raw":
            return data
        if self.state == "closed":
            return b""
        if self.state == "upgrade":
            self.held += data
            return b""
        self.buf += data
        out = bytearray()
        while self.buf and self.state not in ("upgrade", "closed"):
            if not getattr(self, "_" + self.state.replace("-", "_"))(out):
                break
        if self.state == "upgrade":
            self.held, self.buf = self.buf, b""
        return bytes(out)

    def from_server(self, data):
        if self.state != "upgrade":
            return b""
        self.answer += data
        if b"\r\n" not in self.answer and len(self.answer) < 64:
            return b""
        m = STATUS.match(self.answer)
        if m and m.group(1) == b"101":
            self.state, released, self.held = "raw", self.held, b""
            return released
        self.state, self.held = "closed", b""
        return b""

    # --- states: each consumes from self.buf into out, and returns False when it needs more bytes

    def _head(self, out):
        while self.buf.startswith(b"\r\n"):  # a stray line break between requests is allowed
            self.buf = self.buf[2:]
        end = self.buf.find(b"\r\n\r\n")
        lf = self.buf.find(b"\n", 0, MAX_HEAD if end < 0 else end + 1)
        if lf >= 0 and (lf == 0 or self.buf[lf - 1] != 13):
            raise Refused(400, "a request line ends without CR LF")
        if end < 0:
            if len(self.buf) > MAX_HEAD:
                raise Refused(431, "the request's headers are too large")
            return False
        if end > MAX_HEAD:
            raise Refused(431, "the request's headers are too large")
        head, self.buf = self.buf[:end], self.buf[end + 4:]
        out += self._rewrite(head)
        return True

    def _rewrite(self, head):
        lines = head.split(b"\r\n")
        if any(b"\n" in line or b"\r" in line or b"\0" in line for line in lines):
            raise Refused(400, "a request line ends without CR LF or holds a NUL")
        m = REQUEST.fullmatch(lines[0])
        if not m:
            raise Refused(400, "not an HTTP/1.0 or HTTP/1.1 request")
        if m.group(1).upper() == b"CONNECT":
            raise Refused(400, "CONNECT tunnels are not passed on")
        kept, fields = [lines[0]], {}
        for line in lines[1:]:
            if line[:1] in (b" ", b"\t"):
                raise Refused(400, "folded header lines are not accepted")
            name, sep, value = line.partition(b":")
            if not sep or not TOKEN.fullmatch(name):
                raise Refused(400, "a header name is malformed")
            key = name.lower()
            fields.setdefault(key, []).append(value.strip(b" \t"))
            if key not in STRIP:
                kept.append(line)
        if len(fields.get(b"host", [])) > 1:
            raise Refused(400, "more than one Host header")
        chunked, length = self._framing(fields)
        upgrade = b"upgrade" in fields and any(t.strip().lower() == b"upgrade" for v in fields.get(b"connection", []) for t in v.split(b","))
        if upgrade and (self.requests or chunked or length):
            raise Refused(400, "an upgrade (WebSocket) must be the first request on a connection, with no body")
        self.requests += 1
        kept += [b"X-Forwarded-For: " + self.ip, b"X-Forwarded-Proto: https"]
        if fields.get(b"host"):
            kept.append(b"X-Forwarded-Host: " + fields[b"host"][0])
        self.state, self.left = ("upgrade", 0) if upgrade else ("chunk-size", 0) if chunked else ("length", length) if length else ("head", 0)
        return b"\r\n".join(kept) + b"\r\n\r\n"

    @staticmethod
    def _framing(fields):
        te, cl = fields.get(b"transfer-encoding"), fields.get(b"content-length")
        if te:
            if cl:
                raise Refused(400, "both Content-Length and Transfer-Encoding")
            if [t.strip().lower() for v in te for t in v.split(b",")] != [b"chunked"]:
                raise Refused(400, "only Transfer-Encoding: chunked is accepted")
            return True, 0
        if cl:
            if not all(re.fullmatch(rb"\d{1,18}", v) for v in cl) or len(set(int(v) for v in cl)) != 1:
                raise Refused(400, "Content-Length is missing a number or disagrees with itself")
            return False, int(cl[0])
        return False, 0

    def _length(self, out):
        take = min(self.left, len(self.buf))
        out += self.buf[:take]
        self.buf, self.left = self.buf[take:], self.left - take
        if not self.left:
            self.state = "head"
        return self.left == 0

    def _chunk_size(self, out):
        end = self.buf.find(b"\r\n")
        if end < 0:
            if len(self.buf) > 4096:
                raise Refused(400, "a chunk size line is too long")
            return False
        line, self.buf = self.buf[:end], self.buf[end + 2:]
        size = line.split(b";", 1)[0]
        if not CHUNK.fullmatch(size) or b"\n" in line:
            raise Refused(400, "a chunk size is not a hexadecimal number")
        out += line + b"\r\n"
        self.left = int(size, 16)
        self.state = "chunk-data" if self.left else "trailers"
        return True

    def _chunk_data(self, out):
        take = min(self.left, len(self.buf))
        out += self.buf[:take]
        self.buf, self.left = self.buf[take:], self.left - take
        if self.left:
            return False
        self.state = "chunk-end"
        return True

    def _chunk_end(self, out):
        if len(self.buf) < 2:
            return False
        if self.buf[:2] != b"\r\n":
            raise Refused(400, "a chunk is longer than its size says")
        out += b"\r\n"
        self.buf, self.state = self.buf[2:], "chunk-size"
        return True

    def _trailers(self, out):
        end = self.buf.find(b"\r\n")
        if end < 0:
            if len(self.buf) > MAX_HEAD:
                raise Refused(431, "the request's trailers are too large")
            return False
        line, self.buf = self.buf[:end], self.buf[end + 2:]
        if not line:
            out += b"\r\n"
            self.state = "head"
            return True
        name, sep, _ = line.partition(b":")
        if not sep or not TOKEN.fullmatch(name) or b"\n" in line:
            raise Refused(400, "a trailer is malformed")
        if name.lower() not in STRIP:
            out += line + b"\r\n"
        return True
