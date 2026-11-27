"""Audit harness: start an installed product console in a fresh home, sign a Playwright browser in, take screenshots.

Signs in the way `acxelin-<product> console link` does: the owner-only console.token buys a single-use launch ticket.
"""
import json
import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

LOCAL = Path(os.environ["LOCALAPPDATA"]) / "Acxelin"
REPO = Path(__file__).resolve().parents[2]
# Stage 1 ran the installed release; Stage 3 runs this checkout: ACXELIN_AUDIT_CHECKOUT=1 uses the repository's .venv
CHECKOUT = bool(os.environ.get("ACXELIN_AUDIT_CHECKOUT"))
_bin = {"qguard": "acxelin-qguard", "qvpn": "acxelin-qvpn", "qreadiness": "acxelin-qreadiness"}
_installed = {"qguard": "tls", "qvpn": "vpn", "qreadiness": "readiness"}
EXE = {p: (REPO / ".venv/Scripts" if CHECKOUT else LOCAL / _installed[p] / "Scripts") / f"{c}.exe" for p, c in _bin.items()}
SHOTS = REPO / ("review/screenshots/stage3" if CHECKOUT else "review/screenshots/stage1")
ENV = os.environ | {"ACXELIN_OPENSSL": os.environ.get("ACXELIN_OPENSSL", r"C:\Program Files\OpenSSL-Win64\bin"), "PYTHONUTF8": "1"}
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def run(product, *args, cwd=None, timeout=300, env=None):
    """Run an installed product command; returns (exit code, combined output)."""
    p = subprocess.run([str(EXE[product]), *args], cwd=cwd, env=ENV | (env or {}), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip()


def wait_port(port, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        try:
            socket.create_connection(("127.0.0.1", port), 0.5).close()
            return
        except OSError:
            time.sleep(0.3)
    raise TimeoutError(f"nothing listening on {port}")


class Console:
    def __init__(self, product, home, port, *extra, env=None):
        self.product, self.home, self.port = product, Path(home), port
        self.home.mkdir(parents=True, exist_ok=True)
        self.log = open(self.home.parent / f"{self.home.name}-console-{port}.log", "w", encoding="utf-8")
        self.proc = subprocess.Popen([str(EXE[product]), "console", "--no-browser", "--home", str(self.home), "--port", str(port), *extra],
                                     env=ENV | (env or {}), stdout=self.log, stderr=subprocess.STDOUT)
        wait_port(port)

    def url(self):
        token = (self.home / "console.token").read_text().strip()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/ticket", b"{}",
                                     {"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        return f"http://127.0.0.1:{self.port}/#{json.loads(DIRECT.open(req, timeout=5).read())['ticket']}"

    def stop(self):
        self.proc.terminate()
        self.proc.wait(10)
        self.log.close()


def shot(page, product, name, full=True):
    out = SHOTS / product
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.png"
    page.screenshot(path=str(path), full_page=full)
    return path
