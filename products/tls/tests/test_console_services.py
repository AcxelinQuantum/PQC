"""The QGuard console protects services: it writes the settings file the QGuard service reads, shows what each service sees,
checks connections against public or QCertificate trust, and runs the enrollment a customer needs from day to day."""
import json
import socket
import time

import pytest
from acxelin_core import openssl

from acxelin_tls import console as tc
from acxelin_tls.edge import Edge, load_config, serve_metrics

needs_openssl = pytest.mark.skipif(openssl.available() is not None, reason="needs OpenSSL 3.5+ (set ACXELIN_OPENSSL)")


@pytest.fixture
def home(tmp_path):
    return tmp_path / "state"


@pytest.fixture
def app(home):
    a = tc.build(home)
    call(a, "POST", "/api/ca/create", {"name": "Example Root CA"})
    return a


def call(app, method, path, body=None):
    return app.routes[(method, path)](body or {})[1]


def save(app, **kw):
    body = {"kind": "app", "host": "shop.example", "port": 8443, "target": "127.0.0.1:8080"} | kw
    return call(app, "POST", "/api/services/save", body)


def settings(home):
    return load_config(home / "edge.toml")


def test_no_services_at_first_and_the_settings_file_is_named(app, home):
    s = call(app, "GET", "/api/services")
    assert s["services"] == [] and s["settings"] == str(home / "edge.toml") and s["running"] is False


def test_a_public_website_gets_transition_its_own_certificate_and_forwarded_headers(app, home, tmp_path):
    out = save(app, kind="website", host="www.example", port=443)
    routes, metrics = settings(home)
    r = routes[0]
    assert (r.policy, r.sni, r.listen, r.forwarded_headers, r.shadow) == ("transition", ["www.example"], "0.0.0.0:443", True, False)
    assert metrics == "127.0.0.1:9100"
    row = out["services"][0]
    assert row["kind"] == "website" and row["host"] == "www.example"
    assert any("not private" in p for p in row["problems"]), row["problems"]


def test_a_public_certificate_for_browsers_is_kept_with_the_website(app, home, tmp_path):
    (tmp_path / "pub.pem").write_text("x")
    (tmp_path / "pub.key").write_text("x")
    save(app, kind="website", host="www.example", port=443, public_cert=str(tmp_path / "pub.pem"), public_key=str(tmp_path / "pub.key"))
    r = settings(home)[0][0]
    assert (r.fallback_cert, r.fallback_key) == (str(tmp_path / "pub.pem"), str(tmp_path / "pub.key"))
    with pytest.raises(ValueError, match="does not exist"):
        save(app, kind="website", host="b.example", port=443, public_cert=str(tmp_path / "nope.pem"), public_key=str(tmp_path / "pub.key"))


def test_each_kind_of_service_gets_the_right_settings(app, home):
    save(app, kind="app", host="intranet.example", watch=True)
    save(app, kind="partner", host="api.example")
    save(app, kind="tcp", host="db.example", port=5433, target="127.0.0.1:5432")
    routes = {r.name: r for r in settings(home)[0]}
    assert routes["intranet.example"].policy == "strict" and routes["intranet.example"].shadow and routes["intranet.example"].forwarded_headers
    partner = routes["api.example"]
    assert partner.require_client_cert and partner.crl.endswith("crl.pem") and partner.ca.endswith("ca.crt")
    assert not routes["db.example"].forwarded_headers
    kinds = {s["host"]: s["kind"] for s in call(app, "GET", "/api/services")["services"]}
    assert kinds == {"intranet.example": "app", "api.example": "partner", "db.example": "tcp"}


@pytest.mark.parametrize("body,why", [({"host": "bad host"}, "not a valid host name"), ({"port": 0}, "port"), ({"port": "x"}, "port"),
                                      ({"target": "nowhere"}, "host:port"), ({"kind": "ftp"}, "kind"), ({"watch": "yes"}, "watch")])
