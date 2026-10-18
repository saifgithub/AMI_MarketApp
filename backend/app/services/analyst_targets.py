"""CR260 — analyst price-target detail for the Room fact sheet (Saiful
2026-10-18: show users the buy/sell targets the Street announced on the
ticker the room convened on).

Two yfinance surfaces the existing consensus line
(`fundamentals.analyst_consensus_line`, from `.info`) does not carry:

  - `recommendations_summary` — the strong-buy/buy/hold/sell/strong-sell
    count distribution behind the consensus, plus its trailing monthly
    history (the drift the consensus word hides: a "buy" whose sells
    halved since last month is a different "buy").
  - `upgrades_downgrades` — the dated per-firm action tape: firm, grade
    change, Raises/Lowers/Maintains, prior→current PT.

Lane ruling (Saiful 2026-10-18, lane-pure): the split rides the
`fundamentals` domain (Fundamentals Analyst), the tape rides the `news`
domain (News Analyst). `room_prompts._format_profile` withholds per lane
(CR145 Tier C), so the overlay writes both to the profile and the renderer
gates each on its own `field_state` key — domain assignment is a render
decision, not a payload property.

Both surfaces ride `suppress_analyst_consensus` (CR035) at the fetch site:
the tape names price targets, so an ablation arm that stripped the
consensus but left the tape standing would leak the figure it exists to
remove — the same argument fundamentals.py makes for the high/low band.

Nothing here is price-like (unlike `.info`, which is deliberately
uncached because `base_price` lives in it), so the pair is cached
together at the statements-cache TTL precedent.
"""

from __future__ import annotations

import time
from threading import RLock
from typing import Any

from app.core.config import settings
from app.core.logging import logger

_CACHE_TTL_S = 21600.0  # 6h — fundamentals._STATEMENTS_TTL_S precedent

# CR260 lane ruling — bounded render: the newest N tape rows per ticker.
TAPE_LIMIT = 5

_cache: dict[str, tuple[dict[str, Any] | None, float]] = {}
_lock = RLock()


def clear_analyst_targets_cache() -> None:
    """Drop every cached split/tape. Test seam, and the operational escape
    hatch if a ratings sweep lands inside the TTL window."""
    with _lock:
        _cache.clear()


def fetch_analyst_detail(ticker: str) -> dict[str, Any] | None:
    """The split (+ history) and the tape for one ticker; None when gated
    off or the fetch failed. Cached per ticker at `_CACHE_TTL_S`.

    Returned dict keys (all optional — yfinance omits a surface for some
    names): `analyst_rating_split` {strong_buy, buy, hold, sell,
    strong_sell}, `analyst_rating_split_history` (same shape plus `period`,
    newest previous month first), `analyst_tape` (latest `TAPE_LIMIT` rows,
    newest first: date, firm, to_grade, from_grade, action, pt_action,
    current_pt, prior_pt).
    """
    if not settings.use_real_market_data:
        return None
    if settings.suppress_analyst_consensus:
        return None  # CR035 — the tape names price targets; see module docstring
    key = ticker.upper()
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit is not None and hit[1] > now:
            return hit[0]
    detail = _fetch(key)
    with _lock:
        _cache[key] = (detail, now + _CACHE_TTL_S)
    return detail


def _fetch(ticker: str) -> dict[str, Any] | None:
    try:
        import yfinance as yf

        from app.services.fundamentals import _warn_if_yfinance_convention_stale

        _warn_if_yfinance_convention_stale(yf)
        t = yf.Ticker(ticker)
        out: dict[str, Any] = {}
        split, history = _split_from_frame(t.recommendations_summary)
        if split:
            out["analyst_rating_split"] = split
            if history:
                out["analyst_rating_split_history"] = history
        tape = _tape_from_frame(t.upgrades_downgrades)
        if tape:
            out["analyst_tape"] = tape
        return out or None
    except Exception as exc:  # CR040 — loud at the fetch site, absent below
        logger.error("analyst_targets_fetch_error", ticker=ticker, error=str(exc)[:200])
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        if value != value:  # NaN — pandas' missing marker
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _split_from_frame(frame: Any) -> tuple[dict[str, int] | None, list[dict[str, Any]]]:
    """`recommendations_summary` → the current-month split plus the prior
    months' history. Empty/absent frame → (None, []); a month whose counts
    don't parse is skipped, never half-counted."""
    if frame is None or getattr(frame, "empty", True):
        return None, []
    split: dict[str, int] | None = None
    history: list[dict[str, Any]] = []
    try:
        rows = frame.reset_index().to_dict("records")
    except Exception:
        return None, []
    for i, row in enumerate(rows):
        counts = {k: _int_or_none(row.get(c)) for k, c in (
            ("strong_buy", "strongBuy"), ("buy", "buy"), ("hold", "hold"),
            ("sell", "sell"), ("strong_sell", "strongSell"),
        )}
        if any(v is None for v in counts.values()):
            continue
        entry = {**counts, "period": str(row.get("period", ""))}
        if i == 0:
            split = counts
        else:
            history.append(entry)
    return split, history


