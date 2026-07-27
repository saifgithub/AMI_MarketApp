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

from datetime import date, datetime, timezone


def now_utc() -> datetime:
    """Naive UTC `datetime` — same semantics as the deprecated `utcnow()`."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def relative_day_phrase(target: date, today: date) -> str:
    """Render `target`'s distance from `today` as a phrase an LLM can quote
    directly instead of doing date arithmetic itself (DEF124) — a bare ISO
    date gives the model no "today" to subtract from, so it guesses. Shared
    by `room_runner._profile_for_ticker` (the Room) and
    `fundamentals.build_live_data_block` (1-on-1) so both surfaces anchor a
    date the same way against the same UTC calendar-date basis (D4).

    Past dates are handled explicitly ("N days ago"), not left to go
    negative — a stale cache returning a lapsed date must not render
    "in -2 days"."""
    delta = (target - today).days
    if delta == 0:
        return "today"
    if delta > 0:
        return f"in {delta} day{'s' if delta != 1 else ''}"
    days_ago = -delta
    return f"{days_ago} day{'s' if days_ago != 1 else ''} ago"
