#!/usr/bin/env python3
"""Run a command under a wall-clock cap. macOS ships no coreutils `timeout` (CR215).

Needed because `kimi -p` does not reliably exit once the model has stopped working — the first
foreign-auditor run wrote its output correctly and then sat there until the caller gave up. A hung
harness that has already delivered its artifact must not look like a failure, so this returns the
child's own exit code normally and 124 on timeout (the GNU convention), leaving the caller to decide
by inspecting what the child actually produced.

The child gets its own process group so the kill reaches the whole tree, not just the wrapper's
direct child — an agent harness spawns tool subprocesses that would otherwise outlive it.

Usage: run_timeout.py <seconds> <command> [args...]
"""
import os
import signal
import subprocess
import sys

if len(sys.argv) < 3:
    sys.stderr.write("usage: run_timeout.py <seconds> <command> [args...]\n")
    sys.exit(2)

proc = subprocess.Popen(sys.argv[2:], start_new_session=True)
try:
    sys.exit(proc.wait(timeout=float(sys.argv[1])))
except subprocess.TimeoutExpired:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=10)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
    sys.exit(124)
