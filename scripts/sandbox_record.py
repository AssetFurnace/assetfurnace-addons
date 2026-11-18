#!/usr/bin/env python3
"""Write the test result into an entry. Usage: sandbox_record.py ENTRY.json VERDICT.json [--date YYYY-MM-DD] > new entry.

Only `passed` and `not_run` are ever recorded (a failure is never merged). The record says plainly whether we ran it:
{"run_check": {"status": "passed" | "not_run", "reason": "...", "date": "..."}}. Whatever run_check the entry arrived
with is replaced: only this step, after the real test, may write it.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path


def record(entry: dict, verdict: dict, date: str) -> dict:
    status = verdict.get("status")
    if status not in ("passed", "not_run"):
        raise ValueError(f"cannot record a {status!r} result")
    check = {"status": status, "date": date}
    if status == "not_run":
        check["reason"] = str(verdict.get("reason", ""))[:200]
    return {**{k: v for k, v in entry.items() if k != "run_check"}, "run_check": check}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("entry", type=Path)
    p.add_argument("verdict", type=Path)
    p.add_argument("--date", default=datetime.date.today().isoformat())
    a = p.parse_args(argv)
    new = record(json.loads(a.entry.read_text(encoding="utf-8")), json.loads(a.verdict.read_text(encoding="utf-8")), a.date)
    print(json.dumps(new, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
