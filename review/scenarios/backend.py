"""Plain HTTP test backend: files, uploads with sha256, slow answers, redirects and a header echo. python backend.py PORT DIR"""
import hashlib
import json
import sys
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


class H(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def reply(self, code, body, ctype="application/json", extra=None):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/headers":
            return self.reply(200, {"client": self.client_address[0], "headers": dict(self.headers)})
        if u.path == "/slow":
            time.sleep(float(q.get("s", ["60"])[0]))
            return self.reply(200, {"slept": q.get("s", ["60"])[0]})
        if u.path == "/redirect":  # what a typical app does: an absolute URL built from Host and its own idea of the scheme
            scheme = "https" if self.headers.get("X-Forwarded-Proto") == "https" else "http"
            return self.reply(302, b"", "text/plain", {"Location": f"{scheme}://{self.headers.get('Host')}/landing"})
        if u.path == "/landing":
            return self.reply(200, {"landed": True})
        return super().do_GET()

    def do_POST(self):
        n, h, left = 0, hashlib.sha256(), int(self.headers.get("Content-Length") or 0)
        while left:
            chunk = self.rfile.read(min(left, 1 << 20))
            if not chunk:
                break
            n += len(chunk)
            left -= len(chunk)
            h.update(chunk)
        self.reply(200, {"received": n, "sha256": h.hexdigest()})

    def log_message(self, *a):
        pass


port, root = int(sys.argv[1]), sys.argv[2]
ThreadingHTTPServer(("127.0.0.1", port), partial(H, directory=root)).serve_forever()
