"""CR282 lane E — a US Room renders byte-for-byte what it rendered before CR282.

The Room bank's policy version hashes every agent's derived prompt version, so
changing one character of US prompt text re-keys every banked US Room. Every
Bursa behaviour is therefore a market-conditional branch that is ABSENT for US;
this file is the proof.

How it proves it:

  1. `fixtures/cr282_room_us_golden.json` was generated from the tree BEFORE any
     lane-E change. It holds (a) a frozen production-shaped US fact sheet (the
     codec's encoding of what `_profile_for_ticker` built, every optional block
     populated), (b) a sha256 of every rendering of it — the fact sheet per desk,
     the full Room prompt per desk per reference mandate, the Risk Officer
     prompt, the trader grammar, the forward-catalyst text — and (c) the derived
     prompt version of every agent (the exact input to `room_bank.policy_version`).
  2. The tests re-render the frozen sheet and compare. A frozen sheet rather than
     a live build keeps the comparison independent of today's date.
  3. A freshly built US sheet must equal the frozen one except for the keys that
     depend on today's date, which proves the BUILD side (EDGAR overlays, WACC,
     catalyst) also stayed US-identical.

Regenerate (only when a US prompt change is INTENDED, which re-keys the bank):
`CR282_REGEN_US_GOLDEN=1 pytest tests/unit/test_cr282_room_us_byte_identical.py -k regenerate`.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path as _FsPath

import pytest

from app.core.config import settings
from app.schemas import TWELVE_AGENT_IDS, AgentId
from app.services import (
    analyst_targets,
    buyback_price,
    edgar_filings_feed,
    edgar_pit,
    fundamentals,
    news_context,
    put_call,
    ratio_baselines,
    room_runner,
    social_context,
    technicals,
)
from app.services.buyback_price import BuybackPrice
from app.services.cio_snapshot_codec import decode_profile, encode_profile
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import DividendPayment
from app.services.put_call import PutCallRatio

_THIS_DIR = _FsPath(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import test_prompt_data_parity as P  # noqa: E402  (needs the path insert above)

GOLDEN = _THIS_DIR / "fixtures" / "cr282_room_us_golden.json"
TICKER = "NVDA"

# Sheet keys whose value is a function of today's date (the run-date anchor and
# every relative-day phrase computed against it). The live fixtures are written
# relative to now(), so these move daily by construction.
DATE_RELATIVE_KEYS = frozenset({
    "run_date", "forward_catalyst", "next_earnings_interval", "news_headlines",
    "insider_ratio_line", "insider_cluster_line", "edgar_8k_flag_lines",
    "float_liquidity", "social_fetched_age",
})


class _Provider(P._FakeEarningsProvider):
    def dividend_history(self, underlying):
        return [
            DividendPayment(date(y, m, 14), 0.20 + 0.01 * (y - 2018), "fake")
            for y in range(2018, 2026) for m in (2, 5, 8, 11)
        ]


_BUYBACK = BuybackPrice(
    avg_price=187.4, dollars=9.1e10, shares=4.86e8,
    period_start=date(2024, 10, 1), period_end=date(2025, 9, 30), quarters=4,
)


def enable_default_off_flags(monkeypatch) -> None:
    """The flags that default OFF, switched on so the golden covers their lines."""
    for flag in (
        "room_segment_revenue_enabled", "room_geographic_revenue_enabled",
        "room_executive_change_enabled", "room_recent_filings_enabled",
        "room_float_liquidity_enabled", "room_dividend_growth_enabled",
        "room_buyback_price_enabled",
    ):
        monkeypatch.setattr(settings, flag, True)


def install_seams(monkeypatch, ticker: str = TICKER) -> None:
    """Every fetch seam answering, as `test_def512_frozen_sheet_real_shape` does."""
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(settings, "suppress_analyst_consensus", False)
    monkeypatch.setattr(settings, "adanos_api_key", "x")
    enable_default_off_flags(monkeypatch)
    for mod, name, fn in (
        (fundamentals, "fetch_live_fundamentals", lambda t: dict(P._FUND_SENTINEL)),
        (room_runner, "fetch_live_fundamentals", lambda t: dict(P._FUND_SENTINEL)),
        (technicals, "compute_technicals", lambda t: P._TECH_SENTINEL),
        (room_runner, "compute_technicals", lambda t: P._TECH_SENTINEL),
        (news_context, "fetch_live_news", lambda t, limit=3: [P._news_sentinel()]),
        (room_runner, "fetch_live_news", lambda t: [P._news_sentinel(), P._news_sentinel()]),
        (social_context, "fetch_live_sentiment", lambda t: P._SOCIAL_SENTINEL),
        (room_runner, "fetch_live_sentiment", lambda t: P._SOCIAL_SENTINEL),
        (fundamentals, "get_market_data_provider", lambda: _Provider()),
        (room_runner, "get_market_data_provider", lambda: _Provider()),
        (put_call, "fetch_put_call_ratio", lambda t: PutCallRatio(
            volume_ratio=0.81, oi_ratio=0.66, put_volume=1200, call_volume=1480,
            put_open_interest=9100, call_open_interest=13800, contracts=640,
            expiries=4, expiry_first=date(2026, 12, 4), expiry_last=date(2026, 12, 24),
            chain_date=date(2026, 11, 20),
        )),
        (buyback_price, "resolve_buyback_price", lambda facts, as_of: _BUYBACK),
        (edgar_pit, "load_facts", lambda *a, **k: {}),
        (edgar_filings_feed, "fetch_recent_filings", lambda t, a: ("live", [
            {"form": "10-Q", "label": "quarterly report", "filed_date": "2026-11-02"},
        ])),
        (analyst_targets, "fetch_analyst_detail", lambda t: {
            "analyst_rating_split": {
                "strong_buy": 9, "buy": 14, "hold": 8, "sell": 1, "strong_sell": 0,
            },
            "analyst_rating_split_history": [{
                "period": "-1m", "strong_buy": 8, "buy": 15, "hold": 8,
                "sell": 1, "strong_sell": 0,
            }],
            "analyst_tape": [{
                "date": "2026-11-10", "firm": "Fake & Co", "to_grade": "Buy",
                "from_grade": "Hold", "action": "up", "pt_action": "Raises",
                "current_pt": 300.0, "prior_pt": 280.0,
            }],
        }),
    ):
        monkeypatch.setattr(mod, name, fn)
    today = datetime.now(timezone.utc).date()
    for i in range(1, 9):
        for metric, value in (
            (ratio_baselines.METRIC_PUT_CALL_VOLUME, 0.7 + 0.01 * i),
            (ratio_baselines.METRIC_PUT_CALL_OI, 0.6 + 0.01 * i),
            (ratio_baselines.METRIC_SENTIMENT_SCORE, 0.1 * i),
            (ratio_baselines.METRIC_MENTION_VOLUME, 50.0 + i),
        ):
            ratio_baselines.record_observation(ticker, metric, value, on=today - timedelta(days=i))


def _h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def render_corpus(sheet: dict) -> dict[str, str]:
    """sha256 of every US rendering the Room's prompts are built from."""
    from app.services import room_prompts as rp
    from app.services.room_prompts import (
        _format_profile,
        build_risk_officer_messages,
        build_room_messages,
    )

    out: dict[str, str] = {}
    for agent in AgentId:
        out[f"sheet/{agent.value}"] = _h(_format_profile(sheet, agent))
    out["sheet/full"] = _h(_format_profile(sheet))

    mandates = {
        "r3": hydrate_coach_mandate({"plan": "trader", "risk_score": 3, "single_name_cap_pct": 3.0}),
        "r1": hydrate_coach_mandate({"plan": "trader", "risk_score": 1, "single_name_cap_pct": 2.0}),
        "r5": hydrate_coach_mandate({"plan": "trader", "risk_score": 5, "single_name_cap_pct": 8.0}),
    }
    mandates["r1"] = mandates["r1"].model_copy(update={
        "compliance": mandates["r1"].compliance.model_copy(update={"halal": True}),
    })
    proposal = {"size_pct": 3.0, "entry": 100.0, "stop": 94.0, "target": 118.0}
    snapshot = (
        "─── YOUR PORTFOLIO (AMI simulation) ───\n"
        "Cash: $50,000.00 | Portfolio value: $100,000.00\n"
        "Open positions: none — you hold nothing yet. You hold 0% of NVDA.\n───"
    )
    for mname, mandate in mandates.items():
        for agent in TWELVE_AGENT_IDS:
            system_prompt, messages = build_room_messages(
                agent_id=agent, mandate=mandate, ticker=TICKER, profile=sheet,
                transcript=[], portfolio_snapshot=snapshot,
                trade_proposal=dict(proposal), portfolio_value=100_000.0,
                sector_weights={"Technology": 31.5, "Financials": 12.0},
                agent_size_pct=3.0, current_drawdown_pct=2.5,
            )
            out[f"room/{mname}/{agent.value}"] = _h(
                system_prompt + "\n" + "\n".join(str(m.content) for m in messages)
            )
            if mname == "r3":
                system_prompt, messages = build_room_messages(
                    agent_id=agent, mandate=mandate, ticker=TICKER, profile=sheet,
                    transcript=[], cards_envelope=True, parallel_phase=True,
                )
                out[f"room_cards/{agent.value}"] = _h(system_prompt)
        ro_system, ro_messages, _rows = build_risk_officer_messages(
            mandate=mandate, ticker=TICKER, profile=sheet, transcript=[],
            trade_proposal=dict(proposal), portfolio_snapshot=snapshot,
            sector_weights={"Technology": 31.5}, current_drawdown_pct=2.5,
            portfolio_value=100_000.0,
        )
        out[f"risk_officer/{mname}"] = _h(
            ro_system + "\n" + "\n".join(str(m.content) for m in ro_messages)
        )
    out["trader_regex"] = _h(rp.trader_block_regex(ticker=TICKER))
    out["forward_catalyst"] = _h(room_runner._forward_catalyst_text(date(2026, 12, 1)))
    out["forward_catalyst_late"] = _h(room_runner._forward_catalyst_text(date(2027, 3, 1)))
    out["holdings_none"] = _h(room_runner._build_sim_holdings_block(None, TICKER))
    return out


