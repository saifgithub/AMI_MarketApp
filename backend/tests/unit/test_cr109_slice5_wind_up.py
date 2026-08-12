"""CR109 slice 5 — the Wind-Up, §10's LOSS ceremony.

*"A blowup gets a dignified post-mortem with real numbers and immediate
re-entry — never a fail screen. Losing must be a chapter, not an ending."*

Four properties, each of which is what makes it a ceremony rather than a
failure state:

1. **It is decided on the server.** The threshold governs the TONE of the
   highest-attention screen in the product; duplicated on the client it will
   eventually disagree with itself and show confetti over a wipeout.
2. **Its numbers are the closing numbers.** Attribution is frozen by the
   scoring pass, so the post-mortem's *"real numbers"* never drift as the
   market moves on.
3. **It never takes the free Close away.** §10.2 fence 1 — rank, delta,
   curve, counterfactuals, markers and re-entry all survive, so the Wind-Up
   adds a ceremony rather than replacing one.
4. **The way back in still ships.** §10.3 — the loop-back is the entire
   point; a loss screen without it is the fail screen the design forbids.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import GameEntryRow, GameFieldRow, PortfolioNavDailyRow
from app.schemas.trade import Side
from app.services import games_record_service as record_service
from app.services import games_scoring, games_scoring_pass as pass_module
from app.services import games_service as games

_ENTRY_OPEN_CLOSED_MARKET = datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)
_MARKET_OPEN = datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)
_STARTS_ON = date(2026, 8, 10)
_MID = date(2026, 8, 12)
_ENDS_ON = date(2026, 8, 14)
_AFTER_CLOSE = datetime(2026, 8, 17, 15, 0, tzinfo=timezone.utc)


# ── The trigger, as pure math ────────────────────────────────────────────


def test_a_busted_run_is_always_a_wind_up():
    """Amendment I — the book went below zero and the run was stopped. There
    is no return figure that makes that an ordinary close."""
    assert games_scoring.is_wind_up(busted=True, final_twr_pct=0.0) is True


def test_a_heavy_loss_is_a_wind_up_without_a_bust():
    assert games_scoring.is_wind_up(busted=False, final_twr_pct=-20.0) is True
    assert games_scoring.is_wind_up(
        busted=False, final_twr_pct=games_scoring.WIND_UP_LOSS_PCT,
    ) is True


def test_an_ordinary_loss_is_not_a_wind_up():
    """Down 3% is a bad week, not a blowup. Handing it the loss ceremony
    would make the ceremony meaningless and the week feel worse than it was."""
    assert games_scoring.is_wind_up(busted=False, final_twr_pct=-3.0) is False


def test_an_unmeasured_run_is_never_a_wind_up():
    """A VOID run has no result to hold a post-mortem over."""
    assert games_scoring.is_wind_up(busted=False, final_twr_pct=None) is False


# ── The Close payload ────────────────────────────────────────────────────


def _closed_run(*, end_nav: float, bust: bool = False):
    user_id = uuid4()
    entry = games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=5,
        now=_MARKET_OPEN,
    )
    for as_of, nav, ev in (
        (_STARTS_ON, 10_000.0, "open"),
        (_MID, (10_000.0 + end_nav) / 2, None),
        (_ENDS_ON, end_nav, None),
    ):
        with get_session() as s:
            s.add(PortfolioNavDailyRow(
                user_id=user_id, run_id=entry.run_id, as_of_date=as_of, nav=nav,
                cash=nav, price_source="live", capital_event=ev,
            ))
    with get_session() as s:
        field = s.execute(
            select(GameFieldRow).where(GameFieldRow.id == entry.field_id)
        ).scalar_one()
        field.state = "live"
        if bust:
            row = s.execute(
                select(GameEntryRow).where(GameEntryRow.id == entry.id)
            ).scalar_one()
            row.busted_at = _AFTER_CLOSE
            row.nav_shortfall = 240.0
    pass_module.run_scoring_pass(now=_AFTER_CLOSE)
    return user_id, entry.run_id


def test_a_heavy_loss_closes_into_the_wind_up():
    user_id, run_id = _closed_run(end_nav=7_500.0)

    close = record_service.get_close_payload(user_id, run_id)

    assert close["wind_up"] is not None
    assert close["wind_up"]["reason"] == "heavy_loss"
    assert close["wind_up"]["final_twr_pct"] <= games_scoring.WIND_UP_LOSS_PCT


def test_a_bust_names_itself_and_states_the_shortfall():
    """Amendment I stores how far past zero the book went precisely so the
    floored NAV does not swallow it. The ceremony is where it gets said."""
    user_id, run_id = _closed_run(end_nav=1.0, bust=True)

    close = record_service.get_close_payload(user_id, run_id)

    assert close["wind_up"]["reason"] == "busted"
    assert close["wind_up"]["nav_shortfall"] == 240.0


def test_an_ordinary_close_carries_no_wind_up():
    user_id, run_id = _closed_run(end_nav=10_200.0)

    close = record_service.get_close_payload(user_id, run_id)

    assert close["wind_up"] is None


def test_the_wind_up_takes_the_insight_slot():
    """§10.2's priority: the post-mortem outranks the near-miss and the
    counterfactual. A player whose run went to zero must not be handed "if
    you'd held the index" as their one insight."""
    user_id, run_id = _closed_run(end_nav=7_500.0)

    close = record_service.get_close_payload(user_id, run_id)

    assert close["beats"]["insight"]["kind"] == "post_mortem"


