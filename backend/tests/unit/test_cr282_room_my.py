"""CR282 lane E — the Room on a `.KL` ticker: an honest, market-aware fact sheet.

No network: every fetch seam is stubbed, and the EDGAR seams RAISE if reached, so
"nothing from SEC is fetched for a Bursa name" is asserted, not assumed. The
US-side guarantee (byte-identical prompts) is `test_cr282_room_us_byte_identical.py`.
"""

from __future__ import annotations

import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path as _FsPath
from uuid import uuid4

import pytest

from app.agents.safety_floor import append_safety_floor  # noqa: F401  (import cycle guard)
from app.core.config import settings
from app.schemas import TWELVE_AGENT_IDS, AgentId
from app.schemas.liquidity import (
    LiquidityStatus,
    LiquidityVerdict,
    illiquid_floor,
    microcap_floor_m,
    money_symbol,
)
from app.services import (
    agent_prompts,
    edgar_filings_feed,
    edgar_pit,
    fundamentals,
    opendosm_cpi,
    put_call,
    room_bank,
    room_runner,
    wacc,
)
from app.services.coach_engine import hydrate_coach_mandate
from app.services.edgar_8k import EXEC_CHANGE_LABEL
from app.services.edgar_filings_feed import FEED_LABEL as FILINGS_LABEL
from app.services.edgar_forensics import (
    CLUSTER_BUY_LABEL,
    EIGHT_K_FLAGS_LABEL,
    INSIDER_PLAN_TAG_LABEL,
    INSIDER_RATIO_LABEL,
)
from app.services.room_market import NOT_AVAILABLE_FOR_MARKET, localize_money
from app.services.room_prompts import (
    _format_profile,
    build_risk_officer_messages,
    build_room_messages,
    trader_block_regex,
)
from app.trading_math import bnm_calendar
from app.trading_math.markets import Market

