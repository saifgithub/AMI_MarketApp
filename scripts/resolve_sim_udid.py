#!/usr/bin/env python3
"""Resolve an iOS Simulator name to a UDID. One implementation, two callers.

    scripts/resolve_sim_udid.py "iPhone 17"

Exists as a file rather than inline `python3 -c` because it had already gone
wrong twice in the two places it was duplicated:

1. Both copies matched by substring, so "iPhone 17" also matched
   "iPhone 17 Pro" and "iPhone 17 Pro Max" and picked whichever happened to be
   booted or listed first. A build once installed to the Pro while every later
   command addressed the non-Pro, and nothing reported the mismatch.
2. Fixing the inline copy inside a double-quoted shell command substitution
   broke the script outright: a Python comment mentioning "iPhone 17" in double
   quotes terminated the shell string.

A simulator UDID is machine-specific and must never be committed, so it is
resolved at run time. `qa/appium/helpers/device.py::resolve_ios_udid` keeps the
same semantics for the harness, which cannot shell out mid-session.
"""

from __future__ import annotations

import json
import subprocess
import sys


def resolve(name: str) -> str:
    raw = subprocess.run(
        ["xcrun", "simctl", "list", "devices", "available", "--json"],
        capture_output=True, text=True, timeout=120,
    ).stdout
    devices = [d for group in json.loads(raw).get("devices", {}).values() for d in group]
    wanted = name.strip().lower()

    exact = [d for d in devices if d.get("name", "").strip().lower() == wanted]
    if exact:
        booted = [d for d in exact if d.get("state") == "Booted"]
        return (booted or exact)[0]["udid"]

    partial = [d for d in devices if wanted in d.get("name", "").lower()]
    if len(partial) == 1:
        return partial[0]["udid"]
    if len(partial) > 1:
        names = sorted(d.get("name", "?") for d in partial)
        raise SystemExit(f"{name!r} is ambiguous: {names} — name the device exactly")
    raise SystemExit(
        f"no available simulator matching {name!r}. "
        f"Available: {sorted(d.get('name', '?') for d in devices)}"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: resolve_sim_udid.py <simulator name>")
    print(resolve(sys.argv[1]))
