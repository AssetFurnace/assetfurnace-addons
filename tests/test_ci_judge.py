"""Drive the real scripts/ci_judge.sh with a fake `gh` and a real git repo, the way the workflows do."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not (shutil.which("jq") and shutil.which("bash") and shutil.which("git")), reason="needs jq, bash and git")

BY = {"github_login": "ann", "github_id": "99"}


def entry(i):
    return {"id": i, "name": i.title(), "repo": f"https://github.com/ann/{i}.git", "commit": "a" * 40, "author": {"name": "Ann"},
            "summary": "s", "tier": "listed", "runs": "local", "picture": f"pictures/{i}.png", "submitted_by": BY}


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}).stdout.strip()


def world(tmp_path, changed=("cool",), existing=("aaa",), files_json=None):
    """origin holds main (with `existing` entries) and refs/pull/7/head (main plus the `changed` entries); work is a checkout of main."""
    origin = tmp_path / "origin"
    origin.mkdir()
    git(origin, "init", "-q", "-b", "main")
    for d in ("addons", "pictures"):
        (origin / d).mkdir()
    for i in existing:
        (origin / "addons" / f"{i}.json").write_text(json.dumps({**entry(i), "submitted_by": {"github_login": "bob", "github_id": "5"}}))
        (origin / "pictures" / f"{i}.png").write_bytes(b"\x89PNG\r\n\x1a\n0000")
    git(origin, "add", "-A")
    git(origin, "commit", "-qm", "main")
    git(origin, "checkout", "-q", "-b", "pr")
    for i in changed:
        (origin / "addons" / f"{i}.json").write_text(json.dumps(entry(i)))
        (origin / "pictures" / f"{i}.png").write_bytes(b"\x89PNG\r\n\x1a\n0000")
    git(origin, "add", "-A")
    git(origin, "commit", "-qm", "pr")
    sha = git(origin, "rev-parse", "HEAD")
    git(origin, "update-ref", "refs/pull/7/head", sha)
    git(origin, "checkout", "-q", "main")
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    shutil.copytree(ROOT / "scripts", work / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    files = files_json or [{"filename": f"addons/{i}.json"} for i in changed] + [{"filename": f"pictures/{i}.png"} for i in changed]
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "gh").write_text(f"""#!/usr/bin/env bash
case "$*" in
  api*) echo '{json.dumps(files)}' | jq -r '.[] | .filename, (.previous_filename // empty)';;
  *isCrossRepository*) echo false;;
  *) echo "unexpected gh call: $*" >&2; exit 9;;
esac
""")
    (bindir / "gh").chmod(0o755)
    (bindir / "python").write_text(f'#!/usr/bin/env bash\nexec "{sys.executable}" "$@"\n')
    (bindir / "python").chmod(0o755)
    return work, bindir, sha


def judge(tmp_path, expect=None, **kw):
    work, bindir, sha = world(tmp_path, **kw)
    temp = tmp_path / "tmp"
    temp.mkdir()
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "RUNNER_TEMP": str(temp), "GITHUB_REPOSITORY": "AssetFurnace/assetfurnace-addons", "BOT_LOGINS": "the-bot", "GUARD_OFFLINE": "1"}
    args = ["bash", "scripts/ci_judge.sh", "7", "the-bot"] + ([sha if expect is True else expect] if expect else [])
    done = subprocess.run(args, cwd=work, env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return json.loads((temp / "verdict.json").read_text())


def test_the_add_on_named_is_the_one_the_pull_request_changed_not_the_first_in_the_folder(tmp_path):
    v = judge(tmp_path, existing=("aaa",), changed=("cool",))     # aaa sorts first, and git archive copies it too
    assert v["action"] == "merge" and v["id"] == "cool"


def test_a_pull_request_that_moved_since_it_was_checked_waits(tmp_path):
    v = judge(tmp_path, expect="0" * 40)
    assert v["action"] == "hold" and "changed after" in v["message"]


def test_the_expected_commit_passes_when_it_is_the_one(tmp_path):
    assert judge(tmp_path, expect=True)["action"] == "merge"


def test_a_rename_that_deletes_someone_elses_entry_waits(tmp_path):
    files = [{"filename": "addons/cool.json", "previous_filename": "addons/aaa.json"}, {"filename": "pictures/cool.png"}]
    assert judge(tmp_path, files_json=files)["action"] == "hold"
