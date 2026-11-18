#!/usr/bin/env python3
"""Install and run an add-on with the studio's own add-on commands, on a throwaway machine. UNTRUSTED ZONE.

Usage: sandbox_exec.py PLAN.json --lab PATH_TO_IMAGE_TO_3DLAB --out DIR

Runs inside the sandbox job only. It does not decide anything: it installs the add-on exactly the way a user would
(`addon add --unlisted repo@commit --yes`), runs each planned tool, and copies what came out to DIR with a run.json
of what happened. The add-on's code can lie to this script, so a separate trusted job re-checks every file it
produced (sandbox_verdict.py). Nothing here may be trusted; nothing here has any token.

Time: the whole thing has one budget (TOTAL_SECONDS) that fits inside the job's limit, a time-out kills the add-on's
whole process group (not just the first process), and run.json is rewritten after every step, so an overrun still
reports what happened up to then.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

SETUP_SECONDS = 420
RUN_SECONDS = 300
TOTAL_SECONDS = 900      # the job limit is 20 minutes and the Blender download comes out of it
LOG_TAIL = 2000


def tail(data: bytes | str | None) -> str:
    text = data.decode("utf-8", "replace") if isinstance(data, bytes) else (data or "")
    return text[-LOG_TAIL:]


def popen_run(argv: list[str], env: dict, seconds: float) -> tuple[int, str]:
    """(exit code, last of the output). Time-out = the whole process group is killed, exit code 124."""
    proc = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=max(1.0, seconds))
        return proc.returncode, tail(out)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        out, _ = proc.communicate()
        return 124, tail(out)


def execute(plan: dict, lab: Path, out: Path, runner=popen_run, on_progress=lambda result: None,
            total: float = TOTAL_SECONDS, clock=time.monotonic) -> dict:
    deadline = clock() + total
    work = out / "work"
    addons, output = work / "addons", work / "output"
    addons.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "ADDONS_DIR": str(addons), "OUTPUT_DIR": str(output)}
    cli = [sys.executable, str(lab / "scripts" / "addon.py")]
    result = {"install_exit": -1, "log": "", "runs": []}   # -1 until the install is done: a run that dies early reads as "did not install"
    on_progress(result)
    code, log = runner(cli + ["add", "--unlisted", f"{plan['repo']}@{plan['commit']}", "--yes"], env, min(SETUP_SECONDS, deadline - clock()))
    result["install_exit"], result["log"] = code, log
    on_progress(result)
    if code == 0:
        for index, step in enumerate(plan["runs"]):
            argv = cli + ["run", plan["id"], step["tool"]]
            for key, value in step["inputs"].items():
                argv += ["--input", f"{key}={value}"]
            before = {p for p in output.rglob("*") if p.is_file()}
            started = clock()
            left = deadline - started
            if left <= 1:
                code, log = 124, "out of time before this tool could run"
            else:
                code, log = runner(argv, env, min(RUN_SECONDS, left))
            made = sorted(p for p in output.rglob("*.glb") if p.is_file() and p not in before)
            files = []
            for n, src in enumerate(made[:3]):
                name = f"run{index}-{n}.glb"
                shutil.copyfile(src, out / name)
                files.append(name)
            result["runs"].append({"tool": step["tool"], "exit": code, "seconds": round(clock() - started, 1), "files": files, "log": log})
            on_progress(result)
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
    write = lambda result: (a.out / "run.json").write_text(json.dumps(result), encoding="utf-8")  # noqa: E731
    write(execute(plan, a.lab, a.out, on_progress=write))
    return 0


if __name__ == "__main__":
    sys.exit(main())
