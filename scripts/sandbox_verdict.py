#!/usr/bin/env python3
"""Judge what the sandbox produced. TRUSTED: runs in a separate job, reads only data, never runs anything from the add-on.

Usage: sandbox_verdict.py PLAN.json RESULT_DIR      prints {"status": "passed"|"partial"|"failed"|"not_run", "reason", "problems": [...]}

Never believes the sandbox's own claims beyond "what files came out": every .glb is parsed here, byte by byte.
Statuses: passed = it installed, every tool ran and made a real model; partial = the same for the tools we could run, and the
ones we could not run (they need a file as input, or are past the tool limit) are named in "skipped"; failed = it did not (the author is told why);
not_run = we could not test it on a throwaway machine (the plan said so), so it is listed as "not run-checked".
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

GLB_MAX_BYTES = 50_000_000
RUN_FILE_MAX = 1_000_000
MAX_SKIPPED = 20
MAGIC = b"glTF"


def check_glb(data: bytes) -> list[str]:
    """Problems with a .glb file, as plain sentences. Empty means it is a real model with something in it."""
    if len(data) > GLB_MAX_BYTES:
        return [f"the model is {len(data) // 1_000_000} MB; keep it under {GLB_MAX_BYTES // 1_000_000} MB"]
    if len(data) < 20 or data[:4] != MAGIC:
        return ["the file is not a real .glb model"]
    version, length = struct.unpack_from("<II", data, 4)
    if version != 2 or length != len(data):
        return ["the .glb header is wrong (version or length)"]
    chunk_len, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != 0x4E4F534A or 20 + chunk_len > len(data):
        return ["the .glb has no readable description chunk"]
    try:
        gltf = json.loads(data[20:20 + chunk_len].decode("utf-8"))
    except ValueError:
        return ["the .glb description is not valid"]
    accessors = gltf.get("accessors") or []
    triangles = 0
    for mesh in gltf.get("meshes") or []:
        for prim in mesh.get("primitives") or []:
            idx = prim.get("indices")
            pos = (prim.get("attributes") or {}).get("POSITION")
            ref = idx if idx is not None else pos
            if isinstance(ref, int) and 0 <= ref < len(accessors):
                count = accessors[ref].get("count", 0)
                triangles += count // 3
    if triangles < 1:
        return ["the model is empty: no triangles"]
    return []


def read_run(path: Path) -> dict | None:
    """The sandbox's run.json, strictly: only the fields and types we expect, anything else is thrown away."""
    try:
        if path.stat().st_size > RUN_FILE_MAX:
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get("install_exit"), int) or not isinstance(raw.get("runs"), list):
        return None
    runs = []
    for r in raw["runs"][:10]:
        if not (isinstance(r, dict) and isinstance(r.get("tool"), str) and isinstance(r.get("exit"), int) and isinstance(r.get("files"), list)):
            return None
        files = [f for f in r["files"][:3] if isinstance(f, str) and f.startswith("run") and f.endswith(".glb") and "/" not in f and "\\" not in f]
        runs.append({"tool": r["tool"][:60], "exit": r["exit"], "files": files})
    return {"install_exit": raw["install_exit"], "runs": runs}


def judge(plan: dict, result_dir: Path) -> dict:
    if not plan.get("runnable"):
        return {"status": "not_run", "reason": str(plan.get("reason", "")), "problems": []}
    run = read_run(result_dir / "run.json")
    if run is None:
        return {"status": "failed", "reason": "", "problems": ["the test machine did not report back, so the add-on could not be checked"]}
    if run["install_exit"] != 0:
        return {"status": "failed", "reason": "", "problems": ["it did not install: its setup step failed or ran out of time"]}
    planned = [r["tool"] for r in plan["runs"]]
    if [r["tool"] for r in run["runs"]] != planned:
        return {"status": "failed", "reason": "", "problems": ["not every tool was run (it may have run out of time)"]}
    problems = []
    for r in run["runs"]:
        if r["exit"] != 0:
            problems.append(f"the tool {r['tool']} failed or ran out of time")
            continue
        if not r["files"]:
            problems.append(f"the tool {r['tool']} ran but made no .glb model")
            continue
        for name in r["files"]:
            path = result_dir / name
            if path.is_symlink() or not path.is_file():
                problems.append(f"the tool {r['tool']} made no readable model")
                continue
            if path.stat().st_size > GLB_MAX_BYTES:
                problems.append(f"the tool {r['tool']}: the model is over {GLB_MAX_BYTES // 1_000_000} MB")
                continue
            problems.extend(f"the tool {r['tool']}: {p}" for p in check_glb(path.read_bytes()))
    if problems:
        return {"status": "failed", "reason": "", "problems": problems}
    if plan.get("skipped"):
        return {"status": "partial", "reason": "", "problems": [], "skipped": [str(t)[:60] for t in plan["skipped"]][:MAX_SKIPPED]}
    return {"status": "passed", "reason": "", "problems": []}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(__doc__)
        return 2
    plan = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    print(json.dumps(judge(plan, Path(argv[1]))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
