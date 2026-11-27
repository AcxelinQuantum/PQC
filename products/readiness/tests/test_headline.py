"""One set of numbers (R2, R3, R4): every view leads with the things to fix now, counts findings that are only in tests apart, and
the console and the command line report the same scan the same way. Plain words by default (R10), and no supplier chase for a
password hash (R9)."""
import re
import subprocess
import sys
import time

import pytest

from acxelin_readiness import cli, console as rc, pipeline, report, workspace

RSA = "from cryptography.hazmat.primitives.asymmetric import rsa\nrsa.generate_private_key(public_exponent=65537, key_size=2048)\n"
MD5 = "import hashlib\nhashlib.md5(b'x')\n"
SHA256 = "import hashlib\nhashlib.sha256(b'x')\n"


def a(tier, test_only=False):
    return {"tier": tier, "test_only": test_only}


def test_the_headline_counts_add_up_and_keep_test_only_findings_apart():
    h = workspace.headline([a("critical"), a("high"), a("ok"), a("high", True), a("low"), a("medium", True)])
    assert h == {"fix_now": 2, "critical": 1, "high": 1, "medium": 0, "low": 1, "ok": 1, "findings": 4, "test_only": 2}
    assert sum(h[k] for k in ("critical", "high", "medium", "low", "ok")) == h["findings"]


def test_adding_harmless_cryptography_never_changes_what_needs_fixing():
    risky = [a("critical"), a("high")]
    assert workspace.headline(risky + [a("ok")] * 20)["fix_now"] == workspace.headline(risky)["fix_now"] == 2


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repos" / "shop"
    (root / "tests").mkdir(parents=True)
    (root / "keys.py").write_text(RSA)
    (root / "legacy.py").write_text(MD5)
    (root / "digest.py").write_text(SHA256)
    (root / "tests/test_keys.py").write_text(MD5 + "hashlib.sha1(b'y')\n" + RSA.replace("2048", "1024"))
    return root


def console_scan(tmp_path, repo):
    app = rc.build(tmp_path / "home")
    r = lambda method, path, body=None: app.routes[(method, path)](body or {})[1]
    r("POST", "/api/setup", {"directory": str(repo.parent)})
    r("POST", "/api/projects/register", {"name": repo.name})
    r("POST", "/api/projects/scan", {"project": 0})
    while r("GET", "/api/projects/status")["running"]:
        time.sleep(0.05)
    return r("GET", "/api/projects/status")["last"]


def cli_scan(capsys, repo, out, *more):
    assert cli.main(["scan", str(repo), "-o", str(out), *more]) == 0
    return capsys.readouterr().out


def sections(text):
    """The finding names the CLI lists, and those it lists under "Only in tests"."""
    listed, tests, part = [], [], None
    for line in text.splitlines():
        if re.match(r"^\S.*things? to fix now", line):
            part = listed
        elif line.startswith("Only in tests"):
            part = tests
        elif part is not None and re.match(r"^  (critical|high|medium|low|ok) ", line):
            part.append(line.split()[1])
        elif part is not None and line.strip() == "":
            continue
        elif part is not None and not line.startswith("  "):
            part = None
    return sorted(listed), sorted(tests)


def test_the_console_and_the_command_line_report_the_same_scan_the_same_way(tmp_path, capsys, repo):
    last = console_scan(tmp_path, repo)
    h = last["summary"]["headline"]
    text = cli_scan(capsys, repo, tmp_path / "out")
    lead = re.search(r"(\d+) things? to fix now \((\d+) critical, (\d+) high\), of (\d+) findings?; (\d+) more only in tests", text)
    assert lead, text
    assert [int(x) for x in lead.groups()] == [h["fix_now"], h["critical"], h["high"], h["findings"], h["test_only"]]
    listed, tests = sections(text)
    assert listed == sorted(x["name"] for x in last["assets"] if not x["test_only"])
    assert tests == sorted(x["name"] for x in last["assets"] if x["test_only"]) and "RSA-1024" in tests
    assert h["test_only"] >= 1 and h["findings"] >= 3


def test_the_command_line_speaks_plainly_unless_asked_for_the_pipeline(tmp_path, capsys, repo):
    plain = cli_scan(capsys, repo, tmp_path / "a")
    assert "detectors" not in plain and " raw " not in plain and "->" not in plain
    verbose = cli_scan(capsys, repo, tmp_path / "b", "--verbose")
    assert "detectors" in verbose and "raw" in verbose


def test_the_report_leads_with_the_things_to_fix_now_and_explains_its_assumptions(tmp_path, capsys, repo):
    cli_scan(capsys, repo, tmp_path / "out")
    html = (tmp_path / "out" / "report.html").read_text(encoding="utf-8")
    assert "things to fix now" in html.lower() and "Only in tests" in html
    assert "noisy by design" not in html and "CRQC" not in html and "Mosca" not in html
    assert "quantum computer able to break" in html


def test_why_texts_say_quantum_computer_instead_of_crqc_or_mosca(tmp_path):
    (tmp_path / "k.py").write_text(RSA)
    found = pipeline.run(tmp_path, "k").assets
    assert found and all("CRQC" not in x.why and "Mosca" not in x.why for x in found)


def test_scan_help_is_in_plain_words():
    out = subprocess.run([sys.executable, "-m", "acxelin_readiness", "--help"], capture_output=True, text=True).stdout
    assert "send the pipeline" not in out
    scan = subprocess.run([sys.executable, "-m", "acxelin_readiness", "scan", "--help"], capture_output=True, text=True).stdout
    assert "Mosca" not in scan and "CRQC" not in scan.upper().replace("--CRQC-YEAR", "")


def test_a_password_hash_library_is_not_on_the_supplier_list(tmp_path):
    root = tmp_path / "repos"
    (root / "web").mkdir(parents=True)
    (root / "web/requirements.txt").write_text("bcrypt==4.1\nargon2-cffi==23\nrsa==4.9\ncryptography==44\n")
    (root / "web/app.py").write_text("import bcrypt, argon2, rsa, cryptography\n")
    app = rc.build(tmp_path / "home")
    r = lambda method, path, body=None: app.routes[(method, path)](body or {})[1]
    r("POST", "/api/setup", {"directory": str(root)})
    r("POST", "/api/projects/scan-all", {})
    while r("GET", "/api/overview")["scan_all"]["running"]:
        time.sleep(0.05)
    o = r("GET", "/api/overview")
    libs = {x["name"]: x for x in o["libraries"]}
    assert libs["bcrypt"]["pq_needed"] is False and libs["argon2-cffi"]["pq_needed"] is False
    assert libs["rsa"]["pq_needed"] is True and not libs["rsa"]["pq"]
    assert o["board"]["libraries_without_pq"] == 1, "only rsa needs a supplier's post-quantum date"
    html = report.html(pipeline.run(root / "web", "web"))
    assert re.search(r"<td>bcrypt</td>(?:(?!</tr>).)*not needed", html, re.S)
