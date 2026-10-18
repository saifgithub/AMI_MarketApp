"""CR260 — analyst price-target detail: service, lanes, and verdict payload.

Coverage:
  - `fetch_analyst_detail` shape/gating/cache/error swallowing (yfinance stub
    via sys.modules, the same seam test_fundamentals uses).
  - The line builders (split with history, tape with raise/reiterate).
  - Lane discipline in `_format_profile`: split in the fundamentals lane,
    tape in the news lane, both for full-sheet agents, neither when
    UNAVAILABLE.
  - `_analyst_view_from_profile` — the user-facing verdict payload block.
"""

from __future__ import annotations

import sys
import types

import pandas as pd
import pytest

from app.core.config import settings
from app.schemas import AgentId
from app.schemas.room import AnalystView
from app.services import analyst_targets, room_runner
from app.services.analyst_targets import (
    analyst_split_line,
    analyst_tape_line,
    clear_analyst_targets_cache,
    fetch_analyst_detail,
)
from app.services.room_prompts import _format_profile


def _summary_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "period": ["0m", "-1m", "-2m"],
        "strongBuy": [6, 6, 6],
        "buy": [19, 19, 22],
        "hold": [13, 14, 14],
        "sell": [3, 3, 2],
        "strongSell": [3, 2, 2],
    })


def _tape_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Firm": ["JP Morgan", "Morgan Stanley", "Needham", "Evercore ISI Group", "B of A Securities", "TD Cowen"],
            "ToGrade": ["Overweight", "Overweight", "Hold", "Outperform", "Buy", "Buy"],
            "FromGrade": ["Overweight", "Overweight", "Hold", "Outperform", "Buy", "Buy"],
            "Action": ["main", "main", "reit", "main", "reit", "reit"],
            "priceTargetAction": ["Raises", "Lowers", "", "Raises", "Maintains", "Maintains"],
            "currentPriceTarget": [360.0, 355.0, 0.0, 380.0, 370.0, 400.0],
            "priorPriceTarget": [340.0, 360.0, 0.0, 365.0, 370.0, 400.0],
        },
        index=pd.to_datetime([
            "2026-10-12 18:47:46", "2026-10-01 15:55:51", "2026-10-01 11:00:30",
            "2026-09-18 11:45:30", "2026-09-17 18:02:53", "2026-09-10 13:14:37",
        ]),
    )


class _Ticker:
    def __init__(self, _sym: str) -> None:
        self.recommendations_summary = _summary_frame()
        self.upgrades_downgrades = _tape_frame()


def _stub_yfinance(monkeypatch) -> None:
    fake_yf = types.SimpleNamespace(Ticker=_Ticker, __version__="1.3.0")
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_analyst_targets_cache()
    yield
    clear_analyst_targets_cache()


# ── fetch_analyst_detail ────────────────────────────────────────────────


def test_fetch_returns_split_history_and_bounded_tape(monkeypatch):
    _stub_yfinance(monkeypatch)
    monkeypatch.setattr(settings, "use_real_market_data", True)
    detail = fetch_analyst_detail("AAPL")
    assert detail is not None
    assert detail["analyst_rating_split"] == {
        "strong_buy": 6, "buy": 19, "hold": 13, "sell": 3, "strong_sell": 3,
    }
    history = detail["analyst_rating_split_history"]
    assert history[0]["period"] == "-1m"
    assert history[0]["hold"] == 14
    tape = detail["analyst_tape"]
    assert len(tape) == analyst_targets.TAPE_LIMIT  # 6 feed rows → bounded to 5
    assert tape[0]["firm"] == "JP Morgan"
    assert tape[0]["date"] == "2026-10-12"
    assert tape[0]["current_pt"] == 360.0
    # yfinance's own 0.0 = "no PT on this action" convention → None, never $0.
    reit = next(r for r in tape if r["firm"] == "Needham")
    assert reit["current_pt"] is None and reit["prior_pt"] is None


