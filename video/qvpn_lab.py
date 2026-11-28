"""The QVPN film's network, run in WSL as root by video/qvpn.py: Acme's headquarters and branch office joined over real IPsec,
a WireGuard gateway and enrollment service at headquarters, and Alice's laptop, each in its own network namespace, run by this
checkout's acxelin-qvpn. The administrator's console runs here in WSL's own network, and Alice's app is reached through a
forwarder, so Windows opens both on 127.0.0.1.

    python qvpn_lab.py up CONSOLE_PORT APP_PORT    prints one JSON line when everything is protected; stops when stdin closes
    python qvpn_lab.py down                         removes everything an interrupted run left
"""
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

LAB = Path("/srv/acme/lab")
NS = {"hq": "acme-hq", "branch": "acme-branch", "alice": "acme-alice"}
NETNS_ETC = Path("/etc/netns/acme-alice")
VPN = [sys.executable, "-m", "acxelin_vpn"]
ENV = os.environ | {"ACXELIN_OPENSSL": "/usr/lib/x86_64-linux-gnu", "PYTHONUNBUFFERED": "1"}
CHARON = "/usr/lib/ipsec/charon"
PROCS = []


def sh(*cmd, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True, env=ENV, stdin=subprocess.DEVNULL, cwd=LAB if LAB.exists() else "/")
    if check and r.returncode:
        raise SystemExit(f"lab: {' '.join(map(str, cmd))} failed: {r.stdout}{r.stderr}")
    return r


def spawn(ns, name, *cmd):
    log = open(LAB / "logs" / f"{name}.log", "w", encoding="utf-8")
    PROCS.append(subprocess.Popen(["ip", "netns", "exec", NS[ns], *cmd], cwd=LAB, stdout=log, stderr=subprocess.STDOUT,
                                  stdin=subprocess.DEVNULL, env=ENV, start_new_session=True))
    return PROCS[-1]


def down():
    for p in PROCS:
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except OSError:
            pass
    for p in PROCS:
        try:
            p.wait(8)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
    for ns in NS.values():
        for pid in sh("ip", "netns", "pids", ns, check=False).stdout.split():
            try:
                if int(pid) != os.getpid():
                    os.kill(int(pid), signal.SIGKILL)
            except OSError:
                pass
    for proc in Path("/proc").glob("[0-9]*"):  # a copy left by an interrupted run, in any namespace
        try:
            line = (proc / "cmdline").read_bytes()
        except OSError:
            continue
        if b"/srv/acme/lab" in line and int(proc.name) != os.getpid():
            try:
                os.kill(int(proc.name), signal.SIGKILL)
            except OSError:
                pass
    for ns in NS.values():
        sh("ip", "netns", "del", ns, check=False)
    shutil.rmtree(NETNS_ETC, ignore_errors=True)
    try:
        NETNS_ETC.parent.rmdir()  # only when empty: nothing else uses it
    except OSError:
        pass


def network():
    """HQ (LAN 192.168.10.1) cabled to the branch (LAN 192.168.20.1) and to Alice; WSL reaches each site's status address."""
    for ns in NS.values():
        sh("ip", "netns", "add", ns)
        sh("ip", "-n", ns, "link", "set", "lo", "up")
    cables = (("acme-hq-br", "hq", "10.30.0.1", "acme-br-hq", "branch", "10.30.0.2"),
              ("acme-hq-al", "hq", "10.40.0.1", "acme-al-hq", "alice", "10.40.0.2"),
              ("acme-mg-hq", None, "10.50.0.2", "acme-hq-mg", "hq", "10.50.0.1"),
              ("acme-mg-br", None, "10.51.0.2", "acme-br-mg", "branch", "10.51.0.1"))
    for a, a_ns, a_ip, b, b_ns, b_ip in cables:
        sh("ip", "link", "add", a, "type", "veth", "peer", "name", b)
        for dev, ns, ip in ((a, a_ns, a_ip), (b, b_ns, b_ip)):
            pre = ["-n", NS[ns]] if ns else []
            if ns:
                sh("ip", "link", "set", dev, "netns", NS[ns])
            sh("ip", *pre, "addr", "add", f"{ip}/24", "dev", dev)
            sh("ip", *pre, "link", "set", dev, "up")
    sh("ip", "-n", NS["hq"], "addr", "add", "192.168.10.1/32", "dev", "lo")
    sh("ip", "-n", NS["branch"], "addr", "add", "192.168.20.1/32", "dev", "lo")
    sh("ip", "-n", NS["hq"], "route", "add", "192.168.20.0/24", "via", "10.30.0.2")
    sh("ip", "-n", NS["branch"], "route", "add", "192.168.10.0/24", "via", "10.30.0.1")
    NETNS_ETC.mkdir(parents=True, exist_ok=True)  # Alice's laptop finds Acme's servers by name
    (NETNS_ETC / "hosts").write_text("127.0.0.1 localhost\n10.40.0.1 vpn.acme.example ca.acme.example\n", encoding="utf-8")