_THIS_DIR = _FsPath(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import test_cr282_room_us_byte_identical as G  # noqa: E402
import test_prompt_data_parity as P  # noqa: E402

KL = "1155.KL"
DOLLAR_AMOUNT = re.compile(r"\$\d")
_REPO = _FsPath(__file__).resolve().parents[3]


def _boom(*a, **k):
    raise AssertionError("an SEC/EDGAR/options seam was reached for a Bursa ticker")


@pytest.fixture
def my_sheet(monkeypatch):
    """The production `_profile_for_ticker` on a `.KL` code; EDGAR + options seams
    raise, everything else answers."""
    monkeypatch.setattr(settings, "market_bursa_enabled", True)
    G.install_seams(monkeypatch, ticker=KL)
    monkeypatch.setattr(edgar_filings_feed, "fetch_recent_filings", _boom)
    monkeypatch.setattr(edgar_pit, "load_facts", _boom)
    monkeypatch.setattr(put_call, "fetch_put_call_ratio", _boom)
    for name in (
        "_overlay_debt_structure", "_overlay_filing_dimensions", "_overlay_executive_change",
        "_overlay_capital_returns", "_overlay_recent_filings", "_overlay_sbc_and_roic",
        "_overlay_insider_forensics", "_overlay_edgar_8k_flags", "_overlay_put_call",
        "_overlay_peer_comparison",
    ):
        monkeypatch.setattr(room_runner, name, _boom)
    monkeypatch.setattr(opendosm_cpi, "_fetch_rows", lambda: [
        {"date": "2026-10-01", "index": 137.7, "division": "overall"},
        {"date": "2025-10-01", "index": 135.1, "division": "overall"},
    ])
    monkeypatch.setattr(settings, "opendosm_cpi_enabled", True)
    opendosm_cpi.reset_cache()
    return room_runner._profile_for_ticker(KL)


# ── the sheet ────────────────────────────────────────────────────────────────


def test_a_bursa_sheet_is_stamped_and_nothing_sec_is_fetched(my_sheet):
    assert my_sheet["market"] == "MY"
    state = my_sheet["field_state"]
    for key in (
        "debt_maturity", "cost_of_debt", "executive_change", "recent_filings", "sbc", "roic",
        "insider_ratio", "insider_plan_tag", "insider_cluster", "edgar_8k_flags",
        "put_call", "peer_comparison",
    ):
        assert state[key] == "unavailable", key


def test_a_us_sheet_never_carries_the_market_key(monkeypatch):
    G.install_seams(monkeypatch)
    assert "market" not in room_runner._profile_for_ticker(G.TICKER)


def test_the_bursa_sheet_is_in_ringgit_with_no_dollar_amount(my_sheet):
    for agent in list(AgentId) + [None]:
        text = _format_profile(my_sheet, agent)
        assert not DOLLAR_AMOUNT.search(text), (agent, DOLLAR_AMOUNT.search(text))
    assert "RM" in _format_profile(my_sheet)


def test_every_sec_dark_input_is_named_not_available_for_this_market(my_sheet, monkeypatch):
    # Flags irrelevant: a Bursa desk names the inputs whether or not the US feature is on.
    for flag in ("room_insider_ratio_enabled", "room_edgar_8k_flags_enabled",
                 "room_put_call_enabled", "room_peer_comparison_enabled"):
        monkeypatch.setattr(settings, flag, False)
    news = _format_profile(my_sheet, AgentId.NEWS_ANALYST)
    for label in (EXEC_CHANGE_LABEL, FILINGS_LABEL, INSIDER_RATIO_LABEL,
                  INSIDER_PLAN_TAG_LABEL, CLUSTER_BUY_LABEL, EIGHT_K_FLAGS_LABEL):
        assert re.search(rf"{re.escape(label)}: {re.escape(NOT_AVAILABLE_FOR_MARKET)}", news), label
    fund = _format_profile(my_sheet, AgentId.FUNDAMENTALS_ANALYST)
    for label in ("Peer comparison", "Filed-statement detail", FILINGS_LABEL):
        assert re.search(rf"{re.escape(label)}: {re.escape(NOT_AVAILABLE_FOR_MARKET)}", fund), label
    social = _format_profile(my_sheet, AgentId.SOCIAL_MEDIA_ANALYST)
    assert re.search(rf"Put/call ratio: {re.escape(NOT_AVAILABLE_FOR_MARKET)}", social)
    # No US-flavoured "no filings" claim and no SEC form cited as a live source.
    for agent in AgentId:
        text = _format_profile(my_sheet, agent)
        assert "SEC Form" not in text and "FOMC" not in text and "S&P 500" not in text, agent
        assert "LIVE, AMI-computed from the issuer's" not in text


def test_the_sheet_states_the_bnm_rate_the_cpi_and_the_klci_basis(my_sheet):
    news = _format_profile(my_sheet, AgentId.NEWS_ANALYST)
    assert "BNM Overnight Policy Rate 2.75%" in news
    assert "BNM's published calendar" in news
    assert "Malaysia headline CPI: +1.9% year-on-year for Oct 2026" in news
    assert "Bank Negara Malaysia (BNM)" in news
    assert "FOMC" not in news


def test_relative_strength_is_against_the_klci(monkeypatch):
    seen = []

    def _chg(symbol):
        seen.append(symbol)
        return {"^KLSE": 4.0, "1155.KL": 10.5}[symbol]

    monkeypatch.setattr(fundamentals, "_one_year_change_pct", _chg)
    out = {"change_52w_sp500_pct": 99.0, "relative_strength_52w_pct": 99.0, "change_52w_pct": 1.0}
    fundamentals._apply_my_benchmark(out, KL)
    assert seen == [KL, "^KLSE"]
    assert out["benchmark_name"] == "FBM KLCI"
    assert (out["change_52w_pct"], out["change_52w_sp500_pct"], out["relative_strength_52w_pct"]) == (10.5, 4.0, 6.5)
    line = fundamentals.relative_strength_line(10.5, 4.0, 6.5, index_name="FBM KLCI")
    assert "vs FBM KLCI +4.0%" in line and "S&P" not in line


def test_a_missing_benchmark_leg_drops_the_line_rather_than_keeping_the_sp500(monkeypatch):
    monkeypatch.setattr(fundamentals, "_one_year_change_pct", lambda s: None if s == "^KLSE" else 5.0)
    out = {"change_52w_sp500_pct": 11.9, "relative_strength_52w_pct": 1.0, "change_52w_pct": 5.0}
    fundamentals._apply_my_benchmark(out, KL)
    assert not any(k in out for k in ("change_52w_sp500_pct", "relative_strength_52w_pct", "benchmark_name"))


def test_penny_stock_prices_keep_three_decimals(monkeypatch):
    class _Info(dict):
        pass

    import types

    info = {"currentPrice": 0.545, "trailingPE": 12.0}
    fake_yf = types.SimpleNamespace(
        Ticker=lambda sym: types.SimpleNamespace(info=info), __version__="1.0.0",
    )
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)
    monkeypatch.setattr(fundamentals, "_apply_my_benchmark", lambda out, t: None)
    out = fundamentals.fetch_live_fundamentals("0166.KL")
    assert out["base_price"] == 0.545


