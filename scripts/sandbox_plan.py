#!/usr/bin/env python3
"""Work out how to test-run an add-on on a throwaway machine. Trusted: reads the entry and the add-on's addon.json only.

Usage: sandbox_plan.py ENTRY.json [--manifest addon.json]   (without --manifest it is fetched at the pinned commit)
Prints the plan as JSON: {"runnable": bool, "reason": ..., "id", "repo", "commit", "blender", "runs": [{"tool", "inputs"}]}.

An add-on we cannot run there (downloads models, needs a picture or model file as input, needs a newer Blender than
the test machine has, makes something other than a .glb) is not an error: it is marked not runnable with the reason,
and is listed as "not run-checked". A tool that needs a file as input is left out of the run and named in "skipped";
the rest are still tested, and the result is "partial". Only when no tool can be run is the add-on "not run-checked".
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_entry import manifest_url  # noqa: E402

BLENDER = "4.2"                 # the version installed on the test machine (see .github/workflows/sandbox.yml)
MAX_TOOLS = 5
NEEDS_VERSION = re.compile(r"^\s*>=\s*(\d+)\.(\d+)")


def sample_value(spec: dict) -> str | None:
    """A plain test value for one input, or None when it cannot be given one (a file)."""
    kind = spec.get("type")
    if kind == "text":
        return "test"
    if kind == "toggle":
        return "false"
    if kind == "choice":
        choices = spec.get("choices") or []
        return str(choices[0]) if choices else None
    if kind == "number":
        lo, hi = spec.get("min"), spec.get("max")
        if isinstance(lo, int) and isinstance(hi, int) and not isinstance(lo, bool) and not isinstance(hi, bool):
            mid = (lo + hi) // 2          # a whole-number range gets a whole number
        elif isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
            mid = (lo + hi) / 2
        elif isinstance(lo, (int, float)):
            mid = lo
        elif isinstance(hi, (int, float)):
            mid = hi
        else:
            mid = 1
        return str(int(mid)) if float(mid).is_integer() else repr(round(float(mid), 4))
    return None


def not_runnable(entry: dict, reason: str) -> dict:
    return {"runnable": False, "reason": reason, "id": entry.get("id"), "repo": entry.get("repo"),
            "commit": entry.get("commit"), "blender": None, "runs": []}


def make_plan(entry: dict, manifest: dict) -> dict:
    """The plan for one entry and its addon.json. Pure: no network, nothing run."""
    if not isinstance(manifest, dict):
        return not_runnable(entry, "its addon.json is not a JSON object")
    if manifest.get("models"):
        return not_runnable(entry, "it downloads models, which a throwaway machine cannot do")
    tools = manifest.get("tools") or []
    if not isinstance(tools, list) or not all(isinstance(t, dict) for t in tools) or not tools:
        return not_runnable(entry, "it lists no tools")
    uses_blender = bool((manifest.get("needs") or {}).get("blender")) or any("{blender}" in (t.get("run") or []) for t in tools)
    if uses_blender:
        match = NEEDS_VERSION.match(str((manifest.get("needs") or {}).get("blender", "")))
        if match and (int(match[1]), int(match[2])) > tuple(int(x) for x in BLENDER.split(".")):
            return not_runnable(entry, f"it needs a newer Blender than the test machine's {BLENDER}")
    runs = []
    skipped = []          # tools that were not run (they need a file as input, or are past the limit): named in the result
    file_reason = ""
    names = [str(t.get("id") or "(unnamed)") for t in tools]
    skipped.extend(names[MAX_TOOLS:])      # past the limit: not run, and said so
    for tool, name in zip(tools[:MAX_TOOLS], names):
        inputs = {}
        needs_file = False
        for spec in tool.get("inputs") or []:
            value = sample_value(spec)
            if value is None:
                if spec.get("optional"):
                    continue
                needs_file = True
                break
            inputs[str(spec.get("id"))] = value
        if needs_file:
            skipped.append(name)
            file_reason = file_reason or f"the tool {name} needs a file as input, which we cannot give it"
            continue
        if tool.get("makes") != "glb":
            return not_runnable(entry, f"the tool {name} makes a .{tool.get('makes')}, and only .glb can be checked so far")
        runs.append({"tool": name, "inputs": inputs})
    if not runs:
        return not_runnable(entry, file_reason or "it lists no tools")
    return {"runnable": True, "reason": "", "id": entry.get("id"), "repo": entry.get("repo"), "commit": entry.get("commit"),
            "blender": BLENDER if uses_blender else None, "runs": runs, "skipped": skipped}


def fetch_manifest(entry: dict) -> dict:
    url = manifest_url(str(entry["repo"]), str(entry["commit"]))
    if url is None:
        raise ValueError("only GitHub repos can be test-run")
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("entry", type=Path)
    p.add_argument("--manifest", type=Path)
    a = p.parse_args(argv)
    entry = json.loads(a.entry.read_text(encoding="utf-8"))
    try:
        manifest = json.loads(a.manifest.read_text(encoding="utf-8")) if a.manifest else fetch_manifest(entry)
        plan = make_plan(entry, manifest)
    except (OSError, ValueError) as exc:
        plan = not_runnable(entry, f"its addon.json could not be read: {exc}")
    print(json.dumps(plan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