def site(name, address, metrics, peer, peer_address, local, remote, ca, dial):
    lines = ["[site]", f'name = "{name}"', f'address = "{address}"', f'cert = "{LAB}/pki/{name}/chain.pem"', f'key = "{LAB}/pki/{name}/key.pem"',
             f'ca = "{ca}/ca.crt"', f'crl = "{ca}/crl.pem"', f'vici = "unix://{LAB}/{name}.vici"', f'metrics = "{metrics}"',
             *([] if dial else [f'keyring_listen = "{address}:7443"']), "", "[[peer]]", f'name = "{peer}"', f'address = "{peer_address}"',
             f'local_subnets = ["{local}"]', f'remote_subnets = ["{remote}"]', *(["initiate = true", f'keyring = "{peer_address}:7443"'] if dial else [])]
    (LAB / f"{name}.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    conf = LAB / f"{name}.conf"
    conf.write_text(f"charon {{\n plugins {{ vici {{ socket = unix://{LAB}/{name}.vici }} }}\n"
                    f" filelog {{ log {{ path = {LAB}/logs/charon-{name}.log\n flush_line = yes\n default = 1\n }} }}\n}}\n", encoding="utf-8")


def status(url):
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url + "/status", timeout=3) as r:
            return json.loads(r.read())
    except (OSError, ValueError):
        return {}


def protected(url):
    peers = [p for k, p in status(url).items() if not k.startswith("_")]
    return bool(peers) and all((t := p.get("tunnel") or {}).get("state") == "ESTABLISHED" and t.get("ppk") and "ML_KEM" in t.get("key_exchange", "")
                               and any(c.get("state") == "INSTALLED" and c.get("bytes_in", 0) > 0 for c in t.get("children", [])) for p in peers)


def wait(cond, what, seconds=90):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return
        time.sleep(0.5)
    logs = "\n".join(f"--- {f.name}\n{f.read_text(errors='replace')[-1200:]}" for f in sorted((LAB / "logs").glob("*.log")))
    raise SystemExit(f"lab: {what}\n{logs}")


def forward(port, ns):
    """127.0.0.1:`port` here to 127.0.0.1:`port` in namespace `ns` (WSL forwards this one to Windows). Each connection's thread
    joins the namespace on its own, so the app stays bound to its laptop's loopback as the product starts it."""
    fd = os.open(f"/run/netns/{ns}", os.O_RDONLY)
    srv = socket.create_server(("127.0.0.1", port))

    def pipe(a, b):
        try:
            while data := a.recv(65536):
                b.sendall(data)
        except OSError:
            pass
        finally:
            for s in (a, b):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def one(c):
        os.setns(fd, os.CLONE_NEWNET)
        try:
            u = socket.create_connection(("127.0.0.1", port), timeout=10)
        except OSError:
            return c.close()
        u.settimeout(None)
        threading.Thread(target=pipe, args=(c, u), daemon=True).start()
        pipe(u, c)

    def loop():
        while True:
            c, _ = srv.accept()
            threading.Thread(target=one, args=(c,), daemon=True).start()
    threading.Thread(target=loop, daemon=True).start()
    return srv


