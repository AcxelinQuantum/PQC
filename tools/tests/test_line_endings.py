"""Scripts that run inside Linux images keep LF line endings in every checkout, Windows included: a CRLF `#!/bin/sh` cannot start,
so an image built from a Windows checkout would not run."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def attributes(paths):
    out = subprocess.run(["git", "check-attr", "eol", "--", *paths], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return {line.split(": ")[0]: line.split(": ")[-1] for line in out.splitlines()}


def test_shell_scripts_and_dockerfiles_are_checked_out_with_lf():
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    scripts = [p for p in tracked if p.endswith(".sh") or Path(p).name == "Dockerfile"]
    assert "products/vpn/deploy/entrypoint.sh" in scripts
    wrong = {p: eol for p, eol in attributes(scripts).items() if eol != "lf"}
    assert not wrong, f"add these to .gitattributes with eol=lf: {wrong}"
