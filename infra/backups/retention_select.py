#!/usr/bin/env python3
"""Pick which backup names to DELETE under a daily + weekly retention rule.

Why: pg-backup.sh keeps backups off-server in an S3-compatible bucket (R2) and
must prune them without a bucket lifecycle rule. Names come from stdin, one per
line, `ami_trade-YYYYmmddTHHMMSSZ.sql.gz.gpg`. Kept: the newest --daily names,
plus the newest name of each of the --weekly most recent ISO weeks that has any
name older than the daily window. Everything else is printed for deletion.

A name that does not match the pattern is never printed: unknown objects in the
bucket are not ours to delete.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime

_NAME = re.compile(r"^ami_trade-(\d{8}T\d{6}Z)\.sql\.gz\.gpg$")


def select_deletions(names: list[str], daily: int, weekly: int) -> list[str]:
    parsed = []
    for name in names:
        m = _NAME.match(name.strip())
        if m:
            parsed.append((datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ"), name.strip()))
    parsed.sort(reverse=True)
    keep = {name for _, name in parsed[:daily]}
    seen_weeks: list[tuple[int, int]] = []
    for ts, name in parsed[daily:]:
        iso = ts.isocalendar()
        week = (iso[0], iso[1])
        if week in seen_weeks:
            continue
        if len(seen_weeks) < weekly:
            seen_weeks.append(week)
            keep.add(name)
    return sorted(name for _, name in parsed if name not in keep)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--daily", type=int, default=14)
    ap.add_argument("--weekly", type=int, default=8)
    args = ap.parse_args()
    if args.daily < 1 or args.weekly < 0:
        print("--daily must be >= 1 and --weekly >= 0", file=sys.stderr)
        return 2
    for name in select_deletions(sys.stdin.read().split(), args.daily, args.weekly):
        print(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
