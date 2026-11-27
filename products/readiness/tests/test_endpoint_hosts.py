"""Each host keeps its own dated results (R7): a check adds to the hosts it checked and leaves the others' last results in place,
and "what changed" compares a host with its own previous result, not with whatever was checked last."""
import json
import time
from unittest.mock import patch

import pytest

from acxelin_readiness import console as rc


def row(target, grade):
    return {"target": target, "grade": grade, "protocol": "tls", "certificate": None, "accepts": [], "negotiated": None,
            "error": "connection refused" if grade == "F" else None}


@pytest.fixture
def app(tmp_path):
    return rc.build(tmp_path / "home")


def check(app, *rows):
    with patch("acxelin_readiness.console.endpoints.scan", return_value=list(rows)):
        app.routes[("POST", "/api/endpoints/scan")]({"targets": [r["target"] for r in rows]})
        while status(app)["running"]:
            time.sleep(0.02)
    return status(app)


def status(app):
    return app.routes[("GET", "/api/endpoints/status")]({})[1]


def test_checking_other_hosts_keeps_each_hosts_last_result(app):
    check(app, row("a.example:443", "C"))
    last = check(app, row("b.example:443", "F"), row("c.example:443", "F"))["last"]
    grades = {r["target"]: r["grade"] for r in last["endpoints"]}
    assert grades == {"a.example:443": "C", "b.example:443": "F", "c.example:443": "F"}, "unreachable hosts do not wipe the earlier grade"
    assert last["summary"]["grades"]["C"] == 1 and last["summary"]["endpoints"] == 3
    assert last["targets"] == ["b.example:443", "c.example:443"], "the last check's own hosts"
    checked = {r["target"]: r["checked"] for r in last["endpoints"]}
    assert checked["a.example:443"] < checked["b.example:443"], "each row says when that host was checked"


def test_what_changed_compares_a_host_with_its_own_last_result(app):
    check(app, row("a.example:443", "C"))
    check(app, row("b.example:443", "A"))
    last = check(app, row("a.example:443", "B"))["last"]
    assert last["changes"] == [{"target": "a.example:443", "before": "C", "after": "B"}], "not against b, which was checked in between"
    again = check(app, row("b.example:443", "A"))["last"]
    assert again["changes"] == []


def test_each_host_keeps_a_bounded_dated_history_across_restarts(app, tmp_path):
    for g in ("F", "C", "A"):
        check(app, row("a.example:443", g))
    again = rc.build(tmp_path / "home")
    history = status(again)["hosts"]["a.example:443"]
    assert [h["grade"] for h in history] == ["F", "C", "A"] and all(isinstance(h["finished"], float) for h in history)
    assert status(again)["last"]["endpoints"][0]["grade"] == "A"
    for _ in range(35):
        check(again, row("a.example:443", "A"))
    assert len(status(again)["hosts"]["a.example:443"]) == 30


def test_a_host_can_be_forgotten(app):
    check(app, row("a.example:443", "C"), row("typo.example:443", "F"))
    assert app.routes[("POST", "/api/endpoints/forget")]({"target": "typo.example:443"})[1] == {"forgotten": "typo.example:443"}
    assert [r["target"] for r in status(app)["last"]["endpoints"]] == ["a.example:443"]
    with pytest.raises(ValueError):
        app.routes[("POST", "/api/endpoints/forget")]({"target": "never.example:443"})


@pytest.mark.parametrize("damage", ["{not json", "[1, 2]", '{"hosts": {"a:443": {"result": {"grade": "Z"}, "history": []}}}',
                                    '{"hosts": {"a:443": {"result": {"target": "a:443", "grade": "A"}, "history": [{"finished": NaN, "grade": "A"}]}}}'])
def test_a_damaged_host_history_starts_again_instead_of_stopping_the_console(tmp_path, damage):
    (tmp_path / "home").mkdir()
    (tmp_path / "home" / "endpoints-hosts.json").write_text(damage)
    s = status(rc.build(tmp_path / "home"))
    assert s["last"] is None or all(r["grade"] in "ABCF" for r in s["last"]["endpoints"])
    json.dumps(s, allow_nan=False)
