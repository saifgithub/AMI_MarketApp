#!/usr/bin/env python3
"""CI status — one WARNING line in /promote-to-alpha, never a promotion blocker (CR235).

Background (measured by the Architect, 2026-09-25): GitHub Actions on `main` last went
green 2026-08-10. The harness job was red every run since 08-11 (stale `MANIFEST.sha256`,
then 8 stale containment tests), the backend job flapped 08-14->08-25 and then took 5h13m
on a single 09-17 run, and every push cancels the previous run — 11 consecutive cancels the
day this was measured. Nothing in `/promote-to-alpha` ever read the result, so 46 days of
red sat unseen. CR235 moves the tests that must GATE (Flutter, harness offline guards) into
the local release gate, where a human actually reads the exit code, and cuts CI to a
clean-checkout check in minutes. This script is what stops the new, shorter CI from going
right back to being a gate nobody reads: it prints the result for the exact commit being
promoted, in capitals when it's red, and it is Saiful's explicit choice that it WARNS
rather than blocks — the local gates are what block.

    scripts/promotion/ci_status.py --sha <commit>

Prints exactly one of:

    CI: GREEN — all jobs passed (<url>)
    CI: RED — <job1>, <job2> failed (<url>)
    CI: PENDING — still running (<url>)
    CI: CANCELLED — superseded by a later push (<url>)
    CI: NOT RUN — no workflow run found for this commit
    CI: UNAVAILABLE — gh CLI not installed / not authenticated (<detail>)

Exit code is ALWAYS 0 on a successful lookup (including RED, PENDING, CANCELLED, NOT RUN —
none of those are a script failure, they are facts about CI). The only non-zero exit is an
internal error preventing the check from running at all (unexpected `gh` output shape),
because "I could not tell" and "I looked and it's fine" must not look the same to whatever
called this — same distinction `postflight.py`'s COULD_NOT_RUN state already draws. The
caller (`/promote-to-alpha`) treats this as advisory regardless of exit code — it is never
allowed to abort the promotion, per Saiful's explicit ruling (CR235).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys

_WORKFLOW = "tests.yml"
_REPO_ROOT_MARKER = "AMI_MarketApp"


class CIUnavailable(Exception):
    """gh is missing, unauthenticated, or returned something this script can't parse."""


def _run_gh(args: list[str]) -> str:
    gh = shutil.which("gh")
    if gh is None:
        raise CIUnavailable("gh CLI not found on PATH")
    try:
        proc = subprocess.run(
            [gh, *args], capture_output=True, text=True, timeout=30, check=False
        )
    except Exception as exc:  # noqa: BLE001 - reported, not swallowed
        raise CIUnavailable(f"gh invocation failed: {type(exc).__name__}: {exc}") from exc
    if proc.returncode != 0:
        raise CIUnavailable(
            f"gh exited {proc.returncode}: {proc.stderr.strip()[:300] or proc.stdout.strip()[:300]}"
        )
    return proc.stdout


def fetch_run_for_sha(sha: str) -> dict | None:
    """The most recent `tests.yml` run for this exact commit, or None if none exists.

    `gh run list --commit` filters by headSha server-side (confirmed against the live repo,
    gh 2.92.0) — no client-side headSha filtering needed. Several runs can exist for the same
    sha (re-runs); the newest one is what matters.
    """
    out = _run_gh([
        "run", "list",
        "--commit", sha,
        "--workflow", _WORKFLOW,
        "--json", "status,conclusion,headSha,databaseId,url,createdAt",
        "--limit", "10",
    ])
    try:
        runs = json.loads(out)
    except json.JSONDecodeError as exc:
        raise CIUnavailable(f"gh run list returned non-JSON: {exc}") from exc
    if not isinstance(runs, list):
        raise CIUnavailable(f"gh run list returned unexpected shape: {out[:200]}")
    matching = [r for r in runs if r.get("headSha") == sha]
    if not matching:
        return None
    matching.sort(key=lambda r: r.get("createdAt", ""), reverse=True)
    return matching[0]


def fetch_failing_jobs(run_id: int) -> list[str]:
    """Job names with conclusion != success/skipped, for naming in the RED line."""
    out = _run_gh([
        "api", f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}/jobs",
        "--jq", ".jobs[] | @json",
    ])
    failing = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            job = json.loads(line)
        except json.JSONDecodeError:
            continue
        conclusion = job.get("conclusion")
        if conclusion not in ("success", "skipped", None):
            failing.append(job.get("name", "?"))
    return failing


def classify(run: dict) -> tuple[str, str]:
    """(label, detail) for a run dict. label is one of GREEN/RED/PENDING/CANCELLED."""
    status = run.get("status")
    conclusion = run.get("conclusion") or ""
    if status != "completed":
        return "PENDING", "still running"
    if conclusion == "success":
        return "GREEN", "all jobs passed"
    if conclusion == "cancelled":
        return "CANCELLED", "superseded by a later push"
    return "RED", conclusion or "failed"


def format_line(sha: str) -> str:
    try:
        run = fetch_run_for_sha(sha)
    except CIUnavailable as exc:
        return f"CI: UNAVAILABLE — {exc}"

    if run is None:
        return f"CI: NOT RUN — no {_WORKFLOW} run found for {sha[:12]}"

    label, detail = classify(run)
    url = run.get("url", "")

    if label == "RED":
        try:
            failing = fetch_failing_jobs(int(run["databaseId"]))
        except CIUnavailable:
            failing = []
        except (KeyError, ValueError, TypeError):
            failing = []
        names = ", ".join(failing) if failing else detail
        return f"CI: RED — {names} failed ({url})"
    if label == "GREEN":
        return f"CI: GREEN — all jobs passed ({url})"
    if label == "PENDING":
        return f"CI: PENDING — still running ({url})"
    if label == "CANCELLED":
        return f"CI: CANCELLED — superseded by a later push ({url})"
    return f"CI: {label} — {detail} ({url})"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sha", required=True, help="the commit being promoted (git rev-parse HEAD)")
    args = ap.parse_args()

    line = format_line(args.sha)
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