def test_fetch_cached_per_ticker(monkeypatch):
    _stub_yfinance(monkeypatch)
    monkeypatch.setattr(settings, "use_real_market_data", True)
    calls = {"n": 0}
    real_ticker = _Ticker

    class CountingTicker(real_ticker):
        def __init__(self, sym: str) -> None:
            calls["n"] += 1
            super().__init__(sym)

    fake_yf = types.SimpleNamespace(Ticker=CountingTicker, __version__="1.3.0")
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)
    fetch_analyst_detail("AAPL")
    fetch_analyst_detail("AAPL")
    assert calls["n"] == 1
    fetch_analyst_detail("MSFT")
    assert calls["n"] == 2


def test_fetch_gated_off_returns_none_without_network(monkeypatch):
    monkeypatch.setattr(settings, "use_real_market_data", False)
    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(
        Ticker=lambda *_a, **_kw: pytest.fail("no network when gated off")))
    assert fetch_analyst_detail("AAPL") is None


def test_fetch_suppressed_with_consensus_ablation(monkeypatch):
    _stub_yfinance(monkeypatch)
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(settings, "suppress_analyst_consensus", True)
    assert fetch_analyst_detail("AAPL") is None


def test_fetch_swallows_yfinance_exceptions(monkeypatch):
    class _Boom:
        def __init__(self, *_a, **_kw):
            raise RuntimeError("network is on fire")

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(
        Ticker=_Boom, __version__="1.3.0"))
    assert fetch_analyst_detail("AAPL") is None


def test_fetch_empty_frames_mean_no_keys(monkeypatch):
    class _EmptyTicker:
        recommendations_summary = pd.DataFrame()
        upgrades_downgrades = pd.DataFrame()

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(
        Ticker=_EmptyTicker, __version__="1.3.0"))
    assert fetch_analyst_detail("NOBODY") is None


# ── line builders ───────────────────────────────────────────────────────


def test_split_line_renders_total_and_history():
    line = analyst_split_line(
        {"strong_buy": 6, "buy": 19, "hold": 13, "sell": 3, "strong_sell": 3},
        [{"period": "-1m", "strong_buy": 6, "buy": 19, "hold": 14, "sell": 3, "strong_sell": 2}],
    )
    assert "6 strong buy / 19 buy / 13 hold / 3 sell / 3 strong sell (44 analysts)" in line
    assert "one month earlier: 6 / 19 / 14 / 3 / 2" in line


def test_split_line_without_history_omits_delta():
    line = analyst_split_line({"strong_buy": 1, "buy": 2, "hold": 3, "sell": 4, "strong_sell": 5})
    assert "one month earlier" not in line
    assert analyst_split_line(None) is None


def test_tape_line_words_raises_lowers_maintains_and_reiteration():
    line = analyst_tape_line([
        {"date": "2026-10-12", "firm": "JP Morgan", "to_grade": "Overweight",
         "from_grade": "Overweight", "action": "main", "pt_action": "Raises",
         "current_pt": 360.0, "prior_pt": 340.0},
        {"date": "2026-10-01", "firm": "Morgan Stanley", "to_grade": "Overweight",
         "from_grade": "Overweight", "action": "main", "pt_action": "Lowers",
         "current_pt": 355.0, "prior_pt": 360.0},
        {"date": "2026-09-29", "firm": "Morgan Stanley", "to_grade": "Overweight",
         "from_grade": "Overweight", "action": "reit", "pt_action": "Maintains",
         "current_pt": 360.0, "prior_pt": None},
        {"date": "2026-10-01", "firm": "Needham", "to_grade": "Hold",
         "from_grade": "Hold", "action": "reit", "pt_action": "",
         "current_pt": None, "prior_pt": None},
    ])
    assert "JP Morgan — Overweight, raises target to $360 from $340" in line
    assert "Morgan Stanley — Overweight, lowers target to $355 from $360" in line
    assert "target maintained at $360" in line
    assert "Needham — Hold" in line
    assert "$0" not in line
    assert analyst_tape_line([]) is None


# ── lane discipline in the fact sheet ───────────────────────────────────


