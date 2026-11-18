#!/usr/bin/env python3
"""Install and run an add-on with the studio's own add-on commands, on a throwaway machine. UNTRUSTED ZONE.

Usage: sandbox_exec.py PLAN.json --lab PATH_TO_IMAGE_TO_3DLAB --out DIR

Runs inside the sandbox job only. It does not decide anything: it installs the add-on exactly the way a user would
(`addon add --unlisted repo@commit --yes`), runs each planned tool, and copies what came out to DIR with a run.json
of what happened. The add-on's code can lie to this script, so a separate trusted job re-checks every file it
produced (sandbox_verdict.py). Nothing here may be trusted; nothing here has any token.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

SETUP_SECONDS = 420
RUN_SECONDS = 300
LOG_TAIL = 2000


def tail(text: bytes | str | None) -> str:
    text = text.decode("utf-8", "replace") if isinstance(text, bytes) else (text or "")
    return text[-LOG_TAIL:]


def run(argv: list[str], env: dict, seconds: int, runner=subprocess.run) -> tuple[int, str]:
    """(exit code, last of the output). A timeout is exit code 124."""
    try:
        done = runner(argv, env=env, capture_output=True, timeout=seconds, check=False)
        return done.returncode, tail(done.stdout) + tail(done.stderr)
    except subprocess.TimeoutExpired as exc:
        return 124, tail(exc.stdout) + tail(exc.stderr)


def execute(plan: dict, lab: Path, out: Path, runner=subprocess.run) -> dict:
    work = out / "work"
    addons, output = work / "addons", work / "output"
    addons.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "ADDONS_DIR": str(addons), "OUTPUT_DIR": str(output)}
    cli = [sys.executable, str(lab / "scripts" / "addon.py")]
    result = {"install_exit": None, "log": "", "runs": []}
    code, log = run(cli + ["add", "--unlisted", f"{plan['repo']}@{plan['commit']}", "--yes"], env, SETUP_SECONDS, runner)
    result["install_exit"], result["log"] = code, log
    if code == 0:
        for index, step in enumerate(plan["runs"]):
            argv = cli + ["run", plan["id"], step["tool"]]
            for key, value in step["inputs"].items():
                argv += ["--input", f"{key}={value}"]
            before = {p for p in output.rglob("*") if p.is_file()}
            started = time.time()
            code, log = run(argv, env, RUN_SECONDS, runner)
            made = sorted(p for p in output.rglob("*.glb") if p.is_file() and p not in before)
            files = []
            for n, src in enumerate(made[:3]):
                name = f"run{index}-{n}.glb"
                shutil.copyfile(src, out / name)
                files.append(name)
            result["runs"].append({"tool": step["tool"], "exit": code, "seconds": round(time.time() - started, 1), "files": files, "log": log})
    shutil.rmtree(work, ignore_errors=True)
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("plan", type=Path)
    p.add_argument("--lab", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    plan = json.loads(a.plan.read_text(encoding="utf-8"))
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "run.json").write_text(json.dumps(execute(plan, a.lab, a.out)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
