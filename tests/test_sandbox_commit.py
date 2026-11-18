import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sandbox_commit as sc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def entry(addon_id, **extra):
    return {"id": addon_id, "name": addon_id.title(), "repo": "https://github.com/AssetFurnace/x.git",
            "commit": "a" * 40, "author": {"name": "X"}, "summary": "A thing.", **extra}


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          check=True, capture_output=True, text=True).stdout.strip()


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


def make_world(tmp_path):
    """A repo whose `main` has moved on (entry `newer`, a new index) since the pull request branched off it."""
    repo = tmp_path / "pr"
    (repo / "addons").mkdir(parents=True)
    (repo / "pictures").mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    (repo / "addons" / "old.json").write_text(json.dumps(entry("old")), encoding="utf-8")
    (repo / "index.json").write_text(json.dumps([entry("old")]), encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "checkout", "-q", "-b", "pr")
    (repo / "addons" / "mine.json").write_text(json.dumps(entry("mine", picture="pictures/mine.png")), encoding="utf-8")
    (repo / "pictures" / "mine.png").write_bytes(PNG)
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "the pull request")
    checked = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "main")
    (repo / "pictures").mkdir(exist_ok=True)
    (repo / "addons" / "newer.json").write_text(json.dumps(entry("newer", picture="pictures/newer.png")), encoding="utf-8")
    (repo / "pictures" / "newer.png").write_bytes(PNG)
    (repo / "index.json").write_text(json.dumps([entry("newer"), entry("old")]), encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "main moved on")
    main_head = git(repo, "rev-parse", "HEAD")
    main_addons = tmp_path / "main_addons"
    shutil.copytree(repo / "addons", main_addons)
    git(repo, "checkout", "-q", "--detach", checked)
    return repo, checked, main_head, main_addons


def test_merge_commit_with_entry_picture_and_index_even_though_main_moved(tmp_path):
    repo, checked, main_head, main_addons = make_world(tmp_path)
    mine = {**json.loads((repo / "addons" / "mine.json").read_text())}
    new = sc.make_commit(repo, main_addons, mine, "Record", main_ref="main")
    assert git(repo, "rev-list", "--parents", "-n1", new).split() == [new, checked, main_head]
    ids = [e["id"] for e in json.loads((repo / "index.json").read_text())]
    assert ids == ["mine", "newer", "old"]
    # squashing it into main is clean: its base IS main, so only our entry and picture differ
    tree_diff = git(repo, "diff", "--name-only", main_head, new).split()
    assert sorted(tree_diff) == ["addons/mine.json", "index.json", "pictures/mine.png"]


def test_a_clash_in_another_file_makes_no_commit(tmp_path):
    repo, checked, main_head, main_addons = make_world(tmp_path)
    git(repo, "checkout", "-q", "pr")
    (repo / "addons" / "old.json").write_text(json.dumps(entry("old", summary="Changed by the PR.")), encoding="utf-8")
    git(repo, "commit", "-qam", "touches an entry that is not its own")
    checked = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "main")
    (repo / "addons" / "old.json").write_text(json.dumps(entry("old", summary="Changed on main.")), encoding="utf-8")
    git(repo, "commit", "-qam", "main changed it too")
    shutil.rmtree(main_addons)
    shutil.copytree(repo / "addons", main_addons)
    git(repo, "checkout", "-q", "--detach", checked)
    mine = json.loads((repo / "addons" / "mine.json").read_text())
    with pytest.raises(ValueError):
        sc.make_commit(repo, main_addons, mine, "Record", main_ref="main")
    assert git(repo, "rev-parse", "HEAD") == checked
    assert git(repo, "status", "--porcelain") == ""


def test_a_bad_entry_makes_no_commit(tmp_path):
    repo, checked, main_head, main_addons = make_world(tmp_path)
    with pytest.raises(ValueError):
        sc.make_commit(repo, main_addons, entry("bad", commit="main"), "Record", main_ref="main")
    assert git(repo, "rev-parse", "HEAD") == checked
    assert git(repo, "status", "--porcelain") == ""


# ---- the workflows themselves (the parts that cannot be run here are at least checked for their locks)

def workflow(name):
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_every_sandbox_job_refuses_to_run_off_main_and_checks_out_main():
    text = workflow("sandbox.yml")
    assert text.count("refs/heads/main") >= 3          # prepare, run, decide each check it
    assert "ref: main" in text


def test_the_decided_mark_is_posted_before_the_merge():
    text = workflow("sandbox.yml")
    assert text.index("addons/decided") < text.index("gh pr merge")
    assert "checks: write" in text
    assert "publish-index" not in text


def test_nothing_pushes_to_main_directly_any_more():
    assert not (ROOT / ".github" / "workflows" / "publish-index.yml").exists()
    for name in ("check.yml", "guard.yml", "sandbox.yml"):
        assert "git push origin HEAD:main" not in workflow(name)


def test_check_yml_is_read_only():
    assert "permissions:\n  contents: read" in workflow("check.yml")


def test_a_cancelled_decide_run_is_started_again():
    text = workflow("sandbox.yml")
    assert "needs.decide.result == 'cancelled'" in text
    assert "fetch-depth: 0" in text            # main is merged into the pull request, which needs history
    assert text.count("refs/heads/main") >= 4   # prepare, run, decide and retry all refuse to run off main
