"""CR260 / CR267 WP-21b — the Street comparison, computed after the verdict.

The Room decides blind (CR275: `street_view_blind` strips every `analyst_*`
field from every agent input). Once the verdict exists, this module sets it
against the sell-side consensus rating so the user can see where the Room and
the Street part. Analyst consensus is the programme's reference for "correct":
a reasoned PASS on a Street-Buy name is acceptable; APPROVING a name the Street
rates Sell/Underperform is the error, flagged as `approved_against_street_sell`.

One pure function, called once at the bank site
(`room_runner._stamp_next_convene_basis`). It reads the fact sheet; it never
writes to it, and nothing it returns is read by any prompt builder
(`tests/unit/test_cr260_street_comparison.py` pins both).

Degrade loudly (CR040): no usable rating -> an explicit `unavailable` block with
a reason, never an empty or zero rating shown as if real. The "why the Room
differs" reasons come from WP-22's narrow-question judge, which does not exist
yet, so `reasons_from_narrow_answers` is always empty here and is never filled
by an LLM or by prose.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import logger
from app.schemas.room import StreetComparison, Verdict, VerdictAction
from app.services.street_view_blind import STREET_VIEW_PREFIX

# Names the feed. A source swap (CR260 §6: Benzinga as the licensed path) changes
# this one line; the app displays whatever the backend sends.
STREET_SOURCE_LABEL = "Yahoo Finance via yfinance: sell-side analyst consensus"

# yfinance `recommendationKey` values, lower-cased with "_" already turned into a
# space by `fundamentals.fetch_live_fundamentals`.
_STANCE_BY_RATING: dict[str, str] = {
    "strong buy": "buy",
    "buy": "buy",
    "hold": "hold",
    "underperform": "sell",
    "sell": "sell",
    "strong sell": "sell",
}

_LIVE = "live"


def _room_stance(action: str) -> str:
    if action in (VerdictAction.APPROVE.value, VerdictAction.MODIFY.value):
        return "approve"
    if action in (VerdictAction.PASS.value, VerdictAction.REJECT.value):
        return "decline"
    return "no_call"


def _agreement(room_stance: str, street_stance: str) -> str:
    if room_stance == "no_call":
        return "not_comparable"
    if street_stance == "buy":
        return "agree" if room_stance == "approve" else "differ"
    return "agree" if room_stance == "decline" else "differ"


def _unavailable(
    action: str, reason: str, as_of: str | None = None,
) -> StreetComparison:
    return StreetComparison(
        status="unavailable",
        source_label=STREET_SOURCE_LABEL,
        unavailable_reason=reason,
        as_of=as_of,
        room_action=action,
        room_stance=_room_stance(action),  # type: ignore[arg-type]
        agreement="not_comparable",
    )


def build_street_comparison(
    verdict: Verdict, profile: dict[str, Any],
) -> StreetComparison:
    """The Street comparison for a finished verdict. Never raises."""
    action = str(getattr(verdict.action, "value", verdict.action))
    try:
        return _build(action, profile)
    except Exception as exc:  # CR040 — loud in the log, honest on the card
        logger.error("street_comparison_error", error=str(exc)[:200])
        return _unavailable(action, "comparison_error")


def _build(action: str, profile: dict[str, Any]) -> StreetComparison:
    state = profile.get("field_state") or {}
    as_of = (
        str(profile["run_date"])
        if state.get("run_date") == _LIVE and profile.get("run_date")
        else None
    )
    rating_key = f"{STREET_VIEW_PREFIX}rating"
    if state.get(rating_key) != _LIVE or not profile.get(rating_key):
        return _unavailable(action, "no_rating", as_of)
    rating = str(profile[rating_key]).strip().lower()
    stance = _STANCE_BY_RATING.get(rating)
    if stance is None:
        return _unavailable(action, "unrecognised_rating", as_of)

    count_key = f"{STREET_VIEW_PREFIX}opinion_count"
    count: int | None = None
    if state.get(count_key) == _LIVE and profile.get(count_key) is not None:
        count = int(profile[count_key])
        if count <= 0:
            # A rating with no analysts behind it is not a consensus.
            return _unavailable(action, "no_analysts", as_of)

    target_key = f"{STREET_VIEW_PREFIX}target_price"
    target: float | None = None
    if state.get(target_key) == _LIVE and profile.get(target_key) is not None:
        value = float(profile[target_key])
        target = value if value > 0 else None

    room_stance = _room_stance(action)
    return StreetComparison(
        status="available",
        source_label=STREET_SOURCE_LABEL,
        street_rating=rating,
        street_stance=stance,  # type: ignore[arg-type]
        analyst_count=count,
        target_mean=target,
        as_of=as_of,
        room_action=action,
        room_stance=room_stance,  # type: ignore[arg-type]
        agreement=_agreement(room_stance, stance),  # type: ignore[arg-type]
        approved_against_street_sell=room_stance == "approve" and stance == "sell",
    )
