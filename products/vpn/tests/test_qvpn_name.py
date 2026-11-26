"""The product is qvpn now; the 1.x command name still works and says so."""
import sys

import pytest

from acxelin_vpn import cli


@pytest.mark.parametrize("argv0,reminded", [("acxelin-vpn", True), ("acxelin-qvpn", False)])
def test_the_old_command_still_runs_and_names_the_new_one(monkeypatch, capsys, argv0, reminded):
    monkeypatch.setattr(sys, "argv", [argv0, "--version"])
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    out, err = capsys.readouterr()
    assert e.value.code == 0 and out.startswith("acxelin-qvpn ")
    assert ("acxelin-vpn is now acxelin-qvpn" in err) == reminded
