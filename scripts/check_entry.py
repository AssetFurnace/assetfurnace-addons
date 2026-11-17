#!/usr/bin/env python3
"""Check add-on list entries. Usage: check_entry.py [--offline] addons/*.json

Offline checks the entry file itself. Online (the default) also fetches addon.json at the
pinned commit from GitHub and checks it agrees with the entry. Exit code 1 if anything fails.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
REPO_RE = re.compile(r"^https://(github\.com|gitlab\.com)/([\w.-]+)/([\w.-]+?)(\.git)?$")
REQUIRED = ("id", "name", "repo", "commit", "author", "summary")
TIERS = {"listed", "verified"}
TYPES = {"tool", "app"}
RUNS = {"local", "cloud"}


def check_entry(path: Path, data: object) -> list[str]:
    """Problems with one entry file, as plain sentences. Empty means fine."""
    if not isinstance(data, dict):
        return ["the file must hold one JSON object"]
    problems = [f"missing field: {key}" for key in REQUIRED if not data.get(key)]
    addon_id = str(data.get("id", ""))
    if addon_id and not ID_RE.match(addon_id):
        problems.append("id may only use lowercase letters, numbers, - and _")
    if addon_id and path.stem != addon_id:
        problems.append(f"the file must be named {addon_id}.json")
    if data.get("commit") and not COMMIT_RE.match(str(data["commit"])):
        problems.append("commit must be the full 40-character version code, not a branch or tag")
    if data.get("repo") and not REPO_RE.match(str(data["repo"])):
        problems.append("repo must be a public https link on github.com or gitlab.com")
    author = data.get("author")
    if author is not None and not (isinstance(author, dict) and author.get("name")):
        problems.append("author needs at least a name")
    if data.get("tier", "listed") not in TIERS:
        problems.append("tier must be listed or verified")
    if data.get("type", "tool") not in TYPES:
        problems.append("type must be tool or app")
    if data.get("runs", "local") not in RUNS:
        problems.append("runs must be local or cloud")
    return problems


def manifest_url(repo: str, commit: str) -> str | None:
    match = REPO_RE.match(repo)
    if not match or match.group(1) != "github.com":
        return None
    return f"https://raw.githubusercontent.com/{match.group(2)}/{match.group(3)}/{commit}/addon.json"


def check_manifest(data: dict, fetch=None) -> list[str]:
    """Check the add-on's own addon.json, at the pinned commit, agrees with the entry."""
    url = manifest_url(str(data["repo"]), str(data["commit"]))
    if url is None:
        return ["only GitHub repos can be checked automatically for now"]
    fetch = fetch or (lambda u: urllib.request.urlopen(u, timeout=30).read().decode("utf-8"))
    try:
        manifest = json.loads(fetch(url))
    except (urllib.error.URLError, ValueError) as exc:
        return [f"could not read addon.json at that commit: {exc}"]
    problems = []
    if manifest.get("schema") != 1:
        problems.append("addon.json must have schema 1")
    if manifest.get("id") != data["id"]:
        problems.append(f"addon.json says id {manifest.get('id')!r}, the entry says {data['id']!r}")
    if not manifest.get("licence"):
        problems.append("addon.json must name a licence")
    if manifest.get("runs", "local") != data.get("runs", "local"):
        problems.append(
            f"addon.json says runs {manifest.get('runs', 'local')!r}, the entry says {data.get('runs', 'local')!r}"
        )
    if not manifest.get("tools"):
        problems.append("addon.json must list at least one tool")
    return problems


def main(argv: list[str]) -> int:
    offline = "--offline" in argv
    files = [Path(a) for a in argv if not a.startswith("--")]
    failed = False
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"FAIL {path}: cannot read it: {exc}")
            failed = True
            continue
        problems = check_entry(path, data)
        if not problems and not offline:
            problems = check_manifest(data)
        for problem in problems:
            print(f"FAIL {path}: {problem}")
        failed = failed or bool(problems)
        if not problems:
            print(f"ok   {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
