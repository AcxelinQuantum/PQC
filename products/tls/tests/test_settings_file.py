"""The console writes the same settings file the QGuard service reads: what it writes loads back as the same routes."""
from acxelin_tls.edge import Route, load_config, render_config


def test_routes_written_load_back_unchanged(tmp_path):
    for name in ("chain.pem", "key.pem", "public.pem", "public.key", "ca.crt", "crl.pem"):
        (tmp_path / name).write_text("x")
    p = lambda n: str(tmp_path / n)
    routes = [
        Route("shop.example", "terminate", "0.0.0.0:443", "127.0.0.1:8080", policy="transition", cert=p("chain.pem"), key=p("key.pem"),
              fallback_cert=p("public.pem"), fallback_key=p("public.key"), sni=["shop.example"], forwarded_headers=True),
        Route("api.example", "terminate", "0.0.0.0:443", "10.0.0.5:9000", cert=p("chain.pem"), key=p("key.pem"), ca=p("ca.crt"),
              crl=p("crl.pem"), require_client_cert=True, sni=["api.example"], shadow=True, max_connections=64, idle_timeout=120.5),
        Route("to-dc", "originate", "127.0.0.1:5432", "db.example:8443", ca=p("ca.crt"), server_name='db "quoted" \\ name'),
    ]
    f = tmp_path / "edge.toml"
    f.write_text(render_config(routes, "127.0.0.1:9100"), encoding="utf-8")
    loaded, metrics = load_config(f)
    assert metrics == "127.0.0.1:9100"
    strip = lambda r: {k: v for k, v in vars(r).items() if k != "shared"}
    assert [strip(r) for r in loaded] == [strip(r) for r in routes]


def test_defaults_are_left_out_so_the_file_stays_readable(tmp_path):
    text = render_config([Route("web", "terminate", "0.0.0.0:443", "127.0.0.1:8080", cert="c.pem", key="k.pem")], None)
    assert "max_connections" not in text and "shadow" not in text and "[metrics]" not in text
    assert text.lstrip().startswith("#")