def prompt_versions() -> dict[str, str | None]:
    from app.services import prompt_version

    prompt_version.reset_cache()
    return {a.value: prompt_version.prompt_version(a) for a in AgentId}


def _mask(sheet: dict) -> dict:
    return {k: v for k, v in encode_profile(sheet).items() if k not in DATE_RELATIVE_KEYS}


def _load() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_us_renderings_are_byte_identical_to_pre_cr282(monkeypatch):
    install_seams(monkeypatch)
    golden = _load()
    sheet = decode_profile(golden["sheet"])
    now = render_corpus(sheet)
    assert set(now) == set(golden["corpus"]), "corpus keys changed — regenerate deliberately"
    changed = sorted(k for k in now if now[k] != golden["corpus"][k])
    assert not changed, f"US rendering changed (re-keys every banked US Room): {changed[:8]}"


def test_us_derived_prompt_versions_are_unchanged(monkeypatch):
    golden = _load()
    assert any(golden["prompt_versions"].values()), "golden carries no prompt versions"
    assert prompt_versions() == golden["prompt_versions"]
    install_seams(monkeypatch)
    assert prompt_versions() == golden["prompt_versions_flags_on"]


def test_a_freshly_built_us_sheet_matches_the_frozen_one(monkeypatch):
    install_seams(monkeypatch)
    now = _mask(room_runner._profile_for_ticker(TICKER))
    then = _mask(decode_profile(_load()["sheet"]))
    assert set(now) == set(then)
    assert [k for k in now if now[k] != then[k]] == []


def test_the_frozen_sheet_is_the_real_shape(monkeypatch):
    """Non-vacuity: the sheet carries the blocks the Bursa branches replace."""
    from app.services.room_prompts import _format_profile

    enable_default_off_flags(monkeypatch)
    sheet = decode_profile(_load()["sheet"])
    text = "\n".join(_format_profile(sheet, a) for a in AgentId)
    for needle in (
        "Recent SEC filings", "SEC Form 3/4/5", "Put/call", "Peer comparison", "$", "FOMC",
        "8-K forensic", "Executive change (8-K Item 5.02)", "Float & liquidity",
    ):
        assert needle in text, needle


@pytest.mark.skipif(not os.environ.get("CR282_REGEN_US_GOLDEN"), reason="deliberate regeneration only")
def test_regenerate_us_golden(monkeypatch):
    versions_default = prompt_versions()
    install_seams(monkeypatch)
    sheet = room_runner._profile_for_ticker(TICKER)
    payload = {
        "sheet": encode_profile(sheet),
        "corpus": render_corpus(sheet),
        "prompt_versions": versions_default,
        "prompt_versions_flags_on": prompt_versions(),
    }
    GOLDEN.write_text(json.dumps(payload, sort_keys=True, indent=1), encoding="utf-8")