def test_bad_input_is_refused_in_words_and_nothing_is_written(app, home, body, why):
    with pytest.raises(ValueError, match=why):
        save(app, **body)
    assert not (home / "edge.toml").exists()


def test_the_same_host_and_port_cannot_be_protected_twice(app):
    save(app)
    with pytest.raises(ValueError, match="already protects"):
        save(app)


def test_watch_then_turn_on_enforcement(app, home):
    save(app, watch=True)
    out = call(app, "POST", "/api/services/enforce", {"name": "shop.example"})
    assert settings(home)[0][0].shadow is False and out["services"][0]["shadow"] is False
    call(app, "POST", "/api/services/watch", {"name": "shop.example"})
    assert settings(home)[0][0].shadow is True


def test_a_website_cannot_be_watched_because_browsers_need_transition(app):
    save(app, kind="website", host="www.example", port=443)
    with pytest.raises(ValueError, match="website"):
        call(app, "POST", "/api/services/watch", {"name": "www.example"})


def test_editing_keeps_the_certificate_and_removing_leaves_the_others(app, home):
    save(app)
    cert = settings(home)[0][0].cert
    save(app, original="shop.example", target="127.0.0.1:9090")
    r = settings(home)[0][0]
    assert r.target == "127.0.0.1:9090" and r.cert == cert
    save(app, host="other.example")
    call(app, "POST", "/api/services/remove", {"name": "shop.example"})
    assert [r.name for r in settings(home)[0]] == ["other.example"]


def test_routes_the_console_does_not_make_are_kept_when_it_saves(app, home):
    (home / "edge.toml").write_text('[metrics]\nlisten = "127.0.0.1:9188"\n\n[[edge]]\nname = "tunnel"\nmode = "originate"\n'
                                    f'listen = "127.0.0.1:15432"\ntarget = "db.example:8443"\nca = "{(home / "ca" / "ca.crt").as_posix()}"\n')
    save(app)
    routes, metrics = settings(home)
    assert [r.name for r in routes] == ["tunnel", "shop.example"] and metrics == "127.0.0.1:9188"
    tunnel = next(s for s in call(app, "GET", "/api/services")["services"] if s["name"] == "tunnel")
    assert tunnel["managed"] is False


def test_saving_needs_the_ca_unlocked_and_says_so(tmp_path):
    a = tc.build(tmp_path / "h")
    call(a, "POST", "/api/ca/create", {"name": "R", "passphrase": "p-123456"})
    locked = tc.build(tmp_path / "h")
    with pytest.raises(ValueError, match="unlock"):
        save(locked)


@needs_openssl
def test_a_running_guard_reports_each_service_including_who_watch_mode_would_refuse(app, home):
    save(app, watch=True)
    routes, _ = settings(home)
    edges = [Edge(r).start() for r in routes]
    metrics = serve_metrics("127.0.0.1:0", edges, None)
    try:
        text = (home / "edge.toml").read_text().replace("127.0.0.1:9100", f"127.0.0.1:{metrics.server_address[1]}")
        (home / "edge.toml").write_text(text)
        from acxelin_core import tls
        classical = tls.Context(False, "X25519", None, "TLS_AES_256_GCM_SHA384", ca=str(home / "ca" / "ca.crt"))
        with tls.connect("127.0.0.1", edges[0].port, classical, "shop.example", 5):
            time.sleep(0.5)  # let the server finish its side of the handshake, as a real client would by sending a request
        time.sleep(0.3)
        row = call(app, "GET", "/api/services")["services"][0]
        assert call(app, "GET", "/api/services")["running"] is True
        assert row["status"]["would_refuse"] == 1 and row["status"]["refused"] == 0
        assert "no post-quantum key exchange offered" in row["status"]["reasons"]
    finally:
        for e in edges:
            e.stop(0)
        metrics.shutdown()


