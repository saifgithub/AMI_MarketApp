"""DEF397 (dropped-draw leg) — a lost CIO draw is replaced, never silently dropped.

The CR219 R47 corpus (300 draws, 3 profiles) measured every observed verdict flip
as the same mechanism: an empty stream or unparseable reply shrank the 5-way vote
to an even survivor count, the 2-2 tie broke to PASS (DEF059's rule doing the
right thing on the wrong denominator), and the run reported agreement "4/4" as if
all five requested reads agreed. `_draw_pm_candidates` now runs one bounded
replacement round — at most `lost` extra draws, only when at least one original
stream answered (a dark provider stays DEF059's outage path) — and the runner
disclosure says so when the vote still runs short.

These tests drive the helper directly, the way test_cr197 drives the vote.
"""

from __future__ import annotations

import asyncio

from app.schemas.room import Verdict, VerdictAction
from app.services.room_runner import _draw_pm_candidates

_GOOD = '{"action": "APPROVE", "size_pct": 2.0}'
_BAD = "Let me pull the latest intelligence on this name..."  # never opens JSON


def _parse(text: str) -> tuple[str, Verdict | None]:
    if text == _GOOD:
        return ("n", Verdict(action=VerdictAction.APPROVE, size_pct=2.0, reason="r"))
    return (text, None)


def _drawer(replies: list[str]):
    """Async draw() that pops scripted replies in order and counts calls."""
    calls = {"n": 0}

    async def draw() -> str:
        calls["n"] += 1
        return replies.pop(0) if replies else _GOOD

    return draw, calls


def test_lost_draws_are_replaced_to_the_requested_denominator():
    draw, calls = _drawer([_GOOD, _GOOD, _GOOD, _BAD, _BAD])
    cands, raw, lost, recovered = asyncio.run(_draw_pm_candidates(5, draw, _parse))
    assert (len(cands), lost, recovered) == (5, 2, 2)
    assert calls["n"] == 7  # 5 originals + exactly `lost` replacements


def test_an_even_tie_from_loss_no_longer_occurs_when_replacements_parse():
    """The R47 shape: 5 requested, 1 lost, 4 survivors could tie 2-2. With the
    replacement round the vote is 5 again and a majority exists."""
    draw, _ = _drawer([_GOOD, _GOOD, _BAD, _BAD, _BAD])
    cands, _raw, lost, recovered = asyncio.run(_draw_pm_candidates(5, draw, _parse))
    assert len(cands) == 5 and lost == 3 and recovered == 3


def test_a_dark_provider_gets_no_replacement_round():
    """All streams empty = DEF059's outage path. Hammering a dead provider with
    five more requests helps nobody; the caller fails safe."""
    draw, calls = _drawer(["", "", "", "", ""])
    cands, raw, lost, recovered = asyncio.run(_draw_pm_candidates(5, draw, _parse))
    assert cands == [] and raw == "" and recovered == 0
    assert calls["n"] == 5  # no second round


def test_replacements_that_also_fail_leave_the_shortfall_visible():
    draw, _ = _drawer([_GOOD, _BAD, _BAD, _BAD, _BAD, _BAD, _BAD, _BAD, _BAD])
    cands, _raw, lost, recovered = asyncio.run(_draw_pm_candidates(5, draw, _parse))
    assert len(cands) == 1 and lost == 4 and recovered == 0


def test_first_raw_text_survives_for_the_def058_reformat_path():
    """All draws non-empty but unparseable: the DEF058 retry needs material."""
    draw, _ = _drawer([_BAD, _BAD, _BAD, _BAD, _BAD, _BAD, _BAD, _BAD, _BAD, _BAD])
    cands, raw, _lost, _rec = asyncio.run(_draw_pm_candidates(5, draw, _parse))
    assert cands == [] and raw == _BAD


def test_the_replacement_round_is_bounded_to_one():
    """Cost control: at most pm_samples + lost draws ever happen, even when the
    replacements themselves all fail."""
    draw, calls = _drawer([_BAD] * 10)
    asyncio.run(_draw_pm_candidates(5, draw, _parse))
    assert calls["n"] == 10  # 5 + 5, never a third round
