"""CR164 — the historical fact sheet carries what a past date can support,
and says so where it cannot.

Three things are pinned here.

**The derived fields are right.** Ten quarters of hand-built facts and 260
hand-built bars produce known values, and the self-consistency identities hold:
`base_price / trailing_eps` must equal the printed `pe`, and
`market_cap / revenue_ttm` must equal `price_to_sales`. Those identities are
the reason EPS is derived from the same numerator and denominator as the
multiple rather than imported from a reported per-share tag — a sheet whose
own figures do not divide into each other is the DEF302 class of defect.

**The filed-date cutoff still holds for every NEW field.** Parametrised per
field rather than asserted once: the cutoff rides on a single WHERE clause in
`load_facts`, and a future refactor that adds a second read path would only be
caught field by field.

**Absence is declared, not silent.** `_historical_mode_line` names what a past
date cannot carry, lane-filtered, and never fires on a live sheet.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.db import get_session
from app.db.models import EdgarFactRow, PriceHistoryDailyRow
from app.schemas.agents import AgentId
from app.services import edgar_pit, edgar_tags
from app.services.edgar_pit import _FactView, fetch_pit_fundamentals, margin_trend_bps
from app.services.room_prompts import _format_profile

_NOW = datetime(2026, 8, 19, tzinfo=timezone.utc)
_AS_OF = date(2025, 6, 6)
_TICKER = "PITX"

# Quarter ends, oldest first; the last four are the TTM window at _AS_OF.
_QUARTER_ENDS = [
    date(2023, 6, 30), date(2023, 9, 30), date(2023, 12, 31),
    date(2024, 3, 31), date(2024, 6, 30), date(2024, 9, 30),
    date(2024, 12, 31), date(2025, 3, 31),
]


def _add_duration(session, tag: str, per_quarter: dict[date, float], filed_offset: int = 40) -> None:
    for i, end in enumerate(_QUARTER_ENDS):
        if end not in per_quarter:
            continue
        start = _QUARTER_ENDS[i - 1] + \
            (date(1, 1, 2) - date(1, 1, 1)) if i else date(2023, 4, 1)
        session.add(EdgarFactRow(
            cik=1, ticker=_TICKER, taxonomy="us-gaap", tag=tag, unit="USD",
            value=per_quarter[end], period_start=start, period_end=end,
            filed=end + (date(1, 2, 10) - date(1, 1, 1)), accession_no=f"{tag}-{end}",
            ingested_at=_NOW,
        ))


def _add_instant(session, tag: str, value: float, *, end: date = date(2025, 3, 31)) -> None:
    session.add(EdgarFactRow(
        cik=1, ticker=_TICKER, taxonomy="us-gaap", tag=tag, unit="USD",
        value=value, period_start=None, period_end=end,
        filed=end + (date(1, 2, 10) - date(1, 1, 1)), accession_no=f"{tag}-{end}",
        ingested_at=_NOW,
    ))


@pytest.fixture
def seeded() -> None:
    """A whole filer: 8 quarters of flows, a balance sheet, shares, 260 bars."""
    M = 1_000_000.0  # a real filer's magnitudes, so the $M roundings mean something
    rev = {e: v * M for e, v in zip(_QUARTER_ENDS, [800, 850, 900, 950, 1000, 1050, 1100, 1200])}
    ni = {e: v * M for e, v in zip(_QUARTER_ENDS, [80, 85, 90, 95, 100, 105, 110, 132])}
    op = {e: v * M for e, v in zip(_QUARTER_ENDS, [100, 106, 112, 118, 125, 131, 138, 165])}
    gross = {e: v * M for e, v in zip(_QUARTER_ENDS, [320, 340, 360, 380, 400, 420, 440, 480])}
    ocf = {e: 150.0 * M for e in _QUARTER_ENDS}
    capex = {e: 50.0 * M for e in _QUARTER_ENDS}
    divs = {e: 20.0 * M for e in _QUARTER_ENDS}
    buyback = {e: 30.0 * M for e in _QUARTER_ENDS}
    with get_session() as s:
        _add_duration(s, "Revenues", rev)
        _add_duration(s, "NetIncomeLoss", ni)
        _add_duration(s, "OperatingIncomeLoss", op)
        _add_duration(s, "GrossProfit", gross)
        _add_duration(s, "NetCashProvidedByUsedInOperatingActivities", ocf)
        _add_duration(s, "PaymentsToAcquirePropertyPlantAndEquipment", capex)
        _add_duration(s, "PaymentsOfDividendsCommonStock", divs)
        _add_duration(s, "PaymentsForRepurchaseOfCommonStock", buyback)
        _add_instant(s, "CashAndCashEquivalentsAtCarryingValue", 500.0 * M)
        _add_instant(s, "LongTermDebtNoncurrent", 300.0 * M)
        _add_instant(s, "StockholdersEquity", 2_000.0 * M)
        _add_instant(s, "Assets", 4_000.0 * M)
        _add_instant(s, "AssetsCurrent", 1_500.0 * M)
        _add_instant(s, "LiabilitiesCurrent", 750.0 * M)
        _add_instant(s, "InventoryNet", 250.0 * M)
        s.add(EdgarFactRow(
            cik=1, ticker=_TICKER, taxonomy="dei", unit="shares",
            tag="EntityCommonStockSharesOutstanding", value=100.0 * M,
            period_start=None, period_end=date(2025, 3, 31), filed=date(2025, 5, 10),
            accession_no="dei-1", ingested_at=_NOW,
        ))
        # 260 sessions ending exactly on the as-of date, price climbing 100 → 360.
        d, made = _AS_OF, []
        while len(made) < 260:
            if d.weekday() < 5:
                made.append(d)
            d = date.fromordinal(d.toordinal() - 1)
        for i, bar_date in enumerate(reversed(made)):
            px = 100.0 + i
            s.add(PriceHistoryDailyRow(
                ticker=_TICKER, date=bar_date, close=px, adj_close=px,
                open=px - 0.5, high=px + 1.0, low=px - 1.0, volume=1_000_000 + i,
                source="yfinance_backfill", fetched_at=_NOW,
            ))
        for i, bar_date in enumerate(reversed(made)):
            s.add(PriceHistoryDailyRow(
                ticker="SPY", date=bar_date, close=500.0 + i * 0.5,
                adj_close=500.0 + i * 0.5, open=500.0, high=501.0, low=499.0,
                volume=9_000_000, source="yfinance_backfill", fetched_at=_NOW,
            ))


# ── Derived values ──────────────────────────────────────────────────────────


def test_the_fields_the_live_sheet_grew_are_now_reconstructed(seeded) -> None:
    out = fetch_pit_fundamentals(_TICKER, _AS_OF)
    assert out is not None
    # TTM over the last four quarters: rev 4350, ni 447, op 559, gross 1740.
    assert out["revenue_ttm"] == 4350
    assert out["market_cap"] == round(359.0 * 100)
    assert out["shares_outstanding"] == 100
    assert out["total_cash"] == 500
    assert out["total_debt"] == 300
    assert out["free_cash_flow"] == 400
    assert out["trailing_eps"] == round(447 / 100, 2)
    assert out["revenue_per_share"] == round(4350 / 100, 2)
    assert out["operating_margin"] == pytest.approx(round(559 / 4350 * 100))
    assert out["gross_margin"] == pytest.approx(round(1740 / 4350 * 100))
    assert out["return_on_equity"] == pytest.approx(round(447 / 2000 * 100))
    assert out["return_on_assets"] == pytest.approx(round(447 / 4000 * 100))
    assert out["debt_to_equity"] == round(300 / 2000, 2)
    assert out["current_ratio"] == round(1500 / 750, 2)
    assert out["quick_ratio"] == round((1500 - 250) / 750, 2)
    assert out["buyback_ttm"] == 120
    assert out["payout_ratio"] == pytest.approx(round(80 / 447 * 100))


def test_the_sheet_divides_into_itself(seeded) -> None:
    """The identity that makes deriving EPS from the P/E's own numerator the
    right call: a reader can check the sheet against itself."""
    out = fetch_pit_fundamentals(_TICKER, _AS_OF)
    assert float(out["pe"]) == pytest.approx(
        out["base_price"] / out["trailing_eps"], abs=0.15
    )
    assert float(out["price_to_sales"]) == pytest.approx(
        out["market_cap"] / out["revenue_ttm"], abs=0.15
    )
    assert out["net_cash"] == out["total_cash"] - out["total_debt"]


def test_price_derived_fields_come_off_the_stored_bars(seeded) -> None:
    out = fetch_pit_fundamentals(_TICKER, _AS_OF)
    assert out["day_change_pct"] == pytest.approx(round((359 / 358 - 1) * 100, 2))
    assert out["market_state"] == "CLOSED"
    assert out["volume_today"] == 1_000_000 + 259
    assert out["sma_200"] == pytest.approx(sum(range(160, 360)) / 200, abs=0.5)
    assert out["volume_avg_3m"] == int(sum(1_000_000 + i for i in range(195, 260)) / 65)
    # SPY rose 0.5/session against the ticker's 1.0, so relative strength is positive.
    assert out["change_52w_pct"] > 0
    assert out["relative_strength_52w_pct"] == pytest.approx(
        out["change_52w_pct"] - out["change_52w_sp500_pct"], abs=0.2
    )


def test_a_holiday_as_of_does_not_claim_todays_move(seeded) -> None:
    """The newest bar is then an earlier session, and calling its move
    'today's' would be wrong by a day."""
    out = fetch_pit_fundamentals(_TICKER, date(2025, 6, 7))  # a Saturday
    assert "day_change_pct" not in out
    assert "volume_today" not in out
    assert "market_state" not in out
    assert "sma_200" in out  # the window itself is still valid