# ── macro: the BNM table ─────────────────────────────────────────────────────


def test_next_mpc_and_countdown():
    assert bnm_calendar.next_mpc_decision(date(2026, 11, 24)) == date(2027, 1, 21)
    assert bnm_calendar.next_mpc_decision(date(2027, 1, 21)) == date(2027, 1, 21)
    line = bnm_calendar.opr_line(date(2026, 11, 24))
    assert "2.75%" in line and "2027-01-21 (in 58 days)" in line


def test_the_mpc_table_fails_loudly_past_its_end():
    with pytest.raises(bnm_calendar.MpcTableExhausted):
        bnm_calendar.next_mpc_decision(date(2027, 11, 5))
    assert bnm_calendar.next_mpc_decision(date(2027, 11, 4)) == date(2027, 11, 4)


def test_past_the_table_the_sheet_says_so_instead_of_a_stale_countdown():
    profile: dict = {}
    room_runner._stamp_my_macro(profile, {}, date(2028, 1, 5))
    assert "not in AMI's calendar" in profile["forward_catalyst"]
    assert "do not state a meeting date" in profile["forward_catalyst"]


def test_the_table_is_ascending_and_thursday_dates():
    d = bnm_calendar.MPC_DECISION_DATES
    assert list(d) == sorted(d) and len(set(d)) == len(d)
    assert all(x.weekday() == 3 for x in d)


# ── macro: OpenDOSM CPI ──────────────────────────────────────────────────────


def test_cpi_off_by_default_says_so_and_never_fetches(monkeypatch):
    monkeypatch.setattr(opendosm_cpi, "_fetch_rows", _boom)
    monkeypatch.setattr(settings, "opendosm_cpi_enabled", False)
    opendosm_cpi.reset_cache()
    line = opendosm_cpi.cpi_line(opendosm_cpi.fetch_cpi())
    assert "not available this call" in line and "not enabled" in line


def test_cpi_failure_is_stated_not_invented(monkeypatch):
    def _down():
        raise RuntimeError("503")

    monkeypatch.setattr(opendosm_cpi, "_fetch_rows", _down)
    monkeypatch.setattr(settings, "opendosm_cpi_enabled", True)
    opendosm_cpi.reset_cache()
    line = opendosm_cpi.cpi_line(opendosm_cpi.fetch_cpi())
    assert "could not be read" in line and "%" not in line


def test_cpi_is_cached_for_the_rate_limit(monkeypatch):
    calls = []
    monkeypatch.setattr(opendosm_cpi, "_fetch_rows", lambda: calls.append(1) or [
        {"date": "2026-10-01", "index": 137.7, "division": "overall"},
        {"date": "2025-10-01", "index": 135.1, "division": "overall"},
    ])
    monkeypatch.setattr(settings, "opendosm_cpi_enabled", True)
    opendosm_cpi.reset_cache()
    a = opendosm_cpi.fetch_cpi(now=1000.0)
    b = opendosm_cpi.fetch_cpi(now=2000.0)
    assert a is b and len(calls) == 1 and a.yoy_pct == 1.9


def test_cpi_without_the_year_ago_month_is_absent_not_guessed(monkeypatch):
    monkeypatch.setattr(opendosm_cpi, "_fetch_rows", lambda: [
        {"date": "2026-10-01", "index": 137.7, "division": "overall"},
    ])
    monkeypatch.setattr(settings, "opendosm_cpi_enabled", True)
    opendosm_cpi.reset_cache()
    read = opendosm_cpi.fetch_cpi()
    assert read.yoy_pct is None and "a year earlier" in read.reason


# ── WACC ─────────────────────────────────────────────────────────────────────


def test_my_wacc_uses_the_malaysian_inputs_and_names_them(monkeypatch):
    monkeypatch.setattr(settings, "wacc_my_risk_free_pct", 3.9)
    monkeypatch.setattr(settings, "wacc_my_erp_pct", 6.0)
    assert wacc.estimate_wacc_pct_my(1.0) == 9.9
    assert wacc.estimate_wacc_pct_my(None) is None and wacc.estimate_wacc_pct_my(-1.0) is None
    assert wacc.estimate_wacc_pct(1.0) == 8.8  # the US constants are untouched
    line = fundamentals.wacc_estimate_line(9.9, 1.0, risk_free_pct=3.9, erp_pct=6.0)
    assert "10-year MGS" in line and "Malaysian ERP" in line and "4.2%" not in line


