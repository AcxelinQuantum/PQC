"""Problems found by using Acxelin QVPN as a first-time customer would; each test shows the problem fixed."""
import contextlib
import io
import json
import os
import shlex
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from acxelin_core.pki import CA

from acxelin_vpn import app, checks, cli, join, setup


def test_the_printed_next_steps_survive_a_folder_with_spaces(tmp_path):
    folder = tmp_path / "VPN Ops Ünï" / "acxelin-vpn"
    text = setup.next_steps(folder / "gateway.toml", "vpn.acme.example")
    commands = [line.strip() for line in text.splitlines() if line.strip().startswith("acxelin-qvpn ")]
    assert len(commands) == 3, text
    for line in commands:
        args = shlex.split(line) if os.name != "nt" else line
        if os.name != "nt":
            paths = [args[i + 1] for i, a in enumerate(args) if a in ("--dir", "--cert", "--key", "--config")]
            assert paths and all(p.startswith(str(folder)) for p in paths), (line, paths)
    assert f"--ca {shlex.quote(str(folder / 'pki'))}" in text.replace("\n", " ") if os.name != "nt" else True


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out), pytest.raises(SystemExit) as e:
        cli.main(list(argv))
    return e.value.code, out.getvalue()


def invitation_text(**extra):
    return json.dumps({"acxelin_invite": 1, "name": "bob", "enroll": "https://127.0.0.1:1", "ca_fingerprint": "ab" * 32,
                       "gateway": "127.0.0.1:7444", "expires": "2099-01-01T00:00:00+00:00", "token": "0123abcd.secret"} | extra)