# ── The cutoff, per new field ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "field,tag,later_value",
    [
        ("gross_margin", "GrossProfit", 4_000.0),
        ("return_on_equity", "StockholdersEquity", 1.0),
        ("return_on_assets", "Assets", 1.0),
        ("current_ratio", "AssetsCurrent", 999_999.0),
        ("buyback_ttm", "PaymentsForRepurchaseOfCommonStock", 900_000.0),
    ],
)
def test_a_fact_filed_after_the_as_of_never_reaches_the_sheet(
    seeded, field: str, tag: str, later_value: float,
) -> None:
    with get_session() as s:
        s.add(EdgarFactRow(
            cik=1, ticker=_TICKER, taxonomy="us-gaap", tag=tag, unit="USD",
            value=later_value, period_start=date(2025, 4, 1),
            period_end=date(2025, 6, 30), filed=date(2025, 8, 1),
            accession_no=f"future-{tag}", ingested_at=_NOW,
        ))
    before = fetch_pit_fundamentals(_TICKER, _AS_OF)
    assert before is not None
    # The future filing is louder than every seeded value, so if it leaked the
    # field would move. It must not.
    baseline = {
        "gross_margin": 40, "return_on_equity": 22, "return_on_assets": 11,
        "current_ratio": 2.0, "buyback_ttm": 120,
    }[field]
    assert before[field] == pytest.approx(baseline, abs=1.5)


