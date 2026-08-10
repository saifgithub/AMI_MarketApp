"""As-of run context (CR164) — the one switch that puts the production data
layer into historical mode for a single Room run.

The backtest harness runs the REAL Room (runner, prompts, credits, safety
floor) with one difference: while an `AsOfContext` is active, the data
services serve only facts knowable on `as_of` — `price_history` reads rows
`date <= as_of` and never fetches, `market_data` returns the store-backed
provider, `fundamentals` resolves EDGAR facts `filed <= as_of`, and the
news/social feed probes are skipped entirely (UNAVAILABLE, honest absence).

Request-scoped by design: CR035's ablation arms flipped live Alpha's env and
degraded real users until restored. This context travels with one run's
asyncio task (ContextVar → inherited by `asyncio.to_thread`) and touches
nothing else. There is deliberately NO env var and NO public API field that
can set it — only the admin backtest endpoint constructs one.

Imports nothing from app.services, so any service module may import it
without a cycle.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date
from typing import Iterator


class AsOfLeakageError(RuntimeError):
    """A data path emitted a fact dated after the active as_of cutoff.

    Raised, never truncated-around: a backtest run that would silently see
    the future must die loudly (CR040) — a wrong run is worse than a failed
    one, because it scores as evidence.
    """


@dataclass(frozen=True)
class AsOfContext:
    """One backtest run's temporal identity.

    `as_of` — the run's "today": every fact the Room sees must be knowable
    on this date. `batch_id`/`arm` identify the sweep for bookkeeping
    (`backtest_run_index`) and reporting; they never reach a prompt.
    """

    as_of: date
    batch_id: str
    arm: str = "pit_v1"


_asof_var: ContextVar[AsOfContext | None] = ContextVar("asof_context", default=None)


def current_asof() -> AsOfContext | None:
    """The active as-of context, or None on every live-traffic path."""
    return _asof_var.get()


@contextmanager
def asof_scope(ctx: AsOfContext) -> Iterator[AsOfContext]:
    """Activate `ctx` for the enclosed block (and everything it awaits or
    sends to `asyncio.to_thread`, which copies the context)."""
    token = _asof_var.set(ctx)
    try:
        yield ctx
    finally:
        _asof_var.reset(token)


def assert_dates_within(dates: list[date], as_of: date, *, origin: str) -> None:
    """The store-level leakage guard: every served date must be <= as_of.

    Called by each as-of read path AFTER its query, so a wrong query (or a
    future refactor that drops the WHERE clause) fails the run instead of
    leaking the future into a prompt.
    """
    if not dates:
        return
    newest = max(dates)
    if newest > as_of:
        raise AsOfLeakageError(
            f"{origin} served a fact dated {newest.isoformat()} past the "
            f"as_of cutoff {as_of.isoformat()}"
        )
