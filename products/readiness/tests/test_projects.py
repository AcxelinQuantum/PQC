"""What you add can be taken away again (R5): a project is removed with its saved results, a GitHub link that leads nowhere is not
kept, and the repositories folder can be changed. Removing never touches the repository itself."""
import json
import time
from unittest.mock import patch

import pytest

from acxelin_readiness import console as rc

RSA = "from cryptography.hazmat.primitives.asymmetric import rsa\nrsa.generate_private_key(public_exponent=65537, key_size=2048)\n"


@pytest.fixture
def env(tmp_path):
    root = tmp_path / "repos"
    for name in ("shop", "api"):
        (root / name).mkdir(parents=True)
        (root / name / "k.py").write_text(RSA)
    app = rc.build(tmp_path / "home")
    r = lambda method, path, body=None: app.routes[(method, path)](body or {})[1]
    r("POST", "/api/setup", {"directory": str(root)})
    return app, r, root, tmp_path / "home"


def wait(r):
    while r("GET", "/api/projects/status")["running"]:
        time.sleep(0.05)
    return r("GET", "/api/projects/status")


def fetched(url, dest, token=None):
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "sign.py").write_text(RSA)
    return dest


def test_a_folder_project_is_removed_with_its_results_and_the_repository_is_left_alone(env):
    app, r, root, home = env
    for name in ("shop", "api"):
        r("POST", "/api/projects/register", {"name": name})
    r("POST", "/api/projects/scan", {"project": 0})
    wait(r)
    assert r("POST", "/api/projects/remove", {"project": 0}) == {"removed": "shop"}
    status = r("GET", "/api/status")
    assert [p["name"] for p in status["projects"]] == ["api"] and "shop" in status["available"]
    assert (root / "shop/k.py").exists(), "the repository itself is never touched"
    assert len(json.loads((home / "workspace.json").read_text())["projects"]) == 0, "its saved results and tracking go too"
    assert [p["name"] for p in rc.build(home).routes[("GET", "/api/status")]({})[1]["projects"]] == ["api"], "and it stays removed"
    assert r("GET", "/api/projects/status")["last"] is None


def test_github_and_imported_projects_are_removed_with_their_files(env):
    app, r, root, home = env
    with patch("acxelin_readiness.console.remote.fetch", side_effect=fetched):
        i = r("POST", "/api/projects/github", {"url": "https://github.com/acme/payments"})["project"]
        r("POST", "/api/projects/scan", {"project": i})
        wait(r)
    r("POST", "/api/projects/import", {"name": "billing.json", "cbom": {"bomFormat": "CycloneDX", "components": []}})
    assert r("POST", "/api/projects/remove", {"project": i}) == {"removed": "github.com/acme/payments"}
    assert json.loads((home / "github.json").read_text()) == {} and not any((home / "github").iterdir())
    j = next(p["id"] for p in r("GET", "/api/status")["projects"] if p["name"].startswith("Imported"))
    r("POST", "/api/projects/remove", {"project": j})
    assert json.loads((home / "imports.json").read_text()) == {} and not any((home / "imports").iterdir())
    assert r("GET", "/api/status")["projects"] == []


def test_nothing_is_removed_while_a_scan_runs_and_only_a_listed_project_can_be(env):
    app, r, root, home = env
    r("POST", "/api/projects/register", {"name": "shop"})
    with patch("acxelin_readiness.console.workspace.scan", side_effect=lambda *a, **k: time.sleep(0.5) or {}):
        r("POST", "/api/projects/scan", {"project": 0})
        with pytest.raises(ValueError, match="scan"):
            app.routes[("POST", "/api/projects/remove")]({"project": 0})
        wait(r)
    for bad in (5, -1, "0", None):
        with pytest.raises(ValueError):
            app.routes[("POST", "/api/projects/remove")]({"project": bad})


def test_a_github_link_that_leads_nowhere_does_not_become_a_project(env):
    app, r, root, home = env
    with patch("acxelin_readiness.console.remote.fetch", side_effect=rc.remote.Refused("Repository not found on GitHub. Check the link.")):
        i = r("POST", "/api/projects/github", {"url": "https://github.com/acme/no-such-repo"})["project"]
        r("POST", "/api/projects/scan", {"project": i})
        status = wait(r)
    assert "not found" in status["error"] and "not added" in status["error"]
    assert r("GET", "/api/status")["projects"] == [] and json.loads((home / "github.json").read_text()) == {}
    assert r("GET", "/api/overview")["board"]["projects"] == 0, "no 'Provisional: 0 of 1 projects scanned' for a link that never worked"


def test_a_repository_scanned_before_is_kept_when_github_is_unreachable_later(env):
    app, r, root, home = env
    with patch("acxelin_readiness.console.remote.fetch", side_effect=fetched):
        i = r("POST", "/api/projects/github", {"url": "https://github.com/acme/payments"})["project"]
        r("POST", "/api/projects/scan", {"project": i})
        wait(r)
    with patch("acxelin_readiness.console.remote.fetch", side_effect=rc.remote.Refused("Could not reach GitHub")):
        r("POST", "/api/projects/scan", {"project": i})
        assert "reach GitHub" in wait(r)["error"]
    assert [p["name"] for p in r("GET", "/api/status")["projects"]] == ["github.com/acme/payments"]


def test_the_repositories_folder_can_be_changed_and_changed_back(env, tmp_path):
    app, r, root, home = env
    r("POST", "/api/projects/register", {"name": "shop"})
    (tmp_path / "work/web").mkdir(parents=True)
    r("POST", "/api/setup", {"directory": str(tmp_path / "work")})
    status = r("GET", "/api/status")
    assert status["directory"] == str((tmp_path / "work").resolve()) and status["available"] == ["web"] and status["projects"] == []
    r("POST", "/api/setup", {"directory": str(root)})
    assert [p["name"] for p in r("GET", "/api/status")["projects"]] == ["shop"]
