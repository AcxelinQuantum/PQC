"""Live reload: add a route to the running edge's settings file while a long request is in flight on another route."""
import http.client
import socket
import ssl
import threading
import time
from pathlib import Path

sc = Path(__file__).parent / "homes/qguard/sc"
cfg = sc / "edges.toml"
original = cfg.read_text()
ctx = ssl.create_default_context(cafile=str(sc.parent / "ca/ca.crt"))
ctx.check_hostname = False
result = {}


def long_request():
    c = http.client.HTTPSConnection("127.0.0.1", 8443, timeout=60, context=ctx)
    t = time.time()
    try:
        c.request("GET", "/slow?s=15", headers={"Host": "static.audit.test"})
        result["long"] = f"{c.getresponse().status} after {time.time() - t:.0f}s"
    except Exception as e:
        result["long"] = f"failed: {e}"


th = threading.Thread(target=long_request)
th.start()
time.sleep(2)
cfg.write_text(original + '\n[[edge]]\nname = "added-live"\nmode = "terminate"\nlisten = "0.0.0.0:8449"\ntarget = "127.0.0.1:18080"\ncert = "apps/chain.pem"\nkey = "apps/key.pem"\n')
t0 = time.time()
while time.time() - t0 < 30:
    try:
        socket.create_connection(("127.0.0.1", 8449), 1).close()
        print(f"new route listening {time.time() - t0:.1f}s after the file changed")
        break
    except OSError:
        time.sleep(0.5)
else:
    print("new route did not start within 30 s")
# a broken change: a missing certificate file for an existing route
cfg.write_text(original.replace('cert = "apps87/chain.pem"', 'cert = "missing/chain.pem"'))
time.sleep(6)
th.join()
print("in-flight request on the unchanged route:", result.get("long"))
cfg.write_text(original)
time.sleep(3)
log = (Path(__file__).parent / "edge.log").read_text().splitlines()
print("\n".join(line for line in log[-12:] if "added-live" in line or "cnsa2" in line or "configuration" in line))