def _live_profile() -> dict:
    return {
        "ticker": "AAPL",
        "run_date": "2026-10-19",
        "field_state": {
            "run_date": "live",
            "analyst_rating_split": "live",
            "analyst_rating_split_history": "live",
            "analyst_tape": "live",
        },
        "analyst_rating_split": {"strong_buy": 6, "buy": 19, "hold": 13, "sell": 3, "strong_sell": 3},
        "analyst_rating_split_history": [
            {"period": "-1m", "strong_buy": 6, "buy": 19, "hold": 14, "sell": 3, "strong_sell": 2}
        ],
        "analyst_tape": [
            {"date": "2026-10-12", "firm": "JP Morgan", "to_grade": "Overweight",
             "from_grade": "Overweight", "action": "main", "pt_action": "Raises",
             "current_pt": 360.0, "prior_pt": 340.0},
        ],
    }


def test_split_renders_fundamentals_lane_only():
    sheet_fa = _format_profile(_live_profile(), AgentId.FUNDAMENTALS_ANALYST)
    assert "Analyst rating split (LIVE, Street view)" in sheet_fa
    assert "Recent analyst actions" not in sheet_fa


def test_tape_renders_news_lane_only():
    sheet_na = _format_profile(_live_profile(), AgentId.NEWS_ANALYST)
    assert "Recent analyst actions (LIVE, real, dated)" in sheet_na
    assert "Analyst rating split" not in sheet_na


def test_both_render_for_full_sheet_agents():
    sheet = _format_profile(_live_profile(), None)  # agent_id=None → all domains
    assert "Analyst rating split" in sheet
    assert "Recent analyst actions" in sheet


def test_unavailable_fields_render_nothing_and_claim_nothing():
    profile = _live_profile()
    profile["field_state"] = dict.fromkeys(profile["field_state"], "unavailable")
    sheet = _format_profile(profile, None)
    assert "Analyst rating split" not in sheet
    assert "Recent analyst actions" not in sheet


# ── the user-facing verdict payload ─────────────────────────────────────


def test_analyst_view_lifted_from_live_profile():
    profile = _live_profile()
    profile["field_state"].update({
        "analyst_target_price": "live", "analyst_target_median": "live",
        "analyst_target_high": "live", "analyst_target_low": "live",
        "analyst_opinion_count": "live", "analyst_rating": "live",
    })
    profile.update({
        "analyst_target_price": 329.38, "analyst_target_median": 340.0,
        "analyst_target_high": 405.0, "analyst_target_low": 215.0,
        "analyst_opinion_count": 44, "analyst_rating": "buy",
    })
    view = room_runner._analyst_view_from_profile(profile)
    assert isinstance(view, AnalystView)
    assert view.rating_split.strong_buy == 6
    assert view.rating_split.strong_sell == 3
    assert view.target_mean == 329.38
    assert view.target_high == 405.0
    assert view.opinion_count == 44
    assert view.rating == "buy"
    assert len(view.tape) == 1
    assert view.tape[0].firm == "JP Morgan"
    assert view.tape[0].current_pt == 360.0


def test_analyst_view_none_when_nothing_live():
    profile = _live_profile()
    profile["field_state"] = dict.fromkeys(profile["field_state"], "unavailable")
    assert room_runner._analyst_view_from_profile(profile) is None


def test_analyst_view_skips_malformed_tape_rows():
    profile = _live_profile()
    profile["analyst_tape"] = [
        {"date": "2026-10-12", "firm": "JP Morgan"},  # missing grades — kept, defaults
        {"firm": "", "date": "2026-10-01"},           # no firm — skipped
        "not-a-dict",                                  # skipped, never coerced
    ]
    view = room_runner._analyst_view_from_profile(profile)
    assert len(view.tape) == 1


def test_stamped_verdict_carries_analyst_view():
    profile = _live_profile()
    from app.schemas.room import Verdict

    verdict = Verdict(
        action="PASS", reason="test", entry=None, stop=None, target=None,
        time_horizon_days=90, kill_criterion=None, size_pct=0.0,
    )
    stamped = room_runner._stamp_next_convene_basis(verdict, profile, None)
    assert stamped.analyst_view is not None
    assert stamped.analyst_view.rating_split.buy == 19
    # And the JSONB round-trip the verdict column stores survives.
    assert Verdict.model_validate_json(stamped.model_dump_json()).analyst_view.rating_split.buy == 19
