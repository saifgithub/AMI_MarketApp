"""CR172 — `max_loss_budget_usd` means "lose at most $X", at every caller.

The field used to be `risk_budget_usd` and its two callers read it two
different ways. `/propose` defaulted it to `portfolio_value x
single_name_cap_pct` — a POSITION-SIZE cap, how much to deploy. The Room
derived it from `drawdown_contribution`, the function the safety floor enforces
the drawdown cap with — a LOSS budget. Both handed it to `_size_to_budget`,
which divides by max loss either way, so on the same $10,000 book the same
field produced numbers ~28x apart and nothing in the name could catch it.

Saiful's ruling (2026-08-22): one meaning everywhere — **lose at most $X** —
and the name states it, so the next caller cannot guess wrong.

What these tests hold:
  * the default is derived as a loss, never as a position size;
  * given a stop, `/propose` converts through the SAME function the Room uses,
    so the two agree by construction rather than by comment;
  * without a stop it falls back to a figure that is already a loss in
    percentage points, never to `single_name_cap_pct`.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.api.options import _DEFAULT_MAX_LOSS_PCT, _default_max_loss_budget
from app.trading_math.risk import drawdown_contribution


def _mandate(*, single_name_cap_pct=20.0, max_open_risk_pct=2.0):
    return SimpleNamespace(
        single_name_cap_pct=single_name_cap_pct,
        max_open_risk_pct=max_open_risk_pct,
    )


def test_a_stop_converts_the_position_cap_into_a_loss():
    """The 28x case, with the numbers that made it.

    $10,000 book, a 20% single-name cap, entry $100, stop $93. The old default
    was the cap itself: $2,000. The loss that position actually risks is
    20% x 7% = 1.4 points = $140.
    """
    budget = _default_max_loss_budget(
        mandate=_mandate(), portfolio_value=10_000.0, spot=100.0, stop=93.0,
    )
    assert budget == 140.0
    assert budget != 2_000.0, "this is the position-size cap — the defect itself"


def test_it_converts_through_the_same_function_the_room_uses():
    """Agreement by construction: both sides go through `drawdown_contribution`.

    If /propose ever grew its own arithmetic, the two callers could drift apart
    again while both looking correct in isolation — which is exactly how the
    original 28x gap survived review.
    """
    contribution = drawdown_contribution(20.0, 100.0, 93.0)
    assert contribution is not None
    room_budget = round(10_000.0 * contribution.contribution_pts / 100.0, 2)

    propose_budget = _default_max_loss_budget(
        mandate=_mandate(), portfolio_value=10_000.0, spot=100.0, stop=93.0,
    )
    assert propose_budget == room_budget


def test_without_a_stop_it_falls_back_to_a_loss_figure_not_a_size_cap():
    """A position cap cannot become a loss without a stop, so do not pretend.

    `max_open_risk_pct` is already a loss in percentage points (CR129 derives
    it from the user's own `max_drawdown_pct`). Falling back to
    `single_name_cap_pct` here would reintroduce the substitution wholesale.
    """
    budget = _default_max_loss_budget(
        mandate=_mandate(single_name_cap_pct=20.0, max_open_risk_pct=2.0),
        portfolio_value=10_000.0, spot=100.0, stop=None,
    )
    assert budget == 200.0
    assert budget != 2_000.0


def test_a_wider_stop_costs_more_and_a_tighter_stop_costs_less():
    """Non-vacuity: the conversion must actually depend on the stop.

    A constant that happened to look right on one board would pass the tests
    above; this one fails unless the stop distance is really read.
    """
    tight = _default_max_loss_budget(
        mandate=_mandate(), portfolio_value=10_000.0, spot=100.0, stop=98.0,
    )
    wide = _default_max_loss_budget(
        mandate=_mandate(), portfolio_value=10_000.0, spot=100.0, stop=80.0,
    )
    assert tight < wide
    assert (tight, wide) == (40.0, 400.0)


def test_an_incoherent_stop_does_not_produce_a_bogus_loss():
    """A stop at or above spot yields no contribution — fall back, never invent.

    `drawdown_contribution` returns None rather than emitting a nonsense
    figure, and this path must honour that instead of computing something.
    """
    budget = _default_max_loss_budget(
        mandate=_mandate(max_open_risk_pct=2.0),
        portfolio_value=10_000.0, spot=100.0, stop=120.0,
    )
    assert budget == 200.0


def test_a_mandate_with_no_loss_figure_at_all_uses_the_stated_default():
    budget = _default_max_loss_budget(
        mandate=SimpleNamespace(single_name_cap_pct=20.0, max_open_risk_pct=None),
        portfolio_value=10_000.0, spot=None, stop=None,
    )
    assert budget == round(10_000.0 * _DEFAULT_MAX_LOSS_PCT / 100.0, 2)


def test_the_old_field_name_is_gone_from_the_request_model():
    """A caller still sending `risk_budget_usd` must not be silently ignored.

    Pydantic would drop an unknown field and fall through to the default,
    which is the quiet failure this rename exists to prevent.
    """
    from app.api.options import ProposeRequest

    assert "max_loss_budget_usd" in ProposeRequest.model_fields
    assert "risk_budget_usd" not in ProposeRequest.model_fields