def up(console_port, app_port):
    from acxelin_core import console as core
    from acxelin_vpn import console as vc
    down()
    shutil.rmtree(LAB, ignore_errors=True)
    (LAB / "logs").mkdir(parents=True)
    network()
    home = LAB / "console"
    app = vc.build(home)
    call = lambda path, body=None: app.routes[("POST" if body is not None else "GET", path)](body or {})
    call("/api/ca/create", {"name": "Acme VPN Root"})
    ca = home / "ca"
    for kind, name, san in (("site", "hq.acme.example", "10.30.0.1"), ("site", "branch.acme.example", "10.30.0.2"),
                            ("server", "vpn.acme.example", "vpn.acme.example"), ("server", "ca.acme.example", "ca.acme.example")):
        sh(*VPN, "ca", "issue", kind, name, "--san", san, "--dir", str(ca), "--out", str(LAB / "pki" / name))
    site("hq.acme.example", "10.30.0.1", "10.50.0.1:9101", "branch.acme.example", "10.30.0.2", "192.168.10.0/24", "192.168.20.0/24", ca, False)
    site("branch.acme.example", "10.30.0.2", "10.51.0.1:9101", "hq.acme.example", "10.30.0.1", "192.168.20.0/24", "192.168.10.0/24", ca, True)
    for where, name in (("hq", "hq.acme.example"), ("branch", "branch.acme.example")):
        spawn(where, f"charon-{where}", "unshare", "-m", "sh", "-c", f"mount -t tmpfs tmpfs /run && STRONGSWAN_CONF={LAB}/{name}.conf exec {CHARON}")
    wait(lambda: all((LAB / f"{n}.vici").exists() for n in ("hq.acme.example", "branch.acme.example")), "strongSwan did not start", 30)
    if "ML_KEM_768" not in sh("ip", "netns", "exec", NS["hq"], *VPN, "check", "--config", str(LAB / "hq.acme.example.toml"), check=False).stdout:
        raise SystemExit("lab: this strongSwan offers no ML-KEM")
    spawn("hq", "site-hq", *VPN, "up", "--config", str(LAB / "hq.acme.example.toml"))
    spawn("branch", "site-branch", *VPN, "up", "--config", str(LAB / "branch.acme.example.toml"))
    spawn("branch", "traffic-branch", "sh", "-c", "while true; do ping -c 1 -W 1 -I 192.168.20.1 192.168.10.1; sleep 2; done")
    (LAB / "hq").mkdir()
    (LAB / "gateway.toml").write_text("\n".join([
        "[wireguard]", 'name = "vpn.acme.example"', 'endpoint = "vpn.acme.example:51820"', 'keyring_listen = "10.40.0.1:7444"', 'pool = "10.99.0.0/24"',
        'routes = ["192.168.10.0/24"]', f'cert = "{LAB}/pki/vpn.acme.example/chain.pem"', f'key = "{LAB}/pki/vpn.acme.example/key.pem"',
        f'ca = "{ca}/ca.crt"', f'crl = "{ca}/crl.pem"', 'interface = "acme-wg0"', f'private_key = "{LAB}/hq/wireguard.key"',
        f'state = "{LAB}/hq/wireguard-state.json"', "rotate_minutes = 2", 'metrics = "10.50.0.1:9102"']) + "\n", encoding="utf-8")
    spawn("hq", "gateway", *VPN, "gateway", "--config", str(LAB / "gateway.toml"))
    spawn("hq", "enroll", *VPN, "ca", "serve", "--dir", str(ca), "--listen", "10.40.0.1:9443",
          "--cert", str(LAB / "pki/ca.acme.example/chain.pem"), "--key", str(LAB / "pki/ca.acme.example/key.pem"))
    (LAB / "alice").mkdir()
    spawn("alice", "traffic-alice", "sh", "-c", "while true; do ping -c 1 -W 1 192.168.10.1; sleep 2; done")
    wait(lambda: protected("http://10.50.0.1:9101") and protected("http://10.51.0.1:9101"), "the sites' tunnel did not come up protected", 120)
    wait(lambda: status("http://10.50.0.1:9102").get("_gateway"), "the WireGuard gateway did not answer", 30)
    alice = spawn("alice", "app", "unshare", "-m", "sh", "-c", f"mount -t tmpfs tmpfs /run && exec {sys.executable} {Path(__file__).resolve()} app {app_port}")
    wait(lambda: (LAB / "app.ticket").exists() or alice.poll() is not None, "the app did not start", 30)
    call("/api/people/settings", {"enroll": "https://ca.acme.example:9443", "gateway": "vpn.acme.example:7444"})
    call("/api/services/add", {"kind": "site", "name": "Headquarters", "url": "http://10.50.0.1:9101"})
    call("/api/services/add", {"kind": "gateway", "name": "Remote access", "url": "http://10.50.0.1:9102"})
    server = core.start(app, home, console_port)
    forward(app_port, NS["alice"])
    print(json.dumps({"console": f"http://127.0.0.1:{console_port}/#{app.sessions.ticket()}",
                      "app": f"http://127.0.0.1:{app_port}/#{(LAB / 'app.ticket').read_text().strip()}",
                      "branch": "http://10.51.0.1:9101"}), flush=True)
    try:
        for line in sys.stdin:
            if line.strip() == "quit":
                break
    finally:
        server.shutdown()


def app_mode(port):
    """Alice's laptop: the product's VPN window service, as `acxelin-qvpn app` starts it, on this namespace's loopback."""
    import logging
    from acxelin_vpn import app as va
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    window = va.App(folder=LAB / "alice", interface="acme-wg1")
    srv = va.serve(window, ("127.0.0.1", port))
    (LAB / "app.ticket").write_text(window.ticket(), encoding="utf-8")
    try:
        srv.serve_forever()
    finally:
        window.disconnect()


def main():
    cmd = sys.argv[1]
    if cmd == "app":
        return app_mode(int(sys.argv[2]))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        if cmd == "up":
            up(int(sys.argv[2]), int(sys.argv[3]))
    finally:
        down()


if __name__ == "__main__":
    main()