def test_the_my_wacc_inputs_are_forwarded_in_compose():
    compose = (_REPO / "docker-compose.yml").read_text()
    for name in ("WACC_MY_RISK_FREE_PCT", "WACC_MY_ERP_PCT", "OPENDOSM_CPI_ENABLED"):
        assert f"{name}: ${{{name}" in compose


# ── liquidity floors ─────────────────────────────────────────────────────────


def test_liquidity_floors_are_per_market():
    assert (microcap_floor_m("NVDA"), illiquid_floor("NVDA"), money_symbol("NVDA")) == (500, 1_000_000, "$")
    assert (microcap_floor_m(KL), illiquid_floor(KL), money_symbol(KL)) == (2_100, 4_200_000, "RM")


def test_a_bursa_liquidity_message_is_in_ringgit_against_the_ringgit_floor():
    v = LiquidityVerdict(status=LiquidityStatus.EXCLUDED, ticker=KL, market_cap_usd_m=800.0)
    msg = v.message()
    assert "RM800M market cap is below AMI's RM2100M microcap floor" in msg and "$" not in msg
    ok = LiquidityVerdict(status=LiquidityStatus.PERMITTED, ticker=KL, market_cap_usd_m=120_000.0)
    assert "RM120,000M" in ok.message() and "$" not in ok.message()
    us = LiquidityVerdict(status=LiquidityStatus.EXCLUDED, ticker="XYZ", market_cap_usd_m=400.0)
    assert "$400M market cap is below AMI's $500M microcap floor" in us.message()


def test_a_ringgit_cap_is_judged_against_the_ringgit_floor_in_the_lookup():
    from app.services.liquidity_lookup import _verdict_from_info

    small = _verdict_from_info({"market_cap_usd_m": 900.0, "avg_volume": 5_000_000}, KL, 2.0)
    assert small.status is LiquidityStatus.EXCLUDED  # RM900M < RM2,100M
    big = _verdict_from_info({"market_cap_usd_m": 120_000.0, "avg_volume": 5_000_000}, KL, 10.0)
    assert big.status is LiquidityStatus.PERMITTED
    us = _verdict_from_info({"market_cap_usd_m": 900.0, "avg_volume": 5_000_000}, "XYZ", 2.0)
    assert us.status is LiquidityStatus.PERMITTED  # $900M clears the dollar floor


# ── the prompts ──────────────────────────────────────────────────────────────

_SEC_PHRASES = ("Form 4", "Form 3", "8-K", "FOMC", "SEC filings", "Recent SEC", "same-4-digit-SIC",
                "Item 4.02", "10b5-1", "XBRL")


def test_a_bursa_base_prompt_never_tells_a_desk_to_rely_on_sec_data():
    for agent in TWELVE_AGENT_IDS:
        text = agent_prompts.load_base_prompt(agent, Market.MY)
        assert "<!--" not in text, agent
        assert "$" not in text, (agent, text[text.index("$") - 40: text.index("$") + 40])
    for agent in (AgentId.FUNDAMENTALS_ANALYST, AgentId.NEWS_ANALYST,
                  AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER):
        text = agent_prompts.load_base_prompt(agent, Market.MY)
        for phrase in _SEC_PHRASES:
            assert phrase not in text, (agent, phrase)
        assert NOT_AVAILABLE_FOR_MARKET in text, agent


def test_a_us_base_prompt_is_the_file_minus_its_marker_lines():
    for agent in TWELVE_AGENT_IDS:
        raw = (_REPO / "content" / "agents" / f"{agent.value}.md").read_text(encoding="utf-8")
        us = agent_prompts.load_base_prompt(agent, Market.US)
        assert "<!-- market" not in us and "<!-- /market" not in us
        if "<!-- market" not in raw:
            assert us == agent_prompts._strip_frontmatter(raw)
        else:
            # every line of the US text is a line of the file, in order
            no_my = re.sub(r"<!-- market:my -->\n.*?<!-- /market -->\n", "", raw, flags=re.S)
            keep = [l for l in no_my.splitlines() if not l.startswith("<!-- ")]
            assert us.splitlines() == agent_prompts._strip_frontmatter("\n".join(keep) + "\n").splitlines()