def _tape_from_frame(frame: Any) -> list[dict[str, Any]]:
    """`upgrades_downgrades` → the newest `TAPE_LIMIT` rows, plain dicts.
    A zero price target means "no PT on this action" (yfinance's own
    convention — measured, Needham reiterations carry 0.0), normalised to
    None so it never renders as a $0 target."""
    if frame is None or getattr(frame, "empty", True):
        return []
    try:
        rows = frame.reset_index().head(TAPE_LIMIT).to_dict("records")
    except Exception:
        return []
    tape = []
    for row in rows:
        date_raw = row.get("GradeDate") or row.get("index")
        try:
            date = str(date_raw)[:10]
        except Exception:
            continue
        firm = str(row.get("Firm", "")).strip()
        if not firm or not date:
            continue
        tape.append({
            "date": date,
            "firm": firm,
            "to_grade": str(row.get("ToGrade", "")).strip(),
            "from_grade": str(row.get("FromGrade", "")).strip(),
            "action": str(row.get("Action", "")).strip(),
            "pt_action": str(row.get("priceTargetAction", "") or "").strip(),
            "current_pt": _pt(row.get("currentPriceTarget")),
            "prior_pt": _pt(row.get("priorPriceTarget")),
        })
    return tape


def _pt(value: Any) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def analyst_split_line(
    split: dict[str, int] | None,
    history: list[dict[str, Any]] | None = None,
) -> str | None:
    """The Fundamentals Analyst's line: the distribution with the analyst
    total it sums to, plus last month's split when the history carries it —
    "6 strong buy / 19 buy / 13 hold / 3 sell / 3 strong sell (44 analysts)"
    is the consensus word with its disagreement left in."""
    if not split:
        return None
    total = sum(split.values())
    line = (
        "Analyst rating split (LIVE, Street view): "
        f"{split['strong_buy']} strong buy / {split['buy']} buy / "
        f"{split['hold']} hold / {split['sell']} sell / "
        f"{split['strong_sell']} strong sell ({total} analysts)"
    )
    if history:
        prev = history[0]
        line += (
            f" — one month earlier: {prev['strong_buy']} / {prev['buy']} / "
            f"{prev['hold']} / {prev['sell']} / {prev['strong_sell']}"
        )
    return line


def analyst_tape_line(tape: list[dict[str, Any]] | None) -> str | None:
    """The News Analyst's line: the newest dated firm actions, bounded by
    `TAPE_LIMIT` at the fetch site. Reiterations without a PT render as a
    grade call only; Raises/Lowers carry the from→to pair."""
    if not tape:
        return None
    items = []
    for row in tape:
        item = f"{row['date']} {row['firm']} — {row['to_grade'] or 'rating change'}"
        if row.get("from_grade") and row["from_grade"] != row.get("to_grade"):
            item += f" (was {row['from_grade']})"
        move = (row.get("pt_action") or "").lower()
        current = row.get("current_pt")
        if move in ("raises", "lowers") and current is not None:
            item += f", {move} target to ${current:.0f}"
            prior = row.get("prior_pt")
            if prior is not None:
                item += f" from ${prior:.0f}"
        elif move == "maintains" and current is not None:
            item += f", target maintained at ${current:.0f}"
        items.append(item)
    return "Recent analyst actions (LIVE, real, dated): " + " · ".join(items)
