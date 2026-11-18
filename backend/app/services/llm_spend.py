"""LLM cost and the daily spend ceiling (CR270, CR267 WP-12).

Two jobs, both reading `llm_audit`:

1. `compute_cost_usd` prices ONE call from `settings.llm_prices_json` and its
   token counts. Cost is None — never 0 — when either the tokens or the price
   is unknown; a missing price is logged once per model (`llm_price_missing`).
2. `check_budget` refuses NEW work when today's (UTC) spend has reached
   `settings.llm_daily_spend_ceiling_usd`. It FAILS CLOSED when spend cannot be
   known: a row today that has token counts but no cost (an unpriced model), or
   a DB read that errors. "Unknown" is treated as "used up", never as "cheap".

Ceiling unset (None) = no ceiling, no DB read, today's behaviour.
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Iterable

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, or_, select

from app.core.config import parse_llm_prices, settings
from app.core.logging import logger
from app.db.models import LLMAuditRow
from app.db.session import get_session

BUDGET_MESSAGE = (
    "AMI is temporarily unavailable — today's model budget is used up. "
    "Please try again after 00:00 UTC."
)
BUDGET_CODE = "llm_budget_exhausted"

SPEND_CACHE_TTL_S = 60.0

_lock = threading.Lock()
_missing_price_logged: set[str] = set()
_cache: dict[str, object] = {}
_alerted_days: set[str] = set()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _monotonic() -> float:
    return time.monotonic()


def reset_state() -> None:
    """Forget every per-process memo (tests; never called in production)."""
    with _lock:
        _missing_price_logged.clear()
        _cache.clear()
        _alerted_days.clear()
    _prices_for.cache_clear()


@lru_cache(maxsize=8)
def _prices_for(raw: str) -> dict[str, tuple[float, float]]:
    return parse_llm_prices(raw)


def compute_cost_usd(
    model_keys: Iterable[str | None],
    input_tokens: int | None,
    output_tokens: int | None,
) -> float | None:
    """USD for one call, or None when it cannot be known.

    `model_keys` is tried in order (the served model id first, then the
    configured one) so an operator may price either spelling. Cached input
    tokens are billed at the full input rate: an over-estimate, the safe side
    for a ceiling.
    """
    keys = [k for k in model_keys if k]
    if input_tokens is None or output_tokens is None:
        return None
    prices = _prices_for(settings.llm_prices_json)
    for key in keys:
        entry = prices.get(key)
        if entry is not None:
            p_in, p_out = entry
            return (input_tokens * p_in + output_tokens * p_out) / 1_000_000.0
    label = keys[0] if keys else "<unknown model>"
    with _lock:
        first = label not in _missing_price_logged
        _missing_price_logged.add(label)
    if first:
        logger.warning(
            "llm_price_missing",
            model=label,
            tried=keys,
            detail=(
                "no entry in LLM_PRICES_JSON — this call's cost is recorded NULL "
                "(unknown, not free); with a daily ceiling set the ceiling fails closed"
            ),
        )
    return None


@dataclass(frozen=True)
class SpendReading:
    day: str
    spend_usd: float
    unknown_cost_rows: int


def _read_spend(day_start: datetime) -> tuple[float, int]:
    has_tokens = or_(
        LLMAuditRow.input_tokens.isnot(None), LLMAuditRow.output_tokens.isnot(None)
    )
    # DEF488: a row written before CR270 has no `model` and could never have
    # been priced; counting it closed the gate for the rest of the deploy day.
    unknown = case(
        (and_(LLMAuditRow.cost_usd.is_(None), has_tokens, LLMAuditRow.model.isnot(None)), 1),
        else_=0,
    )
    with get_session() as s:
        total, unknown_rows = s.execute(
            select(
                func.coalesce(func.sum(LLMAuditRow.cost_usd), 0),
                func.coalesce(func.sum(unknown), 0),
            ).where(LLMAuditRow.created_at >= day_start)
        ).one()
    return float(total), int(unknown_rows)


def todays_spend() -> SpendReading:
    """Today's (UTC) summed cost across every provider, cached for 60 s.

    A new UTC day never reuses the previous day's cached sum. Raises whatever
    the DB raises — `check_budget` turns that into a closed gate.
    """
    now = _utcnow()
    day = now.strftime("%Y-%m-%d")
    with _lock:
        hit = _cache.get("reading")
        if (
            isinstance(hit, SpendReading)
            and hit.day == day
            and _monotonic() - float(_cache["at"]) < SPEND_CACHE_TTL_S  # type: ignore[arg-type]
        ):
            return hit
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    spend, unknown_rows = _read_spend(day_start)
    reading = SpendReading(day=day, spend_usd=spend, unknown_cost_rows=unknown_rows)
    with _lock:
        _cache["reading"] = reading
        _cache["at"] = _monotonic()
    return reading


class LLMBudgetExhausted(Exception):
    """Today's model budget is used up (or cannot be proven not to be)."""

    def __init__(self, reason: str) -> None:
        super().__init__(BUDGET_MESSAGE)
        self.reason = reason