def test_the_trader_prompt_is_in_ringgit_for_bursa():
    text = agent_prompts.load_base_prompt(AgentId.TRADER, Market.MY)
    assert "Entry:          RM{price}" in text and "$" not in text
    assert "${price}" in agent_prompts.load_base_prompt(AgentId.TRADER, Market.US)


def test_the_trader_grammar_takes_ringgit_with_three_decimals_for_bursa_only():
    my = trader_block_regex(ticker=KL)
    us = trader_block_regex(ticker="NVDA")
    block = (
        "[STANCE: for | CONVICTION: high | HEADLINE: x]\nInstrument: 1155.KL\nSide: BUY\n"
        "Size: 2.50% of portfolio\nEntry: RM0.545\nTarget: RM0.650\nStop: RM0.500\n"
        "Time horizon: weeks\nR:R: 2.10:1\n"
    )
    assert re.fullmatch(my, block)
    assert not re.fullmatch(us, block.replace("1155.KL", "NVDA"))
    assert r"\$" in us and "RM" not in us


def test_a_bursa_room_prompt_for_every_desk_is_free_of_dollar_amounts(my_sheet, monkeypatch):
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3, "single_name_cap_pct": 3.0})
    snapshot = (
        "─── YOUR PORTFOLIO (AMI simulation) ───\n"
        "Cash: $50,000.00 | Portfolio value: $50,000.00\nOpen positions: none\n───"
    )
    proposal = {"size_pct": 3.0, "entry": 9.5, "stop": 9.0, "target": 11.0}
    for agent in TWELVE_AGENT_IDS:
        system_prompt, _ = build_room_messages(
            agent_id=agent, mandate=mandate, ticker=KL, profile=my_sheet, transcript=[],
            portfolio_snapshot=snapshot, trade_proposal=dict(proposal), portfolio_value=50_000.0,
            agent_size_pct=3.0, current_drawdown_pct=1.0,
        )
        assert not DOLLAR_AMOUNT.search(system_prompt), (agent, DOLLAR_AMOUNT.search(system_prompt).span())
        assert "RM50,000.00" in system_prompt
    ro, _, _ = build_risk_officer_messages(
        mandate=mandate, ticker=KL, profile=my_sheet, transcript=[], trade_proposal=dict(proposal),
        portfolio_snapshot=snapshot, portfolio_value=50_000.0,
    )
    assert not DOLLAR_AMOUNT.search(ro)


def test_a_bursa_liquid_only_line_carries_the_ringgit_floor(my_sheet):
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    sp, _ = build_room_messages(
        agent_id=AgentId.PORTFOLIO_MANAGER, mandate=mandate, ticker=KL,
        profile=my_sheet, transcript=[],
    )
    assert "Avoid microcaps (< RM2100M market cap)" in sp


def test_localize_money_leaves_cashtags_and_us_alone():
    assert localize_money("$AAPL up; cap $1,234M and -$5.5", Market.MY) == "$AAPL up; cap RM1,234M and -RM5.5"
    s = "cap $1,234M"
    assert localize_money(s, Market.US) is s


def test_the_halal_line_in_a_bursa_room_prompt_cites_the_sc_standard(my_sheet, monkeypatch):
    """Lane D narrates the halal verdict per market; the assembled Room prompt must carry
    it, and the compliance check (the uncoachable floor) is untouched by lane E."""
    from datetime import timedelta

    import test_cr282_sharia_sc_malaysia as D
    from app.services.sharia_universe import default_halal_universe

    monkeypatch.setattr(settings, "sharia_screen_enabled", True)
    D.reset_sharia_universe_provider(None)
    D._seed_us()
    D._seed_sc(as_of=D._today() - timedelta(days=30))
    uni = default_halal_universe()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    mandate = mandate.model_copy(update={
        "compliance": mandate.compliance.model_copy(update={"halal": True}),
    })
    sp, _ = build_room_messages(
        agent_id=AgentId.PORTFOLIO_MANAGER, mandate=mandate, ticker="5183.KL",
        profile=my_sheet, transcript=[], halal_universe=uni,
    )
    assert "SC Malaysia Shariah Advisory Council list" in sp
    assert "NOT REVIEWED" not in sp and "PAUSED" not in sp
    D.reset_sharia_universe_provider(None)


# ── the portfolio the Room reads, and the bank key ───────────────────────────


