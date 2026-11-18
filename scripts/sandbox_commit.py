#!/usr/bin/env python3
"""Make the ONE commit that carries a tested entry and the rebuilt index.json, merged onto main and the checked pull request.

Usage: sandbox_commit.py --worktree DIR --trusted-addons DIR --entry NEW.json

DIR is a checkout of the pull request's checked commit (only read as data and committed to; nothing in it is run).
--trusted-addons is addons/ from main. The index is built from main's entries plus this one, so it is right
whatever the pull request's branch is based on. Then one commit is made: entry + index.json. Pushing is the caller's job.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_index import build_index  # noqa: E402


def _git(worktree: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(worktree), "-c", "user.name=github-actions[bot]",
                           "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com", *args],
                          check=check, capture_output=True, text=True)


def make_commit(worktree: Path, trusted_addons: Path, entry: dict, message: str, main_ref: str = "origin/main") -> str:
    """Commit entry + index.json in worktree as a MERGE of main into the checked commit; return the new commit id.

    Parents are the checked commit and main's head, so the squash merge into main is always clean even when main moved
    on since the pull request was opened (index.json changes with every merge). The index is built from main's entries
    plus this one; the picture is read from the merged tree. Nothing in worktree is run.
    """
    entry_id = entry["id"]
    _git(worktree, "merge", "--no-commit", "--no-ff", main_ref, check=False)   # a conflict is fine only in the two files we rewrite
    text = json.dumps(entry, indent=2) + "\n"
    with tempfile.TemporaryDirectory() as tmp:
        merged = Path(tmp) / "addons"
        shutil.copytree(trusted_addons, merged)
        (merged / f"{entry_id}.json").write_text(text, encoding="utf-8")
        if (worktree / "pictures").is_dir():
            shutil.copytree(worktree / "pictures", Path(tmp) / "pictures")
        entries, problems = build_index(merged)
    if problems:
        _git(worktree, "merge", "--abort", check=False)
        raise ValueError("; ".join(problems))
    (worktree / "addons").mkdir(exist_ok=True)
    (worktree / "addons" / f"{entry_id}.json").write_text(text, encoding="utf-8")
    (worktree / "index.json").write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    _git(worktree, "add", f"addons/{entry_id}.json", "index.json")
    if _git(worktree, "ls-files", "--unmerged").stdout.strip():
        _git(worktree, "merge", "--abort", check=False)
        raise ValueError("the pull request clashes with main in a file other than its own entry")
    _git(worktree, "commit", "-q", "-m", message)
    return _git(worktree, "rev-parse", "HEAD").stdout.strip()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--worktree", type=Path, required=True)
    p.add_argument("--trusted-addons", type=Path, required=True)
    p.add_argument("--entry", type=Path, required=True)
    args = p.parse_args(argv)
    entry = json.loads(args.entry.read_text(encoding="utf-8"))
    print(make_commit(args.worktree, args.trusted_addons, entry, f"Record the test run for {entry['id']}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
