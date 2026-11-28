import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from release_check import FOLDERS, check, parse_tag  # noqa: E402

VERSION = {p: tomllib.loads((FOLDERS[p] / "pyproject.toml").read_text())["project"]["version"] for p in ("core", "qguard", "qvpn", "qreadiness")}


def test_tags_name_a_product_and_a_version():
    assert parse_tag("qguard-v1.0.0") == ("qguard", "1.0.0")
    assert parse_tag("refs/tags/qreadiness-v1.2.3") == ("qreadiness", "1.2.3")
    assert parse_tag("qvpn-v1.0.0") == ("qvpn", "1.0.0")
    for bad in ("v1.0.0", "qguard-1.0.0", "storage-v1.0.0", "qguard-v1.0", "qguard-v1.0.0-rc1;rm", "tls-v1.3.0", "vpn-v1.3.0", "readiness-v1.4.0"):
        with pytest.raises(ValueError):
            parse_tag(bad)


def test_the_tag_must_match_the_packaged_version_and_the_changelog():
    with pytest.raises(ValueError, match="pyproject"):
        check("qguard", "9.9.9", tags=["core-v1.0.0"])


def test_a_product_needs_a_released_core_in_its_range():
    assert check("qguard", VERSION["qguard"], tags=["core-v1.3.0", "core-v1.4.0"]) == "acxelin-core 1.4.0"
    assert check("qvpn", VERSION["qvpn"], tags=["core-v1.3.0", "core-v1.4.0"]) == "acxelin-core 1.4.0"
    with pytest.raises(ValueError, match="no released acxelin-core"):  # public roots and token listing need core 1.4.0: core first
        check("qguard", VERSION["qguard"], tags=["core-v1.0.0", "core-v1.2.0", "core-v1.3.0"])
    with pytest.raises(ValueError, match="no released acxelin-core"):
        check("qvpn", VERSION["qvpn"], tags=["core-v1.0.0", "core-v1.2.0", "core-v1.3.0"])
    with pytest.raises(ValueError, match="no released acxelin-core"):
        check("qguard", VERSION["qguard"], tags=[])
    with pytest.raises(ValueError, match="no released acxelin-core"):
        check("qreadiness", VERSION["qreadiness"], tags=["core-v2.0.0"])


def test_core_releases_need_no_core_tag():
    assert check("core", VERSION["core"], tags=[]) == f"acxelin-core {VERSION['core']}"
