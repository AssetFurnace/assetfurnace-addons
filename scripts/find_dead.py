#!/usr/bin/env python3
"""Find list entries whose add-on can no longer be loaded: the repo is gone, private, or the pinned commit vanished.

Usage: find_dead.py [--addons addons] [--report report.md]

Prints one line per dead entry and writes a plain-words report. Exit code 0 always: this only reports.
A removal is a person's decision. A busy or unreachable server (anything but a clear "not found") is never
counted as dead, so a GitHub hiccup cannot get an add-on flagged.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_entry import manifest_url  # noqa: E402


def status_of(url: str) -> int | None:
    """HTTP status of a GET, or None if the server could not be reached at all."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "assetfurnace-addons"}), timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def find_dead(entries: list[dict], status=status_of, tries: int = 2, wait: float = 5.0, sleep=time.sleep) -> list[dict]:
    """Entries that clearly answered 'not found' on every one of `tries` attempts (spaced out). Others are left alone."""
    dead = []
    for entry in entries:
        url = manifest_url(str(entry.get("repo", "")), str(entry.get("commit", "")))
        if url is None:
            continue  # not a GitHub repo: cannot be checked here
        answers = []
        for attempt in range(tries):
            if attempt:
                sleep(wait)
            answers.append(status(url))
        if all(a == 404 for a in answers):
            dead.append({"id": entry.get("id"), "repo": entry.get("repo"), "commit": entry.get("commit"),
                         "reason": "the repo or the pinned version cannot be found any more (deleted, made private, or the history was rewritten)"})
    return dead


def report(dead: list[dict]) -> str:
    lines = ["These list entries can no longer be loaded. If it stays this way, remove the entry (a person decides).", ""]
    for d in dead:
        lines.append(f"- **{d['id']}**: {d['reason']}. Repo {d['repo']}, version `{str(d['commit'])[:7]}`.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--addons", type=Path, default=Path("addons"))
    p.add_argument("--report", type=Path, default=Path("dead-report.md"))
    a = p.parse_args(argv)
    entries = []
    for path in sorted(a.addons.glob("*.json")):
        try:
            entries.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    dead = find_dead(entries)
    for d in dead:
        print(f"DEAD {d['id']}")
    if dead:
        a.report.write_text(report(dead), encoding="utf-8")
    print(f"{len(entries)} checked, {len(dead)} dead")
    return 0


if __name__ == "__main__":
    sys.exit(main())