def test_a_field_whose_only_fact_is_in_the_future_is_absent_not_zero() -> None:
    with get_session() as s:
        s.add(PriceHistoryDailyRow(
            ticker="FUTX", date=date(2025, 6, 5), close=10.0, adj_close=10.0,
            open=9.0, high=11.0, low=9.0, volume=1000,
            source="yfinance_backfill", fetched_at=_NOW,
        ))
        s.add(EdgarFactRow(
            cik=2, ticker="FUTX", taxonomy="us-gaap", tag="Assets", unit="USD",
            value=5_000.0, period_start=None, period_end=date(2025, 6, 30),
            filed=date(2025, 8, 1), accession_no="fut-1", ingested_at=_NOW,
        ))
    out = fetch_pit_fundamentals("FUTX", _AS_OF)
    assert out is not None
    assert "return_on_assets" not in out


# ── Margin trend ────────────────────────────────────────────────────────────


def test_margin_trend_is_bps_and_names_its_two_quarters() -> None:
    ni = [(date(2024, 4, 1), date(2024, 6, 30), 10.0),
          (date(2025, 4, 1), date(2025, 6, 30), 12.0)]
    rev = [(date(2024, 4, 1), date(2024, 6, 30), 100.0),
           (date(2025, 4, 1), date(2025, 6, 30), 110.0)]
    bps, basis = margin_trend_bps(ni, rev, date(2025, 8, 1))
    assert bps == round((12 / 110 - 10 / 100) * 10_000)
    assert basis == "2025-06-30 vs 2024-06-30"


def test_a_mismatched_denominator_quarter_is_refused_not_paired() -> None:
    ni = [(date(2024, 4, 1), date(2024, 6, 30), 10.0),
          (date(2025, 4, 1), date(2025, 6, 30), 12.0)]
    rev = [(date(2024, 4, 1), date(2024, 6, 29), 100.0),
           (date(2025, 4, 1), date(2025, 6, 29), 110.0)]
    assert margin_trend_bps(ni, rev, date(2025, 8, 1)) is None


def test_growth_still_means_what_it_meant_after_the_refactor() -> None:
    """`yoy_quarter_growth` is now expressed on `yoy_quarter_pair`; the
    regression pin is that its answer did not move."""
    quarters = [(date(2024, 4, 1), date(2024, 6, 30), 100.0),
                (date(2025, 4, 1), date(2025, 6, 30), 110.0)]
    assert edgar_pit.yoy_quarter_growth(quarters, date(2025, 8, 1)) == pytest.approx(0.10)


# ── Declared absence ────────────────────────────────────────────────────────


def _sheet(historical: bool, agent: AgentId | None) -> str:
    profile = {
        "ticker": "AAA", "field_state": {"run_date": "live"},
        "run_date": "2025-06-06", "historical_mode": historical,
    }
    return _format_profile(profile, agent)


def test_a_historical_sheet_says_what_a_past_date_cannot_carry() -> None:
    s = _sheet(True, AgentId.FUNDAMENTALS_ANALYST)
    assert "HISTORICAL MODE" in s
    assert "analyst consensus" in s
    assert "not a\ndivision of labour" in s or "not a division of labour" in s


