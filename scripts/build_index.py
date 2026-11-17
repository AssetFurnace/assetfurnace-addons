#!/usr/bin/env python3
"""Combine every addons/*.json entry into one index.json, the file the studio reads.

Usage: build_index.py [--addons addons] [--out index.json]

Refuses to write anything if an entry fails its checks (offline checks only; the pinned
commit is verified by the pull request's own check). The output is sorted by id so the same
entries always give the same file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_entry import check_entry  # noqa: E402


def build_index(entries_dir: Path) -> tuple[list[dict], list[str]]:
    """The combined list and any problems found. Problems mean the list must not be published."""
    entries: list[dict] = []
    problems: list[str] = []
    for path in sorted(entries_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            problems.append(f"{path.name}: cannot read it: {exc}")
            continue
        found = check_entry(path, data)
        problems.extend(f"{path.name}: {problem}" for problem in found)
        if not found:
            entries.append(data)
    entries.sort(key=lambda entry: entry["id"])
    return entries, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--addons", type=Path, default=Path("addons"))
    parser.add_argument("--out", type=Path, default=Path("index.json"))
    args = parser.parse_args(argv)
    entries, problems = build_index(args.addons)
    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        return 1
    args.out.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out} with {len(entries)} add-on(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
