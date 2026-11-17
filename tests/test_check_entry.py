import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_entry as ce  # noqa: E402

GOOD = {"id": "pedestal", "name": "Pedestal", "repo": "https://github.com/AssetFurnace/pedestal-addon.git",
        "commit": "a" * 40, "author": {"name": "X"}, "summary": "A stand."}


def test_good_entry_has_no_problems():
    assert ce.check_entry(Path("addons/pedestal.json"), GOOD) == []


def test_branch_instead_of_commit_is_refused():
    assert any("40-character" in p for p in ce.check_entry(Path("addons/pedestal.json"), {**GOOD, "commit": "main"}))


def test_file_name_must_match_id():
    assert any("named pedestal.json" in p for p in ce.check_entry(Path("addons/other.json"), GOOD))


def test_private_or_odd_hosts_are_refused():
    bad = {**GOOD, "repo": "http://example.com/x/y"}
    assert any("public https" in p for p in ce.check_entry(Path("addons/pedestal.json"), bad))


def test_missing_fields_are_named():
    assert "missing field: summary" in ce.check_entry(Path("addons/pedestal.json"), {**GOOD, "summary": ""})


def test_manifest_must_agree_with_entry():
    fetch = lambda url: json.dumps({"schema": 1, "id": "other", "licence": "MIT", "tools": [{}]})  # noqa: E731
    assert any("says id" in p for p in ce.check_manifest(GOOD, fetch=fetch))


def test_manifest_with_licence_and_tools_passes():
    fetch = lambda url: json.dumps({"schema": 1, "id": "pedestal", "licence": "MIT", "tools": [{}]})  # noqa: E731
    assert ce.check_manifest(GOOD, fetch=fetch) == []