def test_the_declaration_is_lane_filtered() -> None:
    fundamentals = _sheet(True, AgentId.FUNDAMENTALS_ANALYST)
    market = _sheet(True, AgentId.MARKET_ANALYST)
    tail = fundamentals.split("HISTORICAL MODE")[1]
    assert "beta" not in tail
    assert "short interest" not in tail
    market_tail = market.split("HISTORICAL MODE")[1]
    assert "beta" in market_tail
    assert "analyst consensus" not in market_tail


def test_the_full_sheet_declares_both_domains() -> None:
    s = _sheet(True, None)
    assert "analyst consensus" in s and "beta" in s


def test_a_live_sheet_never_mentions_historical_mode() -> None:
    for agent in (AgentId.FUNDAMENTALS_ANALYST, AgentId.MARKET_ANALYST, None):
        assert "HISTORICAL MODE" not in _sheet(False, agent)


def test_the_news_analyst_gets_no_historical_bullet_it_cannot_use() -> None:
    """Its lane holds neither domain, so the declaration would be noise —
    `_out_of_lane_line` already covers both for it."""
    assert "HISTORICAL MODE" not in _sheet(True, AgentId.NEWS_ANALYST)


# ── The earnings guard (DEF334) ─────────────────────────────────────────────


def test_an_as_of_run_never_reads_the_live_earnings_calendar(monkeypatch) -> None:
    from app.services import room_runner

    calls: list[str] = []

    class _Loud:
        name = "loud"

        def earnings(self, ticker):  # pragma: no cover - must not run
            calls.append(ticker)
            raise AssertionError("the live earnings calendar was read in as-of mode")

        def quote(self, ticker): return None
        def get_price(self, ticker): return None
        def history(self, ticker, period): return None
        def news(self, ticker, limit=5): return None

    monkeypatch.setattr(room_runner, "get_market_data_provider", lambda: _Loud())
    monkeypatch.setattr(room_runner.settings, "use_real_market_data", True)
    profile = room_runner._profile_for_ticker("AAA", as_of=_AS_OF)
    assert calls == []
    assert "next_earnings_date" not in profile
    assert "next_earnings" not in profile["field_state"]


# ── The pin that stops a PIT-only field shipping dark ───────────────────────


def test_pit_never_emits_a_key_the_live_path_does_not(seeded) -> None:
    """A PIT-only key would have no render site and would land nowhere. This
    is the guard that catches the next field before a sweep does."""
    import inspect

    from app.services import fundamentals

    # The whole module: several live fields are emitted by the statements
    # fetcher rather than by `fetch_live_fundamentals` itself, and a key with
    # a render site anywhere in the live path is not a dark key.
    source = inspect.getsource(fundamentals)
    out = fetch_pit_fundamentals(_TICKER, _AS_OF)
    for key in out:
        assert f'"{key}"' in source, f"{key} is emitted by PIT but not by the live path"


# ── DEF336: an outage verdict is not a decision ─────────────────────────────


def test_the_outage_failsafe_is_recognisable_not_just_readable() -> None:
    """It used to be an inline literal, so the only way to spot one was to
    match prose — which is why a 450-run sweep recorded a dead provider as a
    completed batch of PASSes."""
    from app.services.room_runner import (
        PM_LLM_UNAVAILABLE_REASON,
        is_llm_outage_verdict,
    )

    assert is_llm_outage_verdict(
        {"action": "PASS", "overridden_from_llm": True,
         "reason": PM_LLM_UNAVAILABLE_REASON}
    )
    # A safety-floor override is ALSO `overridden_from_llm`, and must not be
    # mistaken for an outage — it is a real decision the floor rewrote.
    assert not is_llm_outage_verdict(
        {"action": "REJECT", "overridden_from_llm": True,
         "reason": "sized down to 3.0% — mandate risk-tier ceiling."}
    )
    # An ordinary reasoned PASS.
    assert not is_llm_outage_verdict(
        {"action": "PASS", "reason": "waiting for post-FOMC price discovery"}
    )
    assert not is_llm_outage_verdict(None)
    assert not is_llm_outage_verdict({})


def test_the_outage_verdict_the_room_actually_builds_is_detected() -> None:
    """Pins the constant to the Verdict the runner constructs, so a reword of
    one without the other cannot silently un-detect the outage."""
    from app.schemas.room import Verdict, VerdictAction
    from app.services.room_runner import (
        PM_LLM_UNAVAILABLE_REASON,
        is_llm_outage_verdict,
    )

    built = Verdict(
        action=VerdictAction.PASS,
        reason=PM_LLM_UNAVAILABLE_REASON,
        overridden_from_llm=True,
    )
    assert is_llm_outage_verdict(built.model_dump())
