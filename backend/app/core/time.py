"""Time helpers — naive UTC `now()` for legacy callers.

`datetime.utcnow()` was deprecated in 3.12. The recommended replacement
`datetime.now(timezone.utc)` returns a tz-aware datetime, which breaks
comparisons against the many naive datetimes already persisted in the
codebase (tests, schema defaults, in-memory stores).

`now_utc()` returns naive UTC — same semantics as `utcnow()`, no warning.
New code that wants tz-aware should call `datetime.now(timezone.utc)`
directly; this helper exists only to drain the deprecation cleanly.
"""

from __future__ import annotations

from datetime import datetime, timezone


def now_utc() -> datetime:
    """Naive UTC `datetime` — same semantics as the deprecated `utcnow()`."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
