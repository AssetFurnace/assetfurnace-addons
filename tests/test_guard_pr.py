import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import guard_pr as gp  # noqa: E402

BY = {"github_login": "ann", "github_id": "99"}
ENTRY = {"id": "cool", "name": "Cool", "repo": "https://github.com/ann/cool.git", "commit": "a" * 40,
         "author": {"name": "Ann"}, "summary": "A thing.", "tier": "listed", "runs": "local",
         "picture": "pictures/cool.png", "submitted_by": BY}
FILES = ["addons/cool.json", "pictures/cool.png"]


def tree(root: Path, entry=ENTRY, picture=True):
    (root / "addons").mkdir(parents=True, exist_ok=True)
    (root / "pictures").mkdir(exist_ok=True)
    if entry is not None:
        (root / "addons" / "cool.json").write_text(json.dumps(entry))
    if picture:
        (root / "pictures" / "cool.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 20)
    return root


def run(tmp_path, entry=ENTRY, files=FILES, author="the-bot", bots=("the-bot",), labels=(), main_entry=None, **kw):
    head = tree(tmp_path / "head", entry)
    main = tmp_path / "main"
    (main / "addons").mkdir(parents=True, exist_ok=True)
    if main_entry is not None:
        (main / "addons" / "cool.json").write_text(json.dumps(main_entry))
    kw.setdefault("offline", True)
    return gp.judge(author, list(bots), files, list(labels), head, main, **kw)


def test_a_clean_listed_submission_from_the_bot_is_merged(tmp_path):
    assert run(tmp_path)["action"] == "merge"


def test_anyone_else_is_closed_with_the_submit_link(tmp_path):
    v = run(tmp_path, author="stranger")
    assert v["action"] == "close" and "assetfurnace.com/add-ons/submit" in v["message"]


def test_author_name_match_ignores_case(tmp_path):
    assert run(tmp_path, author="The-Bot")["action"] == "merge"


def test_nothing_is_closed_or_merged_until_the_submitters_are_set(tmp_path):
    assert run(tmp_path, bots=())["action"] == "hold"


def test_other_files_or_several_add_ons_need_a_person(tmp_path):
    assert run(tmp_path, files=FILES + [".github/workflows/check.yml"])["action"] == "hold"
    assert run(tmp_path, files=FILES + ["addons/other.json"])["action"] == "hold"
    assert run(tmp_path, files=["pictures/cool.png"])["action"] == "hold"


def test_a_bad_entry_fails_with_a_plain_list(tmp_path):
    v = run(tmp_path, entry={**ENTRY, "commit": "main"})
    assert v["action"] == "fail" and "40-character" in v["message"]


def test_a_bad_picture_fails(tmp_path):
    head = tree(tmp_path / "head")
    (head / "pictures" / "cool.png").write_bytes(b"not a picture")
    main = tmp_path / "main"
    main.mkdir()
    v = gp.judge("the-bot", ["the-bot"], FILES, [], head, main, offline=True)
    assert v["action"] == "fail" and "real PNG" in v["message"]


def test_no_recorded_submitter_means_a_person_looks(tmp_path):
    e = {k: v for k, v in ENTRY.items() if k != "submitted_by"}
    assert run(tmp_path, entry=e)["action"] == "hold"


def test_verified_is_never_set_by_a_submission(tmp_path):
    assert run(tmp_path, entry={**ENTRY, "tier": "verified"})["action"] == "hold"


def test_someone_elses_id_is_not_overwritten(tmp_path):
    other = {**ENTRY, "submitted_by": {"github_login": "bob", "github_id": "5"}}
    assert run(tmp_path, main_entry=other)["action"] == "hold"


def test_the_same_person_can_send_a_new_version(tmp_path):
    assert run(tmp_path, main_entry={**ENTRY, "commit": "b" * 40})["action"] == "merge"


def test_a_new_version_of_a_verified_add_on_waits(tmp_path):
    assert run(tmp_path, main_entry={**ENTRY, "tier": "verified"})["action"] == "hold"


def test_a_verified_request_waits(tmp_path):
    assert run(tmp_path, labels=["verify-request"])["action"] == "hold"


def test_a_symlinked_entry_is_not_read(tmp_path):
    head = tree(tmp_path / "head", entry=None)
    secret = tmp_path / "secret.json"
    secret.write_text(json.dumps(ENTRY))
    (head / "addons" / "cool.json").symlink_to(secret)
    main = tmp_path / "main"
    main.mkdir()
    assert gp.judge("the-bot", ["the-bot"], FILES, [], head, main, offline=True)["action"] == "fail"


def test_the_manifest_check_runs_online(tmp_path):
    v = run(tmp_path, offline=False, fetch=lambda url: json.dumps({"schema": 1, "id": "other", "licence": "MIT", "tools": [{}]}))
    assert v["action"] == "fail" and "addon.json says id" in v["message"]
