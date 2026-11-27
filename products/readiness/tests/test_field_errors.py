"""Each refusal of the tracking form names the field it is about with the label the form shows, so the page can put it next to that
field (R6)."""
import pytest

from acxelin_readiness import workspace

LABELS = ("Owner", "Due date", "Status", "Why it is accepted", "Accepted until")


@pytest.fixture
def store(tmp_path):
    (tmp_path / "shop").mkdir()
    (tmp_path / "shop/k.py").write_text("import hashlib\nhashlib.md5(b'x')\n")
    s = workspace.ProjectStore(tmp_path / "w.json")
    saved = s.save(tmp_path / "shop", workspace.scan(tmp_path / "shop"))
    return s, tmp_path / "shop", saved["assets"][0]["id"]


@pytest.mark.parametrize("fields,label", [
    ({"owner": "x" * 121}, "Owner"),
    ({"due": "soon"}, "Due date"),
    ({"due": "2027-13-45"}, "Due date"),
    ({"status": "done"}, "Status"),
    ({"status": "exception", "reason": "", "until": "2099-01-01"}, "Why it is accepted"),
    ({"status": "exception", "reason": "x" * 1001, "until": "2099-01-01"}, "Why it is accepted"),
    ({"status": "exception", "reason": "Vendor appliance", "until": ""}, "Accepted until"),
    ({"status": "exception", "reason": "Vendor appliance", "until": "2001-01-01"}, "Accepted until"),
    ({"status": "exception", "reason": "Vendor appliance", "until": "31/12/2099"}, "Accepted until"),
])
def test_each_refusal_starts_with_the_label_of_its_field(store, fields, label):
    s, root, finding = store
    body = {"finding": finding, "owner": "", "due": "", "status": "open", "reason": "", "until": ""} | fields
    with pytest.raises(ValueError) as e:
        s.track(root, body)
    assert str(e.value).startswith(label + ": "), str(e.value)
    assert "rationale" not in str(e.value) and "exception" not in str(e.value).split(": ", 1)[1].split(" (")[0], "the form's words, not the API's"
