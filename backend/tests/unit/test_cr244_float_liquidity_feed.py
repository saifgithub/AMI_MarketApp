"""CR244 Part 2 — the float and liquidity block, Execution Desk + Conservative
Risk Officer only (Saiful, 2026-11-22: "two desks only").

What must hold:

1. The block (float, shares outstanding, float % of shares, average daily
   dollar volume with its window, source labels, as-of dates) renders into the
   `trader` and `conservative_debator` prompts and NO other agent's, including
   the structured Risk Officer and the full-sheet `agent_id=None` render.
2. Flag off, the rendered sheet is byte-identical to a sheet with no float data
   at all, and the overlay reads and writes nothing (so the frozen, hashed fact
   sheet is unchanged too).
3. Missing data renders "not available: <reason>" per component and for the
   whole feed; nothing is imputed (CR040).
4. The flag rides the bank policy version, so flipping it changes the bank key.
5. Everything the desks read lives on the frozen fact sheet (keyed by its hash
   in `room_bank`), and survives the sheet's encode/decode round trip.

Fixtures only: no network, no yfinance.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.schemas import AgentId
from app.schemas.company_profile import OwnershipSection
from app.services import room_bank, room_prompts, room_runner, technicals
from app.services.float_liquidity import (
    FEED_LABEL,
    build_float_liquidity,
    float_liquidity_line,
    float_liquidity_unavailable_line,
)
from app.services.market_data import Candle
from app.services.room_bank import decode_profile, encode_profile

_TWO_DESKS = {AgentId.TRADER, AgentId.CONSERVATIVE_DEBATOR}
_BASE_T = 1_800_000_000
_LAST_BAR = "2027-03-20"  # _BASE_T + 64 * 86400, UTC


def _ownership(**kw) -> OwnershipSection:
    base = dict(
        state="live", reason=None, sources=["yfinance"],
        shares_outstanding=34_450_000.0, float_shares=14_200_000.0,
        pct_institutions=0.7, pct_insiders=0.1,
    )
    base.update(kw)
    return OwnershipSection(**base)


_LIVE_PAYLOAD = {
    "float_shares": 14_200_000.0,
    "float_as_of": "2026-11-20",
    "shares_outstanding": 34_450_000.0,
    "float_pct": 41.2,
    "adv_dollar": 3_000_000.0,
    "adv_window": 20,
    "adv_as_of": "2026-11-20",
}


def _sheet_profile(payload=None, *, live=True, reason=None) -> dict:
    field_state = {"float_liquidity": "live" if live else "unavailable", "run_date": "live"}
    profile = {"field_state": field_state, "run_date": "2026-11-22"}
    if live:
        profile["float_liquidity"] = payload or dict(_LIVE_PAYLOAD)
    elif reason:
        profile["float_liquidity_unavailable_reason"] = reason
    return profile


# ── The rendered text ────────────────────────────────────────────────────────


def test_the_line_states_figures_sources_windows_and_dates():
    assert float_liquidity_line(_LIVE_PAYLOAD) == (
        "Float & liquidity: float 14.20M sh [yfinance, as of 2026-11-20] · "
        "float is 41.2% of 34.45M sh outstanding [yfinance, as of 2026-11-20] · "
        "average daily dollar volume $3.00M "
        "[20-session mean of close x volume, yfinance daily bars to 2026-11-20]"
    )


def test_build_computes_float_pct_in_code_and_never_imputes():
    data, reason = build_float_liquidity(
        ownership=_ownership(), snapshot_date="2026-11-20",
        adv_dollar=3_000_000.0, adv_window=20, adv_as_of="2026-11-20",
        adv_missing_reason="",
    )
    assert reason is None
    assert data["float_pct"] == 41.2
    assert data["float_as_of"] == "2026-11-20"


def test_a_missing_float_says_not_available_with_the_reason_and_no_number():
    data, _ = build_float_liquidity(
        ownership=_ownership(float_shares=None, state="partial", reason="Named holders list unavailable"),
        snapshot_date="2026-11-20",
        adv_dollar=3_000_000.0, adv_window=20, adv_as_of="2026-11-20",
        adv_missing_reason="",
    )
    line = float_liquidity_line(data)
    assert "float: not available: float shares missing — Named holders list unavailable" in line
    assert "34.45M sh outstanding; float % of shares outstanding: not available: float shares missing" in line
    assert "float 14" not in line and "41.2%" not in line
    assert "average daily dollar volume $3.00M" in line  # the other half still stands


def test_missing_dollar_volume_says_not_available_beside_the_float():
    data, _ = build_float_liquidity(
        ownership=_ownership(), snapshot_date="2026-11-20",
        adv_dollar=None, adv_window=0, adv_as_of=None,
        adv_missing_reason="the daily price-bar fetch failed or was too short",
    )
    line = float_liquidity_line(data)
    assert "average daily dollar volume: not available: the daily price-bar fetch failed or was too short" in line
    assert "float 14.20M sh" in line


def test_a_float_larger_than_shares_outstanding_is_refused_not_rendered_as_a_percentage():
    data, _ = build_float_liquidity(
        ownership=_ownership(float_shares=40_000_000.0), snapshot_date="2026-11-20",
        adv_dollar=None, adv_window=0, adv_as_of=None, adv_missing_reason="x",
    )
    assert "float_pct" not in data
    assert "exceeds its shares outstanding" in float_liquidity_line(data)


def test_nothing_resolved_is_a_whole_feed_reason_not_a_payload():
    data, reason = build_float_liquidity(
        ownership=None, snapshot_date=None,
        adv_dollar=None, adv_window=0, adv_as_of=None,
        adv_missing_reason="the daily price-bar fetch failed or was too short",
    )
    assert data is None
    assert "no company profile is cached for this symbol" in reason
    assert "price-bar fetch failed" in reason
    line = float_liquidity_unavailable_line(reason)
    assert line.startswith(f"{FEED_LABEL}: not available: ")
    assert "Do not estimate float" in line


# ── Dollar volume: window and as-of from the real bars ───────────────────────


class _Provider:
    def __init__(self, candles):
        self._candles = candles

    def history(self, ticker, period):
        return self._candles


def test_average_daily_dollar_volume_is_the_20_session_mean_of_close_times_volume(monkeypatch):
    closes = [20.0] * 65
    volumes = [9_000_000] * 45 + [150_000] * 20  # old bars must fall outside the window
    candles = [
        Candle(t=_BASE_T + i * 86400, o=c, h=c + 1, low=c - 1, c=c, v=v)
        for i, (c, v) in enumerate(zip(closes, volumes))
    ]
    monkeypatch.setattr(technicals, "get_market_data_provider", lambda: _Provider(candles))
    t = technicals.compute_technicals("CROX")
    assert t is not None
    assert t.adv_window == 20
    assert t.adv_dollar == 3_000_000.0
    assert t.adv_as_of == _LAST_BAR


# ── Who sees it ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("agent", list(AgentId) + [None])
def test_only_the_two_desks_see_the_block(monkeypatch, agent):
    monkeypatch.setattr(settings, "room_float_liquidity_enabled", True)
    sheet = room_prompts._format_profile(_sheet_profile(), agent)
    if agent in _TWO_DESKS:
        assert "Float & liquidity: float 14.20M sh" in sheet
        assert f"- {FEED_LABEL}: LIVE" in sheet
    else:
        assert FEED_LABEL not in sheet, agent


def test_each_desk_gets_its_own_use_sentence(monkeypatch):
    monkeypatch.setattr(settings, "room_float_liquidity_enabled", True)
    trader = room_prompts._format_profile(_sheet_profile(), AgentId.TRADER)
    risk = room_prompts._format_profile(_sheet_profile(), AgentId.CONSERVATIVE_DEBATOR)
    assert "discipline the size you propose" in trader
    assert "discipline the size you propose" not in risk
    assert "overhang and liquidity tail risk" in risk


def test_the_block_reaches_the_actual_desk_prompts_and_no_others(monkeypatch, base_mandate):
    monkeypatch.setattr(settings, "room_float_liquidity_enabled", True)
    profile = _sheet_profile()
    for agent in (AgentId.TRADER, AgentId.CONSERVATIVE_DEBATOR, AgentId.AGGRESSIVE_DEBATOR,
                  AgentId.NEUTRAL_DEBATOR, AgentId.PORTFOLIO_MANAGER, AgentId.BULL_RESEARCHER):
        system_prompt, _ = room_prompts.build_room_messages(
            agent_id=agent, mandate=base_mandate, user_id=None, ticker="CROX",
            profile=profile, transcript=[],
        )
        assert (FEED_LABEL in system_prompt) == (agent in _TWO_DESKS), agent


def test_the_structured_risk_officer_prompt_does_not_carry_it(monkeypatch):
    monkeypatch.setattr(settings, "room_float_liquidity_enabled", True)
    sheet = room_prompts._format_profile(_sheet_profile(), AgentId.RISK_OFFICER)
    assert FEED_LABEL not in sheet


# ── Flag off ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("agent", list(AgentId) + [None])
def test_flag_off_is_byte_identical_to_a_sheet_with_no_float_data(monkeypatch, agent):
    monkeypatch.setattr(settings, "room_float_liquidity_enabled", False)
    with_data = _sheet_profile()
    without = {"field_state": {"run_date": "live"}, "run_date": "2026-11-22"}
    assert room_prompts._format_profile(with_data, agent) == room_prompts._format_profile(without, agent)


def test_flag_off_prompts_are_byte_identical_end_to_end(monkeypatch, base_mandate):
    monkeypatch.setattr(settings, "room_float_liquidity_enabled", False)
    with_data = _sheet_profile()
    without = {"field_state": {"run_date": "live"}, "run_date": "2026-11-22"}
    for agent in _TWO_DESKS:
        a = room_prompts.build_room_messages(
            agent_id=agent, mandate=base_mandate, user_id=None, ticker="CROX",
            profile=with_data, transcript=[],
        )
        b = room_prompts.build_room_messages(
            agent_id=agent, mandate=base_mandate, user_id=None, ticker="CROX",
            profile=without, transcript=[],
        )
        assert a == b


def test_flag_off_the_overlay_reads_and_writes_nothing(monkeypatch):
    monkeypatch.setattr(settings, "room_float_liquidity_enabled", False)
    monkeypatch.setattr(settings, "use_real_market_data", True)

    def _boom(ticker):
        raise AssertionError("flag off must not read the company profile")

    monkeypatch.setattr(room_runner, "get_company_profile", _boom)
    profile, field_state = {}, {}
    room_runner._overlay_float_liquidity(profile, field_state, "CROX", None, None)
    assert profile == {} and field_state == {}


# ── Not available, degraded loudly ───────────────────────────────────────────


def test_whole_feed_failure_renders_the_header_denial_and_a_reasoned_body_line(monkeypatch):
    monkeypatch.setattr(settings, "room_float_liquidity_enabled", True)
    profile = _sheet_profile(live=False, reason="the company profile could not be read")
    for agent in _TWO_DESKS:
        sheet = room_prompts._format_profile(profile, agent)
        assert f"- {FEED_LABEL}: not available this call — do not supply float or dollar volume from memory" in sheet
        assert f"{FEED_LABEL}: not available: the company profile could not be read." in sheet
        assert "[yfinance" not in sheet


def test_a_hand_built_sheet_with_no_recorded_state_refuses_by_default(monkeypatch):
    monkeypatch.setattr(settings, "room_float_liquidity_enabled", True)
    sheet = room_prompts._format_profile({"field_state": {}, "run_date": "2026-11-22"}, AgentId.TRADER)
    assert "not available: no float/liquidity read was recorded for this sheet" in sheet


# ── The overlay ──────────────────────────────────────────────────────────────


@pytest.fixture
def overlay_on(monkeypatch):
    monkeypatch.setattr(settings, "room_float_liquidity_enabled", True)
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(
        room_runner, "get_company_profile",
        lambda t: SimpleNamespace(ownership=_ownership(), as_of="2026-11-20T09:14:00+00:00"),
    )


_TECH = SimpleNamespace(adv_dollar=3_000_000.0, adv_window=20, adv_as_of="2026-11-20")


def test_overlay_populates_a_live_payload_from_the_cached_profile_and_the_bars(overlay_on):
    profile, field_state = {}, {"technicals": "live"}
    room_runner._overlay_float_liquidity(profile, field_state, "CROX", None, _TECH)
    assert field_state["float_liquidity"] == "live"
    assert profile["float_liquidity"] == _LIVE_PAYLOAD


def test_overlay_is_unavailable_with_a_reason_for_a_past_dated_sheet(overlay_on):
    from datetime import date

    profile, field_state = {}, {}
    room_runner._overlay_float_liquidity(profile, field_state, "CROX", date(2026, 1, 5), _TECH)
    assert field_state["float_liquidity"] == "unavailable"
    assert "live-only" in profile["float_liquidity_unavailable_reason"]
    assert "float_liquidity" not in profile


def test_overlay_is_unavailable_in_mock_mode(overlay_on, monkeypatch):
    monkeypatch.setattr(settings, "use_real_market_data", False)
    profile, field_state = {}, {}
    room_runner._overlay_float_liquidity(profile, field_state, "CROX", None, _TECH)
    assert field_state["float_liquidity"] == "unavailable"
    assert "mock mode" in profile["float_liquidity_unavailable_reason"]


def test_overlay_survives_an_unreadable_profile_and_keeps_the_bars_half(overlay_on, monkeypatch):
    def _raise(t):
        raise RuntimeError("yfinance down")

    monkeypatch.setattr(room_runner, "get_company_profile", _raise)
    profile, field_state = {}, {"technicals": "live"}
    room_runner._overlay_float_liquidity(profile, field_state, "CROX", None, _TECH)
    assert field_state["float_liquidity"] == "live"
    data = profile["float_liquidity"]
    assert "float_shares" not in data and "float_reason" in data
    assert data["adv_dollar"] == 3_000_000.0


def test_overlay_with_nothing_resolved_is_unavailable_with_both_reasons(overlay_on, monkeypatch):
    monkeypatch.setattr(room_runner, "get_company_profile", lambda t: None)
    profile, field_state = {}, {"technicals": "withheld_tenure"}
    room_runner._overlay_float_liquidity(profile, field_state, "CROX", None, None)
    assert field_state["float_liquidity"] == "unavailable"
    reason = profile["float_liquidity_unavailable_reason"]
    assert "no company profile is cached" in reason
    assert "daily price bars were not fetched this session" in reason


# ── Keying: bank policy version + frozen sheet ───────────────────────────────


def test_the_flag_is_a_bank_policy_setting_and_moves_the_policy_version(monkeypatch):
    assert "room_float_liquidity_enabled" in room_bank.ROOM_POLICY_SETTINGS
    monkeypatch.setattr(settings, "room_float_liquidity_enabled", False)
    off = room_bank.policy_version()
    monkeypatch.setattr(settings, "room_float_liquidity_enabled", True)
    on = room_bank.policy_version()
    assert off != on


def test_the_payload_survives_the_frozen_sheet_round_trip_so_it_is_keyed_by_the_sheet_hash():
    profile = _sheet_profile()
    assert decode_profile(encode_profile(profile)) == profile


# ── Wiring ───────────────────────────────────────────────────────────────────


def test_the_flag_is_forwarded_in_compose_and_listed_in_the_beta_env_example():
    root = Path(__file__).resolve().parents[3]
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    assert "ROOM_FLOAT_LIQUIDITY_ENABLED: ${ROOM_FLOAT_LIQUIDITY_ENABLED:-false}" in compose
    beta = (root / "infra" / "beta.env.example").read_text(encoding="utf-8")
    assert "ROOM_FLOAT_LIQUIDITY_ENABLED" in beta


def test_the_flag_defaults_off():
    assert type(settings).model_fields["room_float_liquidity_enabled"].default is False