def test_the_free_close_survives_the_wind_up_intact():
    """§10.2 fence 1 — nothing is removed to make room for the ceremony."""
    user_id, run_id = _closed_run(end_nav=7_500.0)

    close = record_service.get_close_payload(user_id, run_id)

    assert close["beats"]["result"]["final_twr_pct"] is not None
    assert close["curve"]
    assert close["debrief"]["counterfactual_hold_index_pct"] is not None
    assert close["beats"]["re_entry"] is not None, "§10.3 — the way back in"


def test_the_post_mortem_names_the_position_that_did_it():
    """*"Real numbers"* — the biggest negative contributor, read from the
    attribution frozen at close rather than recomputed at today's prices."""
    user_id, run_id = _closed_run(end_nav=7_500.0)

    close = record_service.get_close_payload(user_id, run_id)

    worst = close["wind_up"]["worst"]
    assert worst is not None
    assert worst["ticker"] == "AAPL"
    assert worst["pct_points"] < 0


def test_attribution_is_frozen_on_the_entry_at_close():
    user_id, run_id = _closed_run(end_nav=7_500.0)

    with get_session() as s:
        stored = s.execute(
            select(GameEntryRow.attribution).where(GameEntryRow.run_id == run_id)
        ).scalar_one()

    assert stored
    assert stored[0]["ticker"] == "AAPL"


def test_a_run_with_no_attribution_still_winds_up():
    """A run closed before this slice shipped carries no attribution. The
    ceremony must still run — with an honest gap where the number was, never
    a figure reconstructed from today's prices."""
    user_id, run_id = _closed_run(end_nav=7_500.0)
    with get_session() as s:
        row = s.execute(
            select(GameEntryRow).where(GameEntryRow.run_id == run_id)
        ).scalar_one()
        row.attribution = None

    close = record_service.get_close_payload(user_id, run_id)

    assert close["wind_up"] is not None
    assert close["wind_up"]["worst"] is None


def test_the_payload_carries_no_copy():
    """Every word the player reads is an ARB string. Copy shipped from the
    server cannot be translated or held to §10.4's "never scolds" rule."""
    user_id, run_id = _closed_run(end_nav=7_500.0)

    wind_up = record_service.get_close_payload(user_id, run_id)["wind_up"]

    for key, value in wind_up.items():
        assert not (isinstance(value, str) and " " in value), (
            f"{key} looks like a sentence, not a datum: {value!r}"
        )
