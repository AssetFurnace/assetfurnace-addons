#!/usr/bin/env python3
"""Make the ONE commit that carries a tested entry and the rebuilt index.json, on top of the checked pull request.

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


def make_commit(worktree: Path, trusted_addons: Path, entry: dict, message: str) -> str:
    """Write the entry and the index into worktree, commit both, return the new commit id."""
    entry_id = entry["id"]
    with tempfile.TemporaryDirectory() as tmp:
        merged = Path(tmp) / "addons"
        shutil.copytree(trusted_addons, merged)
        (merged / f"{entry_id}.json").write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
        entries, problems = build_index(merged)
    if problems:
        raise ValueError("; ".join(problems))
    (worktree / "addons").mkdir(exist_ok=True)
    (worktree / "addons" / f"{entry_id}.json").write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
    (worktree / "index.json").write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    git = ["git", "-C", str(worktree), "-c", "user.name=github-actions[bot]",
           "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com"]
    subprocess.run([*git, "add", f"addons/{entry_id}.json", "index.json"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", message], check=True)
    return subprocess.run([*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()


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
