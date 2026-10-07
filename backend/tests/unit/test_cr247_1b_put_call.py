"""CR247 Phase 1B — the put/call ratio, Flow & Positioning lane.

The Social Media Analyst reads what retail SAYS (Reddit) and has never had
what the options market DOES. Both ratios — put/call volume and put/call open
interest — are sums over the nearest listed expiries' chains, computed in code
(CR179 Leg 4: never two operands plus an instruction), with the window and the
contract counts stated on the line.

The rules pinned here:

**Unserved is not zero.** `OptionQuote` carries None for a field the provider
did not serve; summed as zero it would render "0 puts traded" — a confident
claim of no activity where the truth is "the provider did not say". A side
served for no strike makes its ratio absent, not zero.

**A zero CALL leg withholds the ratio.** Put volume over zero call volume is
an infinite ratio, not a large one; the line renders the open-interest half
and says the volume half was not served.

**The window is the sample.** Four nearest expiries, first and last stated; a
failed or synthetic chain in the window fails the whole figure (loudly), so
the stated window is always exactly what was summed.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.core.config import settings
from app.schemas.agents import AgentId
from app.services import put_call, room_prompts
from app.services.market_data import OptionChain, OptionQuote
from app.services.put_call import aggregate_chains, fetch_put_call_ratio, put_call_line

# DEF: this test pinned a fixed "today" (2026-09-29), so the suite started
# failing every day once the calendar passed it (first red 2026-10-06). The
# window is defined RELATIVE to today — the pin must roll with it.
_TODAY = date.today()
_EXPIRIES = [_TODAY + timedelta(days=d) for d in (4, 11, 18, 25, 32)]


def _quote(volume, oi):
    return OptionQuote(
        strike=100.0, bid=1.0, ask=1.2, last=1.1,
        volume=volume, open_interest=oi, implied_vol=0.3,
    )


def _chain(expiry, call_volume=100, put_volume=80, call_oi=1000, put_oi=1100):
    return OptionChain(
        underlying="TEST", expiry=expiry,
        calls=(_quote(call_volume, call_oi), _quote(call_volume, call_oi)),
        puts=(_quote(put_volume, put_oi), _quote(put_volume, put_oi)),
        source="yfinance",
    )


def _chains():
    return [_chain(e) for e in _EXPIRIES[:4]]


# ── The aggregation (pure) ───────────────────────────────────────────────


def test_both_ratios_and_their_counts() -> None:
    out = aggregate_chains(_chains(), _TODAY)
    assert out is not None
    # 4 expiries × 2 strikes: volume 640 puts / 800 calls; OI 8,800 / 8,000
    assert out.volume_ratio == 0.8
    assert out.oi_ratio == 1.1
    assert out.put_volume == 640 and out.call_volume == 800
    assert out.put_open_interest == 8800 and out.call_open_interest == 8000
    assert out.contracts == 16 and out.expiries == 4
    assert out.expiry_first == _EXPIRIES[0] and out.expiry_last == _EXPIRIES[3]
    assert out.chain_date == _TODAY


def test_an_unserved_field_is_absent_not_zero() -> None:
    chains = [
        OptionChain(
            underlying="TEST", expiry=e,
            calls=(_quote(None, 1000),), puts=(_quote(None, 1100),),
            source="yfinance",
        )
        for e in _EXPIRIES[:4]
    ]
    out = aggregate_chains(chains, _TODAY)
    assert out is not None
    assert out.volume_ratio is None and out.put_volume is None
    assert out.oi_ratio == 1.1


def test_a_zero_call_leg_withholds_the_ratio_not_an_infinite_one() -> None:
    # Zero call VOLUME with live open interest: the volume ratio is withheld
    # (a division by zero is an infinite ratio, not a large one), the OI half
    # still computes, and the figure survives.
    chains = [
        OptionChain(
            underlying="TEST", expiry=e,
            calls=(_quote(0, 1000),), puts=(_quote(50, 1100),),
            source="yfinance",
        )
        for e in _EXPIRIES[:4]
    ]
    out = aggregate_chains(chains, _TODAY)
    assert out is not None
    assert out.volume_ratio is None
    assert out.oi_ratio == 1.1
    # …and with nothing computable at all there is no figure.
    chains = [
        OptionChain(
            underlying="TEST", expiry=e,
            calls=(_quote(0, 0),), puts=(_quote(50, 100),),
            source="yfinance",
        )
        for e in _EXPIRIES[:4]
    ]
    assert aggregate_chains(chains, _TODAY) is None


def test_no_chains_is_no_figure() -> None:
    assert aggregate_chains([], _TODAY) is None


# ── The fetch (provider seam) ────────────────────────────────────────────


class _Provider:
    def __init__(self, expiries=_EXPIRIES, chains=None, fail_at=None, source="yfinance"):
        self._expiries = expiries
        self._chains = chains
        self._fail_at = fail_at
        self._source = source

    def expiries(self, ticker):
        return self._expiries

    def option_chain(self, ticker, expiry):
        if self._fail_at is not None and expiry == self._fail_at:
            return None
        if self._chains is not None:
            return self._chains
        return OptionChain(
            underlying=ticker, expiry=expiry,
            calls=(_quote(100, 1000),), puts=(_quote(80, 1100),),
            source=self._source,
        )


def _fetch(monkeypatch, provider) -> object:
    monkeypatch.setattr(put_call, "get_market_data_provider", lambda: provider)
    return fetch_put_call_ratio("TEST")


def test_the_fetch_samples_the_nearest_four_expiries(monkeypatch) -> None:
    out = _fetch(monkeypatch, _Provider())
    assert out is not None
    assert out.expiries == 4
    assert out.expiry_last == _EXPIRIES[3], "the fifth listed expiry is NOT in the window"


def test_no_expiries_is_unavailable(monkeypatch) -> None:
    assert _fetch(monkeypatch, _Provider(expiries=None)) is None
    assert _fetch(monkeypatch, _Provider(expiries=[])) is None


def test_a_failed_chain_in_the_window_fails_the_figure(monkeypatch) -> None:
    """The stated window must be exactly what was summed — no silent hole."""
    assert _fetch(monkeypatch, _Provider(fail_at=_EXPIRIES[1])) is None


def test_a_synthetic_chain_is_refused(monkeypatch) -> None:
    assert _fetch(monkeypatch, _Provider(source="mock_walk")) is None


def test_a_raising_provider_is_unavailable_not_an_exception(monkeypatch) -> None:
    class Boom:
        def expiries(self, ticker):
            raise RuntimeError("network down")

    assert _fetch(monkeypatch, Boom()) is None


# ── The line ─────────────────────────────────────────────────────────────


def test_the_line_states_both_ratios_the_counts_and_the_window() -> None:
    line = put_call_line(aggregate_chains(_chains(), _TODAY))
    assert "Put/call ratio (AMI's own quotient, LIVE)" in line
    assert "volume 0.80 (640 puts / 800 calls)" in line
    assert "open interest 1.10 (8,800 puts / 8,000 calls)" in line
    assert f"4 expiries {_EXPIRIES[0].isoformat()} to {_EXPIRIES[3].isoformat()}" in line
    assert f"chain as of {_TODAY.isoformat()}" in line


def test_an_unserved_half_is_named_on_the_line() -> None:
    chains = [
        OptionChain(
            underlying="TEST", expiry=e,
            calls=(_quote(None, 1000),), puts=(_quote(None, 1100),),
            source="yfinance",
        )
        for e in _EXPIRIES[:4]
    ]
    line = put_call_line(aggregate_chains(chains, _TODAY))
    assert "volume not served by the provider" in line
    assert "open interest 1.10" in line


def test_no_ratio_means_no_line() -> None:
    assert put_call_line(None) is None


# ── The render seam (Flow & Positioning lane) ────────────────────────────


def _profile(**overrides) -> dict:
    profile = {
        "field_state": {"put_call": "live"},
        "put_call_ratio": aggregate_chains(_chains(), _TODAY),
        "sentiment_tone": "moderately bullish",
        "sentiment_score": "typical intensity (illustrative)",
    }
    profile.update(overrides)
    return profile


@pytest.fixture(autouse=True)
def _flag_restored():
    before = settings.room_put_call_enabled
    yield
    settings.room_put_call_enabled = before


def test_nothing_renders_with_the_flag_off() -> None:
    settings.room_put_call_enabled = False
    sheet = room_prompts._format_profile(_profile(), AgentId.SOCIAL_MEDIA_ANALYST)
    assert "Put/call" not in sheet


def test_the_flag_is_on_by_default() -> None:
    """Flipped ON 2026-09-29 (CR247 Phase 1B — unit suite + the live AAPL
    render probe). The env var stays as the kill switch; the flag-off render
    is pinned above."""
    assert settings.room_put_call_enabled is True


def test_the_line_appears_with_the_flag_on() -> None:
    settings.room_put_call_enabled = True
    sheet = room_prompts._format_profile(_profile(), AgentId.SOCIAL_MEDIA_ANALYST)
    assert "Put/call ratio (AMI's own quotient, LIVE)" in sheet
    assert "volume 0.80 (640 puts / 800 calls)" in sheet


def test_a_failed_fetch_states_its_reason() -> None:
    """Degrade loudly: not available WITH the reason, never silently blank."""
    settings.room_put_call_enabled = True
    profile = _profile(
        field_state={"put_call": "unavailable"},
        put_call_ratio=None,
        put_call_unavailable_reason="the provider served no usable option chain",
    )
    sheet = room_prompts._format_profile(profile, AgentId.SOCIAL_MEDIA_ANALYST)
    assert "Put/call ratio: not available this call" in sheet
    assert "the provider served no usable option chain" in sheet
    assert "Do not estimate one from memory" in sheet


def test_presence_is_not_provenance() -> None:
    """A populated ratio with no recorded state renders the not-available
    line, not the figure — CR104/D8, on this field like every other."""
    settings.room_put_call_enabled = True
    profile = _profile(field_state={})
    sheet = room_prompts._format_profile(profile, AgentId.SOCIAL_MEDIA_ANALYST)
    assert "volume 0.80" not in sheet
    assert "Put/call ratio: not available this call" in sheet


def test_out_of_lane_agents_do_not_see_the_line() -> None:
    settings.room_put_call_enabled = True
    sheet = room_prompts._format_profile(_profile(), AgentId.FUNDAMENTALS_ANALYST)
    assert "Put/call" not in sheet


def test_the_unlaned_sheet_carries_the_line() -> None:
    """agent_id=None is the union-of-lanes baseline (the parity guard's)."""
    settings.room_put_call_enabled = True
    sheet = room_prompts._format_profile(_profile())
    assert "Put/call ratio (AMI's own quotient, LIVE)" in sheet


# ── The overlay's stated absences ────────────────────────────────────────


def test_an_as_of_run_states_the_historical_store_reason() -> None:
    """DEF334: a live chain must never land on a past-dated sheet."""
    from app.services import room_runner

    profile: dict = {}
    field_state: dict[str, str] = {}
    room_runner._overlay_put_call(profile, field_state, "AAPL", date(2025, 1, 15))
    assert field_state["put_call"] == "unavailable"
    assert "no historical store" in profile["put_call_unavailable_reason"]


def test_a_mock_data_run_states_the_mock_reason(monkeypatch) -> None:
    from app.services import room_runner

    monkeypatch.setattr(settings, "use_real_market_data", False)
    profile: dict = {}
    field_state: dict[str, str] = {}
    room_runner._overlay_put_call(profile, field_state, "AAPL", None)
    assert field_state["put_call"] == "unavailable"
    assert "mock mode" in profile["put_call_unavailable_reason"]


def test_a_live_fetch_populates_the_block(monkeypatch) -> None:
    from app.services import room_runner

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(put_call, "get_market_data_provider", lambda: _Provider())
    profile: dict = {}
    field_state: dict[str, str] = {}
    room_runner._overlay_put_call(profile, field_state, "TEST", None)
    assert field_state["put_call"] == "live"
    assert profile["put_call_ratio"].volume_ratio == 0.8


def test_a_failed_fetch_carries_its_reason_into_the_profile(monkeypatch) -> None:
    from app.services import room_runner

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(put_call, "get_market_data_provider", lambda: _Provider(expiries=None))
    profile: dict = {}
    field_state: dict[str, str] = {}
    room_runner._overlay_put_call(profile, field_state, "TEST", None)
    assert field_state["put_call"] == "unavailable"
    assert "no usable option chain" in profile["put_call_unavailable_reason"]
