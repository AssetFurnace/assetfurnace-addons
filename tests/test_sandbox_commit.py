import json
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


def make_pr_checkout(tmp_path):
    """A real git checkout standing in for the pull request's checked commit (it lacks entries main has gained since)."""
    repo = tmp_path / "pr"
    (repo / "addons").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "addons" / "old.json").write_text(json.dumps(entry("old")), encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    return repo


def test_one_commit_with_entry_and_index_sits_directly_on_the_checked_one(tmp_path):
    repo = make_pr_checkout(tmp_path)
    checked = git(repo, "rev-parse", "HEAD")
    main_addons = tmp_path / "main_addons"
    main_addons.mkdir()
    (main_addons / "old.json").write_text(json.dumps(entry("old")), encoding="utf-8")
    (main_addons / "newer.json").write_text(json.dumps(entry("newer")), encoding="utf-8")  # merged to main after the PR was opened
    new = sc.make_commit(repo, main_addons, entry("mine"), "Record")
    assert git(repo, "rev-list", "--parents", "-n1", new).split() == [new, checked]
    assert sorted(git(repo, "show", "--name-only", "--format=", new).split()) == ["addons/mine.json", "index.json"]
    ids = [e["id"] for e in json.loads((repo / "index.json").read_text())]
    assert ids == ["mine", "newer", "old"]  # main's entries plus this one, not the pull request's stale view


def test_a_bad_entry_makes_no_commit(tmp_path):
    repo = make_pr_checkout(tmp_path)
    before = git(repo, "rev-parse", "HEAD")
    main_addons = tmp_path / "main_addons"
    main_addons.mkdir()
    with pytest.raises(ValueError):
        sc.make_commit(repo, main_addons, entry("bad", commit="main"), "Record")
    assert git(repo, "rev-parse", "HEAD") == before
    assert not (repo / "index.json").exists()


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