def _alert_once(day: str, reason: str, **fields: object) -> None:
    with _lock:
        if day in _alerted_days:
            return
        _alerted_days.add(day)
    logger.error("llm_spend_ceiling_breached", day=day, reason=reason, **fields)
    try:
        import sentry_sdk

        sentry_sdk.capture_message(
            f"llm_spend_ceiling_breached ({reason}) {day}", level="error"
        )
    except Exception:
        pass


def check_budget(surface: str = "unknown") -> None:
    """Raise `LLMBudgetExhausted` when NEW LLM work must be refused.

    No-op without a ceiling. Synchronous (it may read the DB), so async callers
    run it in a threadpool.
    """
    ceiling = settings.llm_daily_spend_ceiling_usd
    if ceiling is None:
        return
    day = _utcnow().strftime("%Y-%m-%d")
    try:
        reading = todays_spend()
    except Exception:
        logger.exception("llm_spend_check_failed", surface=surface)
        _alert_once(day, "spend_unreadable", ceiling_usd=ceiling)
        raise LLMBudgetExhausted("spend_unreadable")
    if reading.unknown_cost_rows > 0:
        _alert_once(
            reading.day,
            "unknown_cost",
            ceiling_usd=ceiling,
            spend_usd=reading.spend_usd,
            unknown_cost_rows=reading.unknown_cost_rows,
            detail=(
                "today's llm_audit has calls with token counts but no cost (a model "
                "missing from LLM_PRICES_JSON): spend cannot be known, so the gate "
                "is closed"
            ),
        )
        logger.warning("llm_budget_refused", surface=surface, reason="unknown_cost")
        raise LLMBudgetExhausted("unknown_cost")
    if reading.spend_usd >= ceiling:
        _alert_once(
            reading.day,
            "ceiling_reached",
            ceiling_usd=ceiling,
            spend_usd=reading.spend_usd,
        )
        logger.warning("llm_budget_refused", surface=surface, reason="ceiling_reached")
        raise LLMBudgetExhausted("ceiling_reached")


async def enforce_budget(surface: str) -> None:
    """Route-side gate: `check_budget` off the event loop, refusal as a 503."""
    try:
        await asyncio.to_thread(check_budget, surface)
    except LLMBudgetExhausted as exc:
        raise budget_http_exception(exc) from exc


def budget_http_exception(exc: LLMBudgetExhausted | None = None) -> HTTPException:
    """The refusal every route returns: 503, AMI-voiced, with a retry hint.

    503 (not 4xx) because nothing the user did is wrong and nothing about their
    account needs changing — the same reasoning as sim.py's DEF305 — and the
    client already renders a 5xx on the Room as a friendly "try again" card.
    """
    now = _utcnow()
    resets_at = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    retry_after = max(1, int((resets_at - now).total_seconds()))
    return HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": BUDGET_CODE,
            "message": BUDGET_MESSAGE,
            "resets_at": resets_at.isoformat(),
            "retry_after_seconds": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )
