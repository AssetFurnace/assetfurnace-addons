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


def test_runs_must_be_local_or_cloud():
    assert any("local or cloud" in p for p in ce.check_entry(Path("addons/pedestal.json"), {**GOOD, "runs": "moon"}))
    assert ce.check_entry(Path("addons/pedestal.json"), {**GOOD, "runs": "cloud"}) == []


def test_entry_and_addon_json_must_agree_on_runs():
    fetch = lambda url: json.dumps({"schema": 1, "id": "pedestal", "licence": "MIT", "tools": [{}], "runs": "cloud"})  # noqa: E731
    assert any("runs" in p for p in ce.check_manifest(GOOD, fetch=fetch))
    assert ce.check_manifest({**GOOD, "runs": "cloud"}, fetch=fetch) == []


def _repo_with_picture(tmp_path, name, content):
    (tmp_path / "addons").mkdir()
    (tmp_path / "pictures").mkdir()
    (tmp_path / "pictures" / name).write_bytes(content)
    return tmp_path / "addons" / "pedestal.json"


def test_picture_that_is_real_and_small_passes(tmp_path):
    entry = _repo_with_picture(tmp_path, "pedestal.jpg", b"\xff\xd8\xff" + b"0" * 100)
    assert ce.check_entry(entry, {**GOOD, "picture": "pictures/pedestal.jpg"}) == []


def test_picture_must_exist_be_small_real_and_named_after_the_add_on(tmp_path):
    entry = _repo_with_picture(tmp_path, "pedestal.png", b"not a png")
    assert any("not a real" in p for p in ce.check_entry(entry, {**GOOD, "picture": "pictures/pedestal.png"}))
    assert any("not in the pull request" in p for p in ce.check_entry(entry, {**GOOD, "picture": "pictures/pedestal.jpg"}))
    assert any("must be pictures/pedestal" in p for p in ce.check_entry(entry, {**GOOD, "picture": "pictures/other.png"}))


def test_picture_over_the_size_limit_is_refused(tmp_path):
    entry = _repo_with_picture(tmp_path, "pedestal.png", b"\x89PNG\r\n\x1a\n" + b"0" * 700_000)
    assert any("KB" in p for p in ce.check_entry(entry, {**GOOD, "picture": "pictures/pedestal.png"}))