@needs_openssl
def test_the_console_can_run_qguard_on_this_computer_and_stop_it(app, home):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    save(app, port=port)
    (home / "edge.toml").write_text((home / "edge.toml").read_text().replace("127.0.0.1:9100", f"127.0.0.1:{port + 1 if port < 65000 else port - 1}"))
    out = call(app, "POST", "/api/guard/start")
    try:
        assert out["running"] is True
        with pytest.raises(ValueError, match="already running"):
            call(app, "POST", "/api/guard/start")
    finally:
        call(app, "POST", "/api/guard/stop")
    assert call(app, "GET", "/api/services")["running"] is False


@needs_openssl
def test_check_a_connection_with_qcertificate_or_public_trust(app, home):
    from acxelin_core import tls
    from acxelin_core.server import Server
    from acxelin_tls import policies
    cert = call(app, "POST", "/api/certificates/issue", {"kind": "server", "common_name": "localhost", "names": ["127.0.0.1"], "days": 30})
    srv = Server(("127.0.0.1", 0), lambda: tls.server_context(policies.policy("strict"), cert["chain"], cert["key"]), lambda c, a: c.recv(timeout=15))  # longer than any client here waits
    srv.start()
    try:
        ok = call(app, "POST", "/api/check", {"target": f"127.0.0.1:{srv.port}", "server_name": "localhost", "trust": "qcertificate"})
        assert ok["ok"] and ok["verdict"].startswith("quantum-safe key exchange, quantum-safe certificate")
        pub = call(app, "POST", "/api/check", {"target": f"127.0.0.1:{srv.port}", "server_name": "localhost", "trust": "public"})
        assert not pub["ok"] and "public certificate authorities this computer trusts" in pub["error"]
    finally:
        srv.stop(0)


def test_download_full_chain_and_key_as_one_pem_file(app, home):
    c = call(app, "POST", "/api/certificates/issue", {"kind": "server", "common_name": "web.example", "days": 30})
    d = app.routes[("POST", "/api/certificates/download")]({"serial": c["serial"], "key": True, "format": "pem"})[1]
    assert d.name.endswith(".pem") and d.data.count(b"BEGIN CERTIFICATE") >= 2 and b"PRIVATE KEY" in d.data
    d = app.routes[("POST", "/api/certificates/download")]({"serial": c["serial"], "format": "pem"})[1]
    assert b"PRIVATE KEY" not in d.data
    with pytest.raises(ValueError, match="format"):
        app.routes[("POST", "/api/certificates/download")]({"serial": c["serial"], "format": "pfx"})


def test_enrollment_tokens_are_shown_once_and_listed_without_their_secret(app, home):
    t = call(app, "POST", "/api/enrollment/token", {"kind": "server", "common_name": "device1.example", "hours": 24})
    assert "." in t["token"] and "acxelin-qguard ca enroll" in t["command"]
    listed = call(app, "GET", "/api/enrollment")
    assert listed["tokens"][0]["common_name"] == "device1.example" and listed["tokens"][0]["state"] == "unused"
    assert t["token"].split(".")[1] not in json.dumps(listed)
    assert t["token"].split(".")[1] not in (home / "audit.jsonl").read_text()
    e = call(app, "POST", "/api/enrollment/eab", {"note": "certbot on web1"})
    assert e["kid"].startswith("kid-") and "--eab-hmac-key" in e["command"]
    assert e["hmac"] not in json.dumps(call(app, "GET", "/api/enrollment"))


def test_the_authority_page_says_what_it_is_and_the_ca_certificate_downloads(app):
    a = call(app, "GET", "/api/authority")
    assert a["name"] == "Example Root CA" and a["algorithm"] == "ML-DSA-87" and len(a["fingerprint"]) == 64
    d = app.routes[("POST", "/api/ca/download")]({})[1]
    assert d.name == "ca.crt" and b"BEGIN CERTIFICATE" in d.data
