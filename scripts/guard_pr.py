#!/usr/bin/env python3
"""Decide what to do with a pull request on this list. Prints one line of JSON: {"action": ..., "message": ...}.

Actions: close (not from our bot), fail (entry or picture has a problem, tell the author), hold (a person has to
look; nothing is merged), merge (all checks passed, a plain Listed submission).

Only data is read from the pull request (json and pictures, copied into --head). No code from it is ever run.
Usage: guard_pr.py --author LOGIN --bots a,b --files "addons/x.json pictures/x.png" --labels "x,y" --head DIR [--offline]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_entry import check_entry, check_manifest  # noqa: E402

SUBMIT_URL = "https://assetfurnace.com/add-ons/submit"
ENTRY = re.compile(r"^addons/([a-z0-9][a-z0-9_-]*)\.json$")
PICTURE = re.compile(r"^pictures/([a-z0-9][a-z0-9_-]*)\.(png|jpg|jpeg)$")


def verdict(action: str, message: str) -> dict:
    return {"action": action, "message": message}


def read_json(path: Path):
    if path.is_symlink() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def judge(author: str, bots: list[str], files: list[str], labels: list[str], head: Path, main: Path,
          offline: bool = False, fetch=None) -> dict:
    """What to do with one pull request. `head` holds the pull request's addons/ and pictures/; `main` is this repo's main."""
    if not bots:
        return verdict("hold", "The list of accepted submitters is not set up yet, so nothing is closed or merged.")
    if author.lower() not in {b.lower() for b in bots}:
        return verdict("close", f"Thanks for the interest! Add-ons are submitted at {SUBMIT_URL} (sign in with GitHub, send your repo link and version). Pull requests made directly here are closed automatically.")

    entries = [f for f in files if ENTRY.match(f)]
    pictures = [f for f in files if PICTURE.match(f)]
    others = [f for f in files if f not in entries and f not in pictures]
    if others or len(entries) != 1 or len(pictures) > 1:
        return verdict("hold", "This pull request changes more than one add-on's entry and picture, so a person has to look at it.")
    addon_id = ENTRY.match(entries[0]).group(1)
    if pictures and PICTURE.match(pictures[0]).group(1) != addon_id:
        return verdict("hold", "The picture is not named after the add-on, so a person has to look at it.")

    if any(path.is_symlink() for path in head.rglob("*")):
        return verdict("fail", "Links between files are not allowed in a submission.")
    entry = read_json(head / entries[0])
    if not isinstance(entry, dict):
        return verdict("fail", "The entry file is missing or is not valid JSON.")
    problems = check_entry(head / entries[0], entry)
    if not problems and not offline:
        problems = check_manifest(entry, fetch)
    if problems:
        return verdict("fail", "These need fixing:\n" + "\n".join(f"- {p}" for p in problems))

    by = entry.get("submitted_by")
    if not (isinstance(by, dict) and by.get("github_id") and by.get("github_login")):
        return verdict("hold", "No submitter is recorded in this entry (it did not come from the site), so a person has to look at it.")
    if entry.get("tier", "listed") != "listed":
        return verdict("hold", "Only we set Verified, so a person has to look at this entry.")

    before = read_json(main / entries[0])
    if isinstance(before, dict):
        was = before.get("submitted_by") or {}
        if str(was.get("github_id")) != str(by.get("github_id")):
            return verdict("hold", f"The name {addon_id} already belongs to someone else, so a person has to look at this entry.")
        if before.get("tier") == "verified":
            return verdict("hold", "This is a new version of a Verified add-on. It stays on the old version until we have read the new one.")
    if "verify-request" in labels:
        return verdict("hold", "The author asked for a Verified review. It waits for one, and is not merged until then.")
    return verdict("merge", "Checks passed. Merging, so it is Listed.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--author", required=True)
    p.add_argument("--bots", default="")
    p.add_argument("--files", default="")
    p.add_argument("--labels", default="")
    p.add_argument("--head", type=Path, required=True)
    p.add_argument("--main", type=Path, default=Path("."))
    p.add_argument("--offline", action="store_true")
    a = p.parse_args(argv)
    split = lambda s: [x for x in re.split(r"[,\s]+", s) if x]  # noqa: E731
    print(json.dumps(judge(a.author, split(a.bots), split(a.files), split(a.labels), a.head, a.main, a.offline)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
