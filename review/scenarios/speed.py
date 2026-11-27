"""Throughput on this machine: 200 MB straight from the backend vs through the edge (strict), same client library."""
import http.client
import ssl
import time
from pathlib import Path

ca = Path(__file__).parent / "homes/qguard/ca/ca.crt"


def get(conn):
    t = time.time()
    conn.request("GET", "/big.bin", headers={"Host": "static.audit.test"})
    r = conn.getresponse()
    n = 0
    while chunk := r.read(1 << 20):
        n += len(chunk)
    return n, time.time() - t


for label, mk in [("direct http 127.0.0.1:18080", lambda: http.client.HTTPConnection("127.0.0.1", 18080, timeout=120)),
                  ("through edge https :8443", lambda: http.client.HTTPSConnection("127.0.0.1", 8443, timeout=120,
                                                                                       context=_ctx()))]:
    pass


def _ctx():
    c = ssl.create_default_context(cafile=str(ca))
    c.check_hostname = False
    return c


for label, mk in [("direct http 127.0.0.1:18080", lambda: http.client.HTTPConnection("127.0.0.1", 18080, timeout=120)),
                  ("through edge https :8443 (strict)", lambda: http.client.HTTPSConnection("127.0.0.1", 8443, timeout=120, context=_ctx()))]:
    for i in range(2):
        n, s = get(mk())
        print(f"{label} run {i + 1}: {n / 1e6:.0f} MB in {s:.1f}s = {n / 1e6 / s:.1f} MB/s")