def test_v5_a_setup_exe_install_is_never_told_to_use_pip(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(checks.shutil, "which", lambda name: None)
    monkeypatch.setattr(checks, "_have", lambda module: False)
    rows = checks.prerequisites()
    assert rows and not [r for r in rows if "pip" in r["message"] + r["action"]], rows


def test_v5_doctor_counts_every_line_it_prints(tmp_path, monkeypatch):
    monkeypatch.setattr(checks.shutil, "which", lambda name: None)
    monkeypatch.setattr(checks, "_have", lambda module: False)
    CA.init(tmp_path / "pki", "Doctor Root")  # an unencrypted key (a warning) and no CRL yet (a problem)
    conf = tmp_path / "missing.toml"
    for argv in (["doctor"], ["doctor", "--ca", str(tmp_path / "pki")], ["doctor", "--ca", str(tmp_path / "pki"), "--config", str(conf)]):
        _, out = run(*argv)
        lines = out.splitlines()
        fails, warns = sum(x.startswith("FAIL") for x in lines), sum(x.startswith("WARN") for x in lines)
        assert f"{fails} problem(s), {warns} warning(s)" in out, out
    _, out = run("doctor", "--ca", str(tmp_path / "pki"))
    assert "WireGuard" not in out and "desktop app" not in out and "pip" not in out, "checking a CA folder is the administrator's machine"


def test_v6_the_cli_says_where_the_consoles_ca_is_when_there_is_no_pki_here(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ACXELIN_VPN_HOME", str(tmp_path / "console"))
    code, out = run("ca", "list")
    assert code == 1 and "console" not in out, "no console CA either: the error stays as it was"
    console_ca = tmp_path / "console" / "ca"
    CA.init(console_ca, "Console Root")
    for argv in (("ca", "list"), ("invite", "x", "--enroll", "https://ca.example:9443", "--gateway", "vpn.example:7444")):
        code, out = run(*argv)
        assert code == 1 and out.startswith("error: ") and str(console_ca) in out and "--dir" in out and out.count("\n") == 1, out
    assert run("ca", "list", "--dir", str(console_ca))[0] == 0
    code, out = run("ca", "init", "--name", "Local Root", "--no-encrypt")
    assert code == 0 and str(console_ca) in out, "a second CA is made only knowingly"
    assert run("ca", "list")[0] == 0, "./pki, once it exists, is the default as before"


def test_v10_join_refuses_a_short_device_passphrase_before_using_the_invitation(tmp_path, monkeypatch):
    inv = tmp_path / "bob.acxinvite"
    inv.write_text(invitation_text())
    monkeypatch.setenv("SHORT_PW", "x" * (join.MIN_PASSPHRASE - 1))
    code, out = run("join", str(inv), "--no-apply", "--key-passphrase-env", "SHORT_PW")
    assert code == 1 and f"at least {join.MIN_PASSPHRASE} characters" in out, out
    assert "token" in json.loads(inv.read_text()) and not (tmp_path / "bob").exists(), "the one-time invitation is still usable"


def test_v10_the_window_refuses_a_short_passphrase_itself_not_only_in_the_page(tmp_path):
    w = app.App(folder=tmp_path, apply=False)
    w.load("bob.acxinvite", invitation_text())
    short = "x" * (join.MIN_PASSPHRASE - 1)
    status, body = w.handle("POST", "/api/connect", {"passphrase": short, "repeat": short})
    assert status == 400 and f"at least {join.MIN_PASSPHRASE} characters" in body["error"]
    assert "token" in json.loads((tmp_path / "bob.acxinvite").read_text()) and not (tmp_path / "bob").exists()


def test_v4_a_wrong_invitation_file_says_what_happened_and_what_to_do(tmp_path):
    w = app.App(folder=tmp_path, apply=False)
    for text in ("\x89PNG\r\n\x1a\n", "{}", invitation_text(acxelin_invite=2)):
        status, body = w.handle("POST", "/api/invitation", {"name": "holiday.png", "text": text})
        assert status == 400 and "holiday.png is not an Acxelin QVPN invitation" in body["error"] and "administrator" in body["error"]
        assert "acxelin-qvpn invite" not in body["error"], "the person is not the administrator"
    assert list(tmp_path.glob("*.acxinvite")) == []


@pytest.mark.skipif(__import__("acxelin_core.openssl", fromlist=["available"]).available() is not None, reason="needs OpenSSL 3.5+ (set ACXELIN_OPENSSL)")
def test_v11_a_failed_enrollment_names_the_address_it_tried(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    inv = join.parse(invitation_text(enroll=f"https://127.0.0.1:{port}"))
    with pytest.raises(ValueError, match=f"https://127.0.0.1:{port}"):
        join.enroll(inv, tmp_path / "bob", tmp_path / "bob.acxinvite", b"device passphrase")


def test_v11_status_finds_the_window_running_without_a_tunnel(tmp_path, monkeypatch):
    from acxelin_vpn import platforms
    monkeypatch.setattr(platforms, "folder", lambda: tmp_path / "system")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    window = app.App(folder=tmp_path / ".acxelin-vpn", apply=False)

    class Agreed:
        def status(self):
            return {"state": "agreed", "gateway": "vpn.example:7444", "address": "10.99.0.2/24", "error": None}
    window.client = Agreed()
    srv = app.serve(window)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        (tmp_path / ".acxelin-vpn").mkdir(exist_ok=True)
        (tmp_path / ".acxelin-vpn" / "wg0.app.json").write_text(json.dumps({"port": srv.server_address[1], "token": window.token}))
        code, out = run("status")
        assert "No VPN client is running" not in out and "no tunnel configured (--no-apply)" in out and code == 1, out
    finally:
        srv.shutdown()
        srv.server_close()


def test_v11_ca_issue_help_says_what_a_server_certificate_is_for():
    _, out = run("ca", "issue", "--help")
    assert "enrollment service" in " ".join(out.split())


def test_access_without_an_action_shows_who_is_limited(tmp_path):
    conf = Path(__file__).resolve().parents[1] / "config" / "gateway.toml"
    r = subprocess.run([sys.executable, "-m", "acxelin_vpn", "access", "--config", str(conf)], capture_output=True, text=True, timeout=60)
    assert "required" not in r.stderr, r.stderr
    shown = subprocess.run([sys.executable, "-m", "acxelin_vpn", "access", "show", "--config", str(conf)], capture_output=True, text=True, timeout=60)
    assert (r.returncode, r.stdout) == (shown.returncode, shown.stdout), (r.stdout + r.stderr, shown.stdout + shown.stderr)
