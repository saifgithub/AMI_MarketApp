#!/usr/bin/env python3
"""Preflight tree gate — is the tree clean in the way that matters? (CR175 Tier D)

`/promote-to-alpha` step 1 printed `git status --short` and told the operator it
"must print nothing", with no `exit 1` behind it. On this shared checkout, with
three or more concurrent tracks, it prints ~20 lines routinely — measured
2026-08-12: **21 lines, none of them the promoter's**. A gate whose failing
state is the normal state is not a gate. It is training to scroll past a failing
check, which is the exact habit the command's own hold-gate comment says it
exists to break.

Blanket-failing on any dirt would make that worse, not better: it would block
every promotion on another lane's uncommitted research notes, and the operator
would learn to pass `--force`. So this classifies instead, using the one
distinction that actually matters — **can this path change what the container
runs?**

    BLOCKING       reaches the running container. Fails closed.
    SHIPPED        rsync copies it to the box; the container never reads it.
                   Reported, recorded in the promotion summary, not blocking.
    NOT SHIPPED    the rsync exclude list drops it. Reported for completeness.

`docker-compose.yml` is what makes BLOCKING derivable rather than guessed: the
api-alpha service bind-mounts `./backend/app`, `./backend/scripts`,
`./backend/tests` and `./content` over the image, so **a change to those paths
is live on the box the moment the rsync lands, with no rebuild at all.** The
build context `./backend` and the compose file itself round out the set.

Exit 0 nothing blocking · 1 blocking dirt · 2 could not run.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Paths whose contents reach the running container. Derived from
# docker-compose.yml's api-alpha service, not from memory:
#   build.context      ./backend
#   volumes (ro)       ./backend/app, ./backend/tests, ./backend/scripts, ./content
# A change under any of these is live after an rsync + swap. `infra/` carries
# the env file the container boots from (gitignored itself, but its README and
# the hold file gate the promotion).
_BLOCKING_PREFIXES = (
    "backend/",
    "content/",
    "docker-compose.yml",
    "infra/",
)

# The rsync exclude list from /promote-to-alpha step 3. Anything matching never
# leaves the Mac, so its dirtiness cannot affect Alpha in any way.
_NOT_SHIPPED_PREFIXES = (
    "mobile/",
    ".claude/",
    "website/",
    "audit/",
    "reports/",
    "backtest_results/",   # DEF276
    ".idea/",
    ".vscode/",
)


def _git_status(repo: Path) -> list[tuple[str, str]]:
    """(status_code, path) for every modified or untracked path. Ignored files
    are already absent — `--porcelain` does not list them without `--ignored`."""
    proc = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git status failed: {proc.stderr.strip()}")
    out: list[tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        code, path = line[:2], line[3:]
        # A rename reads "old -> new"; the new path is what ships.
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        out.append((code, path.strip().strip('"')))
    return out


def classify(path: str) -> str:
    if path.startswith(_NOT_SHIPPED_PREFIXES):
        return "NOT SHIPPED"
    if path.startswith(_BLOCKING_PREFIXES):
        return "BLOCKING"
    return "SHIPPED"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=str(_REPO_ROOT))
    ap.add_argument("--quiet-clean", action="store_true",
                    help="print nothing when there is no blocking dirt")
    args = ap.parse_args()

    try:
        entries = _git_status(Path(args.repo))
    except Exception as exc:
        print(f"CANNOT RUN — {exc}", file=sys.stderr)
        return 2

    groups: dict[str, list[tuple[str, str]]] = {
        "BLOCKING": [], "SHIPPED": [], "NOT SHIPPED": []}
    for code, path in entries:
        groups[classify(path)].append((code, path))

    blocking = groups["BLOCKING"]
    if blocking:
        print(f"PREFLIGHT TREE: {len(blocking)} uncommitted path(s) reach the "
              "running container.\n")
        for code, path in blocking:
            print(f"  {code} {path}")
        print("\nThese are bind-mounted or built into api-alpha, so the rsync "
              "would ship code the tag does not describe.\nCommit them, stash "
              "them, or promote from a clean checkout.")
        return 1

    if args.quiet_clean and not groups["SHIPPED"]:
        return 0

    print("PREFLIGHT TREE: no uncommitted path reaches the container.")
    if groups["SHIPPED"]:
        print(f"\n  {len(groups['SHIPPED'])} path(s) ship but cannot change "
              "behaviour (recorded, not blocking):")
        for code, path in groups["SHIPPED"][:12]:
            print(f"    {code} {path}")
        if len(groups["SHIPPED"]) > 12:
            print(f"    … and {len(groups['SHIPPED']) - 12} more")
    if groups["NOT SHIPPED"]:
        print(f"\n  {len(groups['NOT SHIPPED'])} path(s) excluded from the "
              "rsync entirely.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
