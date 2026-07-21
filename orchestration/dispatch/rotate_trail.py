#!/usr/bin/env python3
"""rotate_trail.py — retention for the dispatch ledger (CR052, DISPATCH_PROTOCOL.md §8.6).

Moves rows older than --keep-days out of the active dispatch/trail.md into monthly archives
under history/trail/trail-<YYYY-MM>.md, so the active ledger stays small and cheap to read.

This is a SINGLE, SHARED job owned by the Architect — NOT per-agent. trail.md + history/ are
single-writer (the Architect); running N per-agent rotators would race and corrupt the ledger.
Run it manually, or wire it to ONE daily routine (/schedule or cron) acting as the Architect.

The trail is a LOG, not a state store: the current state of any lane always comes from the lane
files (`dispatch.sh state`), never the trail. So archiving old log rows — even for a still-open
item — is always safe; you find the history in the dated archive if you ever need it.

Row format (pipe table): `| YYYY-MM-DD HH:MM | Item | Instance | Round | Event | Headline |`
Only rows whose first cell parses as a date are treated as data; the header/comment block is kept.

Usage:
  python3 rotate_trail.py [--keep-days N] [--dry-run] [--trail PATH] [--history DIR]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TRAIL = os.path.join(HERE, "trail.md")
DEFAULT_HISTORY = os.path.abspath(os.path.join(HERE, "..", "history", "trail"))

DATE_RE = re.compile(r"^\|\s*(\d{4})-(\d{2})-(\d{2})(?:[ T]\d{2}:\d{2})?\s*\|")
ARCHIVE_HEADER = (
    "<!-- Rotated dispatch-ledger rows for {period} (rotate_trail.py, CR052). "
    "Append-only archive; the active ledger is ../../dispatch/trail.md. -->\n\n"
    "# Dispatch ledger — {period}\n\n"
    "| When (KL) | Item | Instance | Round | Event | Headline |\n"
    "|---|---|---|---|---|---|\n"
)


def _row_date(line: str):
    m = DATE_RE.match(line)
    if not m:
        return None
    try:
        return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep-days", type=int, default=30, help="retain rows dated within the last N days (default 30)")
    ap.add_argument("--dry-run", action="store_true", help="report what would move; write nothing")
    ap.add_argument("--trail", default=DEFAULT_TRAIL)
    ap.add_argument("--history", default=DEFAULT_HISTORY)
    args = ap.parse_args(argv)

    if not os.path.isfile(args.trail):
        print(f"trail not found: {args.trail}", file=sys.stderr)
        return 2

    with open(args.trail, encoding="utf-8") as fh:
        lines = fh.readlines()

    cutoff = _dt.date.today() - _dt.timedelta(days=args.keep_days)
    keep: list[str] = []
    move: dict[str, list[str]] = {}  # "YYYY-MM" -> rows
    for line in lines:
        d = _row_date(line)
        if d is not None and d < cutoff:
            move.setdefault(f"{d.year:04d}-{d.month:02d}", []).append(line)
        else:
            keep.append(line)

    moved = sum(len(v) for v in move.values())
    if moved == 0:
        print(f"nothing to rotate (all rows within {args.keep_days} days of {cutoff + _dt.timedelta(days=args.keep_days)})")
        return 0

    print(f"rotating {moved} row(s) older than {cutoff} into {len(move)} archive(s):")
    for period in sorted(move):
        print(f"  {period}: {len(move[period])} row(s)")
    if args.dry_run:
        print("(dry-run — no files written)")
        return 0

    os.makedirs(args.history, exist_ok=True)
    for period, rows in move.items():
        path = os.path.join(args.history, f"trail-{period}.md")
        new = not os.path.isfile(path)
        with open(path, "a", encoding="utf-8") as fh:
            if new:
                fh.write(ARCHIVE_HEADER.format(period=period))
            fh.writelines(rows)
    with open(args.trail, "w", encoding="utf-8") as fh:
        fh.writelines(keep)
    print(f"done — active trail now {sum(1 for l in keep if _row_date(l))} data row(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
