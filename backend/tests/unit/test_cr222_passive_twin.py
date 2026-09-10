"""CR222 §2 — the passive twin: same cash, same dates, never traded.

The acceptance case that pins the whole construction is
`test_a_never_traded_book_holding_only_the_twin_matches_it_to_the_cent`: a
portfolio whose only holding IS the twin instrument, never traded, must return
exactly what the twin returns on both measures. Anything else means the twin is
being built on a different grid, a different flow schedule, or a different
price basis than the book it is being compared to — and a benchmark that
disagrees with a portfolio identical to it is worse than no benchmark, because
every difference it reports afterwards is that disagreement plus noise.

The two degrade-loudly cases (`twin_unmapped`, `twin_history`) are the DEF059
shape: both would be trivially "fixable" by falling back to SPY, and both are
tested for the ABSENCE of SPY in the output as well as for the named cause.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.core.config import settings
from app.services.passive_twin import (
    DIFFERENCE_PRECISION_NO_SE,
    INSUFFICIENT_TWIN_HISTORY,
    INSUFFICIENT_TWIN_SHORT_WINDOW,
    INSUFFICIENT_TWIN_UNMAPPED,
    CashFlow,
    TwinInstrument,
    build_passive_twin,
    build_twin_block,
    irr,
    map_twin_instrument,
)
from app.services.portfolio_finding import (
    build_allowlist,
    build_stripped_context,
    render_deterministic_sections,
    validate_sections,
)

_START = date(2026, 1, 5)
_SPY = TwinInstrument(ticker="SPY", expense_ratio_pct=0.0945, halal=False)


def _grid(n: int) -> list[date]:
    """`n` consecutive MARKET days. Consecutive calendar dates stand in for a
    trading grid here on purpose: the twin's contract is that it shares whatever
    grid the NAV rows carry, so the grid's own shape is not what is under test —
    and a fixture that hand-rolled a holiday calendar would be testing the
    fixture."""
    return [_START + timedelta(days=i) for i in range(n)]


def _closes(dates, prices) -> dict[date, float]:
    return dict(zip(dates, prices))


def _flat(n: int, value: float) -> list[float]:
    return [value] * n


def _events(n: int, **at) -> list[str | None]:
    """`capital_events` with `open` at day 0 and whatever `at` names by index."""
    events: list[str | None] = [None] * n
    events[0] = "open"
    for index, event in at.items():
        events[int(index.lstrip("d"))] = event
    return events


class _Row:
    """The two fields `build_passive_twin` reads off a `PortfolioNavDailyRow`.

    A stand-in rather than the ORM row: the read path is CR109's own
    `nav_history`, which this test injects around, and constructing real rows
    would test the table's defaults instead of the twin's arithmetic.
    """

    def __init__(self, as_of_date, nav, capital_event=None):
        self.as_of_date = as_of_date
        self.nav = nav
        self.capital_event = capital_event


@pytest.fixture(autouse=True)
def _twin_on(monkeypatch):
    monkeypatch.setattr(settings, "portfolio_passive_twin_enabled", True)
    monkeypatch.setattr(settings, "passive_twin_default_ticker", "SPY")
    monkeypatch.setattr(settings, "passive_twin_halal_ticker", "")
    monkeypatch.setattr(settings, "passive_twin_default_expense_ratio_pct", 0.0945)
    monkeypatch.setattr(settings, "twin_min_market_days", 20)
    monkeypatch.setattr(settings, "twin_min_market_days_for_se", 60)


# ── (a) A book that IS the twin ─────────────────────────────────────────────


def test_a_never_traded_book_holding_only_the_twin_matches_it_to_the_cent():
    """THE acceptance case. One deposit, one holding, that holding is the twin,
    no trade ever — so both series are the same series and both measures must
    agree exactly, not approximately."""
    dates = _grid(80)
    prices = [400.0 * (1.0 + 0.001) ** i for i in range(80)]
    shares = 10_000.0 / prices[0]
    navs = [shares * p for p in prices]

    block = build_twin_block(
        nav_dates=dates,
        nav_values=navs,
        capital_events=_events(80),
        twin_closes=_closes(dates, prices),
        instrument=_SPY,
    )

    assert block["sufficient"] is True
    assert block["user_irr"] == pytest.approx(block["twin_irr"], abs=1e-9)
    assert block["user_twr"] == pytest.approx(block["twin_twr"], abs=1e-9)
    assert round(block["irr_difference"], 4) == 0.0
    assert round(block["twr_difference"], 4) == 0.0


def test_a_book_that_beats_the_twin_and_one_that_trails_it_have_one_shape():
    """CR131's honesty rule, structurally: the block's keys and its
    `difference_precision` do not depend on the sign of the difference. A shape
    that changed when the user was behind would be a verdict wearing a schema."""
    dates = _grid(80)
    prices = _flat(80, 400.0)
    closes = _closes(dates, prices)

    ahead = build_twin_block(
        nav_dates=dates, nav_values=[10_000.0] * 79 + [12_000.0],
        capital_events=_events(80), twin_closes=closes, instrument=_SPY,
    )
    behind = build_twin_block(
        nav_dates=dates, nav_values=[10_000.0] * 79 + [8_000.0],
        capital_events=_events(80), twin_closes=closes, instrument=_SPY,
    )

    assert set(ahead) == set(behind)
    assert ahead["difference_precision"] == behind["difference_precision"]
    assert ahead["irr_difference"] > 0.0 and behind["irr_difference"] < 0.0
    for block in (ahead, behind):
        for banned in ("grade", "verdict", "warning", "status", "rating"):
            assert banned not in block


# ── (b) A restart lands in both series on the same date ─────────────────────


def test_a_restart_deposit_lands_in_both_series_on_the_same_date():
    """`reset_portfolio()` destroys the book and re-stakes it; the twin has to
    do the same on the same day. A twin that kept compounding through the reset
    would be measuring against a portfolio the user no longer has."""
    dates = _grid(80)
    prices = _flat(80, 400.0)
    events = _events(80, d40="restart")
    navs = [10_000.0] * 40 + [7_500.0] * 40

    block = build_twin_block(
        nav_dates=dates, nav_values=navs, capital_events=events,
        twin_closes=_closes(dates, prices), instrument=_SPY,
    )

    assert block["sufficient"] is True
    # Flat prices: the twin returns nothing on either leg, so its TWR is exactly
    # zero — which is only true if the restart re-based it at 7,500 rather than
    # letting the original 10,000 stake run on.
    assert block["twin_twr"] == pytest.approx(0.0, abs=1e-12)
    # The user's own chain splits at the same row, so the 10,000 → 7,500 drop is
    # a capital event on both sides and appears as performance on neither.
    assert block["user_twr"] == pytest.approx(0.0, abs=1e-12)
    assert block["twr_difference"] == pytest.approx(0.0, abs=1e-12)


def test_the_restart_deposit_is_the_restart_rows_own_nav():
    """The twin's second stake is the fresh capital, not the pre-reset value.
    Pinned by making the two differ: a twin that re-deposited 10,000 would show
    a NAV a third larger than the book it shadows."""
    dates = _grid(80)
    prices = _flat(80, 100.0)
    events = _events(80, d40="restart")
    navs = [10_000.0] * 40 + [7_500.0] * 40

    block = build_twin_block(
        nav_dates=dates, nav_values=navs, capital_events=events,
        twin_closes=_closes(dates, prices), instrument=_SPY,
    )
    # Flat prices and an identical flow schedule: the twin's IRR must equal the
    # user's, which is only true when both re-staked the same 7,500.
    assert block["twin_irr"] == pytest.approx(block["user_irr"], abs=1e-9)


# ── (c) No price history ⇒ named cause, never SPY ───────────────────────────


def test_a_twin_ticker_with_no_price_history_is_insufficient_and_not_substituted():
    """DEF059's shape. The easy wrong answer is to serve SPY and say nothing;
    the block names the cause and carries no numbers at all."""
    dates = _grid(80)
    halal = TwinInstrument(ticker="SPUS", expense_ratio_pct=0.45, halal=True)

    block = build_twin_block(
        nav_dates=dates, nav_values=_flat(80, 10_000.0),
        capital_events=_events(80), twin_closes={}, instrument=halal,
    )

    assert block["sufficient"] is False
    assert block["insufficient_cause"] == INSUFFICIENT_TWIN_HISTORY
    assert block["twin_ticker"] == "SPUS"
    assert "SPY" not in repr(block)
    for numeric in ("user_irr", "user_twr", "twin_irr", "twin_twr",
                    "irr_difference", "twr_difference"):
        assert block[numeric] is None, numeric


def test_a_partial_history_hole_is_insufficient_rather_than_interpolated():
    """One missing close is enough. Filling it would put a fabricated price into
    a comparison whose entire value is that it is not fabricated."""
    dates = _grid(80)
    prices = _flat(80, 400.0)
    closes = _closes(dates, prices)
    del closes[dates[37]]

    block = build_twin_block(
        nav_dates=dates, nav_values=_flat(80, 10_000.0),
        capital_events=_events(80), twin_closes=closes, instrument=_SPY,
    )
    assert block["sufficient"] is False
    assert block["insufficient_cause"] == INSUFFICIENT_TWIN_HISTORY


# ── (d) Halal mandate, unconfigured halal ticker ────────────────────────────


class _Compliance:
    def __init__(self, halal):
        self.halal = halal


class _Mandate:
    def __init__(self, halal):
        self.compliance = _Compliance(halal)


def test_a_halal_mandate_with_no_configured_ticker_never_falls_back_to_spy(monkeypatch):
    """The named guard. `PASSIVE_TWIN_HALAL_TICKER` empty means nobody has
    chosen the Sharia-screened instrument yet — and benchmarking a halal user
    against an unscreened S&P 500 fund would show them a number their own
    mandate forbids them to hold, with nothing on the page saying so."""
    monkeypatch.setattr(settings, "passive_twin_halal_ticker", "")

    assert map_twin_instrument(_Mandate(halal=True)) is None

    dates = _grid(80)
    block = build_twin_block(
        nav_dates=dates, nav_values=_flat(80, 10_000.0),
        capital_events=_events(80), twin_closes={}, instrument=None,
    )
    assert block["sufficient"] is False
    assert block["insufficient_cause"] == INSUFFICIENT_TWIN_UNMAPPED
    assert block["twin_ticker"] is None
    assert "SPY" not in repr(block)


def test_a_configured_halal_ticker_is_used_and_carries_its_own_expense_ratio(monkeypatch):
    monkeypatch.setattr(settings, "passive_twin_halal_ticker", "spus")
    monkeypatch.setattr(settings, "passive_twin_halal_expense_ratio_pct", 0.45)

    instrument = map_twin_instrument(_Mandate(halal=True))
    assert instrument.ticker == "SPUS"
    assert instrument.expense_ratio_pct == 0.45
    assert instrument.halal is True


def test_a_non_halal_mandate_maps_to_the_default_ticker():
    instrument = map_twin_instrument(_Mandate(halal=False))
    assert instrument.ticker == "SPY"
    assert instrument.halal is False


def test_the_halal_marker_is_read_from_a_dict_mandate_too():
    """`compliance.halal` is the marker whether the mandate arrives as a model
    or as the stored JSONB dict."""
    assert map_twin_instrument({"compliance": {"halal": True}}) is None
    assert map_twin_instrument({"compliance": {"halal": False}}).ticker == "SPY"
    assert map_twin_instrument(None).ticker == "SPY"


# ── (e) Below the lower floor ───────────────────────────────────────────────


def test_below_twenty_market_days_the_block_is_insufficient_with_no_numbers():
    dates = _grid(19)
    prices = _flat(19, 400.0)

    block = build_twin_block(
        nav_dates=dates, nav_values=_flat(19, 10_000.0),
        capital_events=_events(19), twin_closes=_closes(dates, prices),
        instrument=_SPY,
    )
    assert block["sufficient"] is False
    assert block["insufficient_cause"] == INSUFFICIENT_TWIN_SHORT_WINDOW
    assert block["market_days"] == 19
    assert block["irr_difference"] is None


def test_a_series_with_no_capital_event_has_nothing_to_shadow():
    """No `open` and no `restart` means no deposit date and no deposit amount —
    the twin has no cash to be given and no day to be given it on. Naming that
    rather than assuming a stake at day zero: a NAV series with no capital event
    is a gap in the spine, and inventing the deposit would hide it."""
    dates = _grid(80)
    prices = _flat(80, 400.0)

    block = build_twin_block(
        nav_dates=dates, nav_values=_flat(80, 10_000.0),
        capital_events=[None] * 80, twin_closes=_closes(dates, prices),
        instrument=_SPY,
    )
    assert block["sufficient"] is False
    assert block["insufficient_cause"] == "twin_no_capital"
    assert block["twin_irr"] is None


def test_exactly_twenty_market_days_is_sufficient():
    """The floor is inclusive: 20 is the first measurable window, not the last
    refused one."""
    dates = _grid(20)
    prices = [400.0 + i for i in range(20)]

    block = build_twin_block(
        nav_dates=dates, nav_values=[10_000.0 + 25 * i for i in range(20)],
        capital_events=_events(20), twin_closes=_closes(dates, prices),
        instrument=_SPY,
    )
    assert block["sufficient"] is True


# ── (f) Between the floors: a difference, and no sampling error ─────────────


def test_between_twenty_and_sixty_days_the_difference_says_it_has_no_sampling_error():
    """There is no bootstrap in Portfolio Health and this CR does not build one
    (CR222 Corrections §6), so the honest thing is a machine state naming the
    absence rather than a silent point estimate."""
    dates = _grid(40)
    prices = [400.0 + i for i in range(40)]

    block = build_twin_block(
        nav_dates=dates, nav_values=[10_000.0 + 40 * i for i in range(40)],
        capital_events=_events(40), twin_closes=_closes(dates, prices),
        instrument=_SPY,
    )
    assert block["sufficient"] is True
    assert block["irr_difference"] is not None
    assert block["twr_difference"] is not None
    assert block["difference_precision"] == DIFFERENCE_PRECISION_NO_SE


def test_at_sixty_days_the_no_sampling_error_state_drops_away():
    dates = _grid(60)
    prices = [400.0 + i for i in range(60)]

    block = build_twin_block(
        nav_dates=dates, nav_values=[10_000.0 + 40 * i for i in range(60)],
        capital_events=_events(60), twin_closes=_closes(dates, prices),
        instrument=_SPY,
    )
    assert block["difference_precision"] != DIFFERENCE_PRECISION_NO_SE


# ── IRR ─────────────────────────────────────────────────────────────────────


def test_irr_on_a_doubling_over_one_year_is_one_hundred_percent():
    flows = [
        CashFlow(on=date(2026, 1, 1), amount=-1_000.0),
        CashFlow(on=date(2027, 1, 1), amount=2_000.0),
    ]
    assert irr(flows) == pytest.approx(1.0, abs=1e-6)


def test_irr_keeps_the_timing_a_time_weighted_return_throws_away():
    """The whole reason both measures ship. Two deposits, the second landing
    just before a rise: the money-weighted answer must be larger than the
    equally-weighted one, or the measure is not doing its job."""
    flows_late = [
        CashFlow(on=date(2026, 1, 1), amount=-1_000.0),
        CashFlow(on=date(2026, 11, 1), amount=-9_000.0),
        CashFlow(on=date(2027, 1, 1), amount=11_500.0),
    ]
    flows_early = [
        CashFlow(on=date(2026, 1, 1), amount=-9_000.0),
        CashFlow(on=date(2026, 11, 1), amount=-1_000.0),
        CashFlow(on=date(2027, 1, 1), amount=11_500.0),
    ]
    assert irr(flows_late) > irr(flows_early)


def test_irr_refuses_a_schedule_with_no_sign_change():
    assert irr([CashFlow(on=date(2026, 1, 1), amount=-100.0)]) is None
    assert irr([
        CashFlow(on=date(2026, 1, 1), amount=-100.0),
        CashFlow(on=date(2026, 6, 1), amount=-100.0),
    ]) is None


def test_irr_is_deterministic_across_repeated_calls():
    """Bit-identical, not merely close: the acceptance case compares a book to
    its own twin and a solver with any nondeterminism would make that
    comparison a coin flip at the last decimal."""
    flows = [
        CashFlow(on=date(2026, 1, 1), amount=-4_321.0),
        CashFlow(on=date(2026, 7, 14), amount=-1_234.0),
        CashFlow(on=date(2027, 3, 2), amount=6_789.0),
    ]
    assert len({irr(flows) for _ in range(20)}) == 1


# ── (g) The rendered block through the closed allow-list ────────────────────


def _rendered(twin_block):
    """The twin block inside a minimal real context, through the deterministic
    renderer and the closed validator — the same path a Finding takes."""
    metric_blocks = [{
        "metric": "weight_concentration",
        "value": 0.34,
        "standard_error": None,
        "n_observations": 200,
        "t_eff": None,
        "window_days": 300,
        "sufficient": True,
        "partial": False,
        "dropped_holdings": [],
        "low_explanatory_power": None,
        "contains_etfs": False,
        "backcast": True,
        "basis": "weights",
        "engine_version": "test",
        "insufficient_cause": None,
        "effective_n": 2.9,
        "holdings_count": 4,
    }]
    context = build_stripped_context(metric_blocks, as_of="2026-03-26")
    if twin_block is not None:
        context["passive_twin"] = twin_block
    sections = render_deterministic_sections(context, [])
    return context, sections


def test_the_rendered_twin_block_has_zero_unregistered_numbers():
    dates = _grid(80)
    prices = [400.0 * (1.0 + 0.0007) ** i for i in range(80)]
    navs = [10_000.0 * (1.0 + 0.0011) ** i for i in range(80)]

    block = build_twin_block(
        nav_dates=dates, nav_values=navs, capital_events=_events(80),
        twin_closes=_closes(dates, prices), instrument=_SPY,
    )
    context, sections = _rendered(block)

    assert "held passively" in sections["f3"]
    assert "SPY" in sections["f3"]
    assert validate_sections(sections, build_allowlist(context, [])) is None


def test_the_expense_ratio_renders_at_its_own_precision_and_validates():
    """0.0945% is basis points wearing a percent sign. At the dp ladder's floor
    it reads "0.09%", a fee 5% lighter than the real one — so the renderer keeps
    four places and the allow-list admits exactly what the renderer writes."""
    dates = _grid(80)
    prices = _flat(80, 400.0)

    block = build_twin_block(
        nav_dates=dates, nav_values=_flat(80, 10_000.0),
        capital_events=_events(80), twin_closes=_closes(dates, prices),
        instrument=_SPY,
    )
    context, sections = _rendered(block)
    assert "0.0945%" in sections["f3"]
    assert validate_sections(sections, build_allowlist(context, [])) is None


def test_an_insufficient_twin_renders_its_machine_state_and_still_validates():
    dates = _grid(19)
    block = build_twin_block(
        nav_dates=dates, nav_values=_flat(19, 10_000.0),
        capital_events=_events(19), twin_closes={}, instrument=_SPY,
    )
    context, sections = _rendered(block)
    assert INSUFFICIENT_TWIN_SHORT_WINDOW in sections["f3"]
    assert validate_sections(sections, build_allowlist(context, [])) is None


def test_the_twin_block_carries_no_grade_no_warning_no_verdict():
    """CR131's honesty rules, checked on the RENDERED text rather than only on
    the payload — the payload is not what a user reads."""
    dates = _grid(40)
    prices = [400.0 - i for i in range(40)]

    block = build_twin_block(
        nav_dates=dates, nav_values=[10_000.0 - 60 * i for i in range(40)],
        capital_events=_events(40), twin_closes=_closes(dates, prices),
        instrument=_SPY,
    )
    _context, sections = _rendered(block)
    twin_text = sections["f3"].lower()
    for banned in (
        "underperform", "outperform", "you should", "well done", "poor",
        "good", "bad", "beat the market", "lagging", "the ai",
    ):
        assert banned not in twin_text, banned


# ── (h) Flag off ⇒ the block is absent entirely ─────────────────────────────


def test_flag_off_returns_no_block_at_all(monkeypatch):
    monkeypatch.setattr(settings, "portfolio_passive_twin_enabled", False)
    assert build_passive_twin(uuid4(), mandate=_Mandate(halal=False)) is None


def test_flag_off_leaves_the_rendered_report_free_of_the_twin():
    """An ABSENT block, not an insufficient one: with the flag off the report
    must read exactly as it did before this CR."""
    _context, sections = _rendered(None)
    assert "held passively" not in sections["f3"]
    assert "passive" not in sections["f3"].lower()


def test_flag_on_with_injected_nav_rows_builds_a_block(monkeypatch):
    """The read seam: `build_passive_twin` resolves its own series through
    CR109's accessor, and the injected rows stand in for it. The twin ticker has
    no stored history in a fresh test DB, so the honest answer here is the named
    cause — which is also the point: no SPY prices, no SPY numbers."""
    dates = _grid(80)
    rows = [
        _Row(d, 10_000.0, "open" if i == 0 else None)
        for i, d in enumerate(dates)
    ]
    block = build_passive_twin(
        uuid4(), mandate=_Mandate(halal=False), nav_rows=rows,
    )
    assert block is not None
    assert block["sufficient"] is False
    assert block["insufficient_cause"] == INSUFFICIENT_TWIN_HISTORY