def test_a_bursa_room_reads_the_myr_book_not_the_us_book(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", True)
    from app.services.sim_engine import SimEngine
    from test_cr282_myr_book import _Pinned

    sim = SimEngine(provider=_Pinned({KL: 10.0, "NVDA": 100.0}))
    monkeypatch.setattr(room_runner, "get_sim_engine", lambda: sim)
    uid = uuid4()
    my_block = room_runner._build_sim_holdings_block(uid, KL)
    us_block = room_runner._build_sim_holdings_block(uid, "NVDA")
    assert "Cash: RM50,000.00 | Portfolio value: RM50,000.00" in my_block
    assert "Cash: $10,000.00 | Portfolio value: $10,000.00" in us_block
    assert room_runner._build_room_sector_context(uid, Market.MY)[0] == []
    assert sim.valuation_snapshot(uid, Market.MY)[0] == 50_000.0
    assert sim.valuation_snapshot(uid)[0] == 10_000.0


def test_the_bank_key_follows_the_myr_book_and_the_my_trading_day(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", True)
    from app.schemas.trade import Side
    from app.services.sim_engine import SimEngine
    from test_cr282_myr_book import _Pinned, _mandate

    sim = SimEngine(provider=_Pinned({KL: 10.0, "NVDA": 100.0}))
    monkeypatch.setattr(room_runner, "get_sim_engine", lambda: sim)
    uid = uuid4()
    us0 = room_runner.RoomRunner._account_digests_blocking(uid, "NVDA")
    my0 = room_runner.RoomRunner._account_digests_blocking(uid, KL)
    assert us0 is not None and my0 is not None
    assert us0["portfolio"] != my0["portfolio"]  # two books, two states

    sim.submit(user_id=uid, ticker=KL, side=Side.BUY, quantity=100, mandate=_mandate())
    my1 = room_runner.RoomRunner._account_digests_blocking(uid, KL)
    us1 = room_runner.RoomRunner._account_digests_blocking(uid, "NVDA")
    assert my1["portfolio"] != my0["portfolio"]      # a Bursa trade re-keys a Bursa Room
    assert us1["portfolio"] == us0["portfolio"]      # and leaves a US Room's key alone

    sim.submit(user_id=uid, ticker="NVDA", side=Side.BUY, quantity=1, mandate=_mandate())
    assert room_runner.RoomRunner._account_digests_blocking(uid, KL)["portfolio"] == my1["portfolio"]
    assert room_runner.RoomRunner._account_digests_blocking(uid, "NVDA")["portfolio"] != us1["portfolio"]

    # 02:00 UTC on a Tuesday is 10:00 in KL (open) but still Monday's session in New York.
    now = datetime(2026, 11, 24, 2, 0, tzinfo=timezone.utc)
    assert room_bank.trading_date_for(now, KL) == date(2026, 11, 24)
    assert room_bank.trading_date_for(now) == date(2026, 11, 23)
    assert room_bank.trading_date_for(now, "NVDA") == date(2026, 11, 23)


def test_flag_off_a_kl_room_is_refused_as_before(monkeypatch):
    from app.db import get_session
    from app.services.ticker_reference import TickerNotFoundError, require_ticker_exists

    monkeypatch.setattr(settings, "market_bursa_enabled", False)
    with get_session() as session, pytest.raises(TickerNotFoundError):
        require_ticker_exists(session, KL)
    monkeypatch.setattr(settings, "market_bursa_enabled", True)
    with get_session() as session:
        require_ticker_exists(session, KL)


def test_a_us_ticker_prose_extraction_is_unchanged_and_kl_codes_need_the_flag(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", False)
    assert fundamentals.extract_tickers("compare AAPL and $MSFT") == ["AAPL", "MSFT"]
    off = fundamentals.extract_tickers("what about 1155.KL?")
    assert "1155.KL" not in off
    monkeypatch.setattr(settings, "market_bursa_enabled", True)
    assert fundamentals.extract_tickers("what about 1155.KL?") == ["1155.KL"]
    assert fundamentals.extract_tickers("AAPL vs 5099.KL and 03068.KL") == ["AAPL", "5099.KL", "03068.KL"]
    assert fundamentals.extract_tickers("compare AAPL and $MSFT") == ["AAPL", "MSFT"]


def test_a_bursa_sheet_freezes_and_thaws_for_the_room_bank(my_sheet):
    from app.services.cio_snapshot_codec import decode_profile, encode_profile

    thawed = decode_profile(encode_profile(my_sheet))
    assert thawed == my_sheet and thawed["market"] == "MY"
    for agent in TWELVE_AGENT_IDS:
        assert _format_profile(thawed, agent) == _format_profile(my_sheet, agent)
