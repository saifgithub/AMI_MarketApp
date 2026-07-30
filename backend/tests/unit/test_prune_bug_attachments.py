"""DEF201 (H9 follow-up) — age-based retention for bug-report attachments.

The total-volume cap (`test_bug_attachments.py`) stops the disk filling
silently by rejecting new uploads once at cap; nothing then frees space, so
that cap would become a permanent wall without this. `prune()` is the pure
logic backend/scripts/prune_bug_attachments.py's CLI wraps — tested
directly here rather than via subprocess, same pattern as
test_def110_backfill.py importing `_plan_and_apply` straight off the
scripts/ path.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from prune_bug_attachments import prune  # noqa: E402


_DAY = 86400


def _touch(path: Path, *, content: bytes = b"x" * 10, age_days: float = 0) -> Path:
    path.write_bytes(content)
    if age_days:
        stamp = time.time() - age_days * _DAY
        import os
        os.utime(path, (stamp, stamp))
    return path


def test_deletes_files_older_than_retention_keeps_newer_ones(tmp_path: Path):
    old = _touch(tmp_path / "old.png", age_days=90)
    fresh = _touch(tmp_path / "fresh.png", age_days=1)

    scanned, deleted, freed = prune(tmp_path, retention_days=60, dry_run=False)

    assert scanned == 2
    assert deleted == 1
    assert freed == 10
    assert not old.exists()
    assert fresh.exists()


def test_boundary_case_age_equal_to_retention_is_kept(tmp_path: Path):
    """A file whose age equals the retention window exactly must be kept,
    not deleted — the boundary is `>`, not `>=`. Both the file's mtime and
    `prune`'s notion of "now" are pinned to the SAME instant here; without
    that, two independent `time.time()` calls a few milliseconds apart make
    this boundary un-testably flaky in either direction."""
    import os
    fixed_now = time.time()
    at_boundary = tmp_path / "boundary.png"
    at_boundary.write_bytes(b"x" * 10)
    stamp = fixed_now - 60 * _DAY
    os.utime(at_boundary, (stamp, stamp))

    scanned, deleted, freed = prune(
        tmp_path, retention_days=60, dry_run=False, now=fixed_now,
    )
    assert deleted == 0
    assert at_boundary.exists()


def test_dry_run_reports_but_does_not_delete(tmp_path: Path):
    old = _touch(tmp_path / "old.png", age_days=90)

    scanned, deleted, freed = prune(tmp_path, retention_days=60, dry_run=True)

    assert scanned == 1
    assert deleted == 1  # counted as "would delete"
    assert freed == 10
    assert old.exists()  # ...but the dry run must not have touched disk


def test_non_attachment_extensions_are_ignored(tmp_path: Path):
    """The sqlite test-DB tempfile shares this dir in other tests
    (test_bug_attachments.py's own note) — a janitor that deleted anything
    other than photo attachments would be a much worse bug than the one it
    fixes. Pin that it only ever touches known attachment suffixes."""
    old_db = _touch(tmp_path / "test.db", age_days=90)
    old_png = _touch(tmp_path / "old.png", age_days=90)

    scanned, deleted, freed = prune(tmp_path, retention_days=60, dry_run=False)

    assert scanned == 1  # the .db file was never even counted
    assert deleted == 1
    assert old_db.exists()  # untouched
    assert not old_png.exists()


def test_missing_directory_is_a_no_op_not_an_error(tmp_path: Path):
    missing = tmp_path / "does_not_exist_yet"
    scanned, deleted, freed = prune(missing, retention_days=60, dry_run=False)
    assert (scanned, deleted, freed) == (0, 0, 0)


def test_bytes_freed_sums_across_multiple_deletions(tmp_path: Path):
    _touch(tmp_path / "a.png", content=b"x" * 100, age_days=90)
    _touch(tmp_path / "b.jpg", content=b"y" * 250, age_days=90)
    _touch(tmp_path / "c.png", content=b"z" * 10, age_days=1)  # kept

    scanned, deleted, freed = prune(tmp_path, retention_days=60, dry_run=False)

    assert scanned == 3
    assert deleted == 2
    assert freed == 350
