"""prune_bug_attachments.py — age-based retention for bug-report attachments.

DEF201 (H9 follow-up): the total-volume cap this same defect added
(`bug_attachments_total_cap_bytes`, checked in `app/services/bug_attachments.py`)
stops the disk from filling silently — but once the volume actually reaches
that cap, NOTHING frees space, so every future upload is rejected forever.
The cap turned "fills silently" into "fails loudly" (CR040); this script is
what keeps the loud failure from becoming permanent.

Deletes attachments older than `--retention-days` (default: settings.
bug_attachments_retention_days). Age-based, not size-based — there is no
"Saiful already reviewed this one" signal to prune against (unlike bug
reports themselves, which have an ack flow — see feedback.py's /updates +
/ack; raw attachments don't), so the only safe backstop is a review window
long enough that nothing routinely queued for review gets deleted first.

Runs INSIDE the api-alpha container, same pattern as social_cache_warm.py —
so it reads the real mounted volume and the real Settings, not a Mac-local
guess at either:

    docker cp backend/scripts ami_api_alpha:/app/scripts
    docker exec ami_api_alpha python -m scripts.prune_bug_attachments --dry-run
    docker exec ami_api_alpha python -m scripts.prune_bug_attachments

Intended to run on a schedule (melehost cron), not per-request — this is
disk housekeeping, not something the API process does for itself.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from app.core.config import settings
from app.services.bug_attachments import ALLOWED_MIMES


def _attachment_suffixes() -> frozenset[str]:
    # ALLOWED_MIMES is the module's public export; deriving suffixes from
    # the same extension map _current_total_bytes uses (not re-declaring
    # our own list) keeps "what counts as an attachment" defined in ONE
    # place.
    ext_by_mime = {
        "image/jpeg": ".jpg", "image/png": ".png", "image/heic": ".heic",
        "image/heif": ".heif", "image/webp": ".webp", "image/gif": ".gif",
    }
    return frozenset(ext_by_mime[m] for m in ALLOWED_MIMES if m in ext_by_mime)


def prune(
    target_dir: Path,
    *,
    retention_days: int,
    dry_run: bool,
    now: float | None = None,
) -> tuple[int, int, int]:
    """Returns (scanned, deleted, bytes_freed). `now` is injectable for tests."""
    now = time.time() if now is None else now
    cutoff = now - (retention_days * 86400)
    suffixes = _attachment_suffixes()

    scanned = deleted = bytes_freed = 0
    if not target_dir.is_dir():
        return 0, 0, 0

    for f in target_dir.iterdir():
        if not f.is_file() or f.suffix not in suffixes:
            continue
        scanned += 1
        mtime = f.stat().st_mtime
        if mtime >= cutoff:
            continue
        size = f.stat().st_size
        if not dry_run:
            f.unlink(missing_ok=True)
        deleted += 1
        bytes_freed += size

    return scanned, deleted, bytes_freed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--retention-days", type=int, default=settings.bug_attachments_retention_days,
        help="delete attachments older than this many days (default: settings value)",
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="report what would be deleted without deleting anything",
    )
    ap.add_argument(
        "--dir", default=settings.bug_attachments_dir,
        help="attachments directory (default: settings.bug_attachments_dir)",
    )
    args = ap.parse_args(argv)

    scanned, deleted, bytes_freed = prune(
        Path(args.dir), retention_days=args.retention_days, dry_run=args.dry_run,
    )
    verb = "would delete" if args.dry_run else "deleted"
    print(
        f"prune_bug_attachments: scanned {scanned}, {verb} {deleted} "
        f"({bytes_freed:,} bytes), retention={args.retention_days}d, dir={args.dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
