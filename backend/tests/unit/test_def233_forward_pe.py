"""DEF233 — the fact sheet carried only the trailing P/E, so the Room reasoned
about valuation from the one figure that argues against entry.

Found live: Saiful ran KTOS on his own account and the PM rejected it on *"the
severe valuation disconnect: a 357.5x P/E"*. Every number in that run was
correct — 357.47 is the real trailing multiple. KTOS's forward P/E is 54.4, and
`fundamentals.py` never fetched `forwardPE` on either surface. Measured over a
10-name sample, trailing ÷ forward ran 1.6×–6.6× (median ~3.3×) with no name
running the other way, so the omission is one-directional: the sheet supplied
the bearish figure and withheld the bullish one. Same asymmetry class as DEF227
(direction-blind trend), one field over.

The fix is deliberately NOT a swap. Forward P/E is an analyst estimate and
CR104/DEF123 exist so an estimate never renders with a measurement's authority,
so both bases are carried, each labelled, each gated on its own `field_state`
entry — the tests below assert the labelling and the gating, not just the
presence of a second number.

Ticker shapes used here are real yfinance responses read on 2026-08-07:
KTOS 357.47/54.39, NBIS 72.86/-86.97, LCID None/-1.41, MU 19.83/5.64.
"""

from __future__ import annotations

import sys
import types

import pytest

from app.core.config import settings
from app.services import fundamentals, room_runner
from app.services.fundamentals import build_live_data_block, fetch_live_fundamentals, pe_line
from app.services.room_prompts import _format_profile
from app.services.room_runner import _forward_pe_clause, _profile_for_ticker


def _fake_yf(info: dict):
    return types.SimpleNamespace(
        __version__="1.2.3",
        Ticker=lambda t: types.SimpleNamespace(info=info),
    )


@pytest.fixture
def live(monkeypatch):
    """Real fetcher + real renderers, driven by a stubbed yfinance `info`."""
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(settings, "suppress_analyst_consensus", True)

    def _install(info: dict):
        monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(info))
        return info

    return _install


_KTOS = {"currentPrice": 60.77, "trailingPE": 357.47058, "forwardPE": 54.385666}
_NBIS = {"currentPrice": 128.4, "trailingPE": 72.85659, "forwardPE": -86.965576}
_LCID = {"currentPrice": 2.11, "forwardPE": -1.4113873}
_MU = {"currentPrice": 178.2, "trailingPE": 19.83209, "forwardPE": 5.641249}


# ── the fetcher ───────────────────────────────────────────────────────────────


def test_forward_pe_is_fetched_alongside_trailing(live):
    live(_KTOS)
    data = fetch_live_fundamentals("KTOS")
    assert data["pe"] == "357.5"
    assert data["forward_pe"] == "54.4"


def test_a_negative_forward_multiple_is_treated_as_absent(live):
    """NBIS's real response: a valid trailing multiple beside a forward figure
    that is negative because consensus forecasts a loss. Rendering "-87.0x
    forward" would be a worse input than the omission this defect fixes."""
    live(_NBIS)
    data = fetch_live_fundamentals("NBIS")
    assert data["pe"] == "72.9"
    assert "forward_pe" not in data


def test_a_loss_maker_with_no_trailing_and_a_negative_forward_carries_neither(live):
    live(_LCID)
    data = fetch_live_fundamentals("LCID")
    assert "pe" not in data
    assert "forward_pe" not in data


# ── the shared line composer ──────────────────────────────────────────────────


def test_both_bases_are_labelled_for_what_they_are():
    line = pe_line("357.5", "54.4")
    assert "357.5 trailing (measured" in line
    assert "54.4 forward (CONSENSUS ESTIMATE" in line
    assert "not a measurement" in line


def test_an_absent_forward_basis_is_stated_not_dropped():
    line = pe_line("357.5", None)
    assert "357.5 trailing" in line
    assert "forward not available — do not estimate one" in line


def test_an_absent_trailing_basis_is_stated_not_papered_over_with_the_forward():
    line = pe_line(None, "54.4")
    assert "trailing not available" in line
    assert "54.4 forward" in line


def test_neither_basis_renders_the_bare_not_available_line():
    assert pe_line(None, None) == "P/E: not available"


def test_the_two_bases_are_never_merged_into_one_number():
    """Non-vacuity: the line must carry both figures verbatim, so a future
    'simplification' that averages, picks one, or drops one goes red here."""
    line = pe_line("19.8", "5.6")
    assert "19.8" in line and "5.6" in line
    other = pe_line("19.8", "9.9")
    assert line != other, "the forward figure does not reach the rendered line"


# ── both surfaces ─────────────────────────────────────────────────────────────


def test_the_ktos_live_failure_now_carries_both_bases_on_both_surfaces(live):
    """The exact run that filed this defect. The verdict was not wrong about
    the number it was given; it was given the wrong number to reason from."""
    live(_KTOS)
    one_on_one = build_live_data_block("KTOS")
    room = _format_profile(_profile_for_ticker("KTOS"))
    for surface in (one_on_one, room):
        assert "357.5 trailing" in surface
        assert "54.4 forward" in surface


def test_the_room_never_shows_a_forward_multiple_the_fetcher_did_not_supply(live):
    live(_NBIS)
    room = _format_profile(_profile_for_ticker("NBIS"))
    assert "72.9 trailing" in room
    assert "forward not available" in room
    assert "86.9" not in room and "-87" not in room


def test_a_forward_figure_with_no_recorded_provenance_is_refused(live):
    """CR104's gate, applied to the new field: a hand-built profile carrying
    `forward_pe` with no `field_state` entry renders as not-available. Refusal
    is the default — presence is never provenance."""
    profile = {
        "pe": "357.5",
        "forward_pe": "54.4",
        "field_state": {"pe": "live"},
    }
    rendered = _format_profile(profile)
    assert "357.5 trailing" in rendered
    assert "54.4" not in rendered
    assert "forward not available" in rendered


def test_the_profile_records_forward_pe_provenance_when_it_is_live(live):
    live(_MU)
    profile = _profile_for_ticker("MU")
    assert profile["forward_pe"] == "5.6"
    assert profile["field_state"]["forward_pe"] == "live"


# ── the PEG denominator ───────────────────────────────────────────────────────


def test_peg_carries_the_trailing_label_when_the_provider_declares_the_basis(live):
    live({**_MU, "trailingPegRatio": 0.1209})
    data = fetch_live_fundamentals("MU")
    assert data["peg_basis"] == "trailing"
    assert "PEG 0.12 (trailing basis)" in build_live_data_block("MU")
    assert "PEG 0.12 (trailing basis)" in _format_profile(_profile_for_ticker("MU"))


def test_the_legacy_peg_key_claims_no_basis_it_does_not_declare(live):
    """yfinance's pre-1.x `pegRatio` does not state its denominator, so the
    label is withheld rather than assumed to match `trailingPegRatio`'s."""
    live({**_MU, "pegRatio": 1.44})
    data = fetch_live_fundamentals("MU")
    assert data["peg_ratio"] == "1.44"
    assert "peg_basis" not in data
    block = build_live_data_block("MU")
    assert "PEG 1.44" in block
    assert "basis)" not in block


# ── the scripted (no-LLM) fallback ────────────────────────────────────────────


def test_the_scripted_fundamentals_sentence_reads_grammatically_either_way():
    assert _forward_pe_clause({"forward_pe": "54.4"}) == ", 54.4x on consensus forward estimates"
    assert _forward_pe_clause({}) == ", forward P/E not available"


def test_the_scripted_template_uses_the_clause_not_a_bare_substitution():
    """A bare `{forward_pe}` would render "not availablex" mid-sentence via the
    scripted backfill — the reason the clause exists."""
    from app.schemas import AgentId

    template = room_runner._TEMPLATES[AgentId.FUNDAMENTALS_ANALYST][0]
    assert "{forward_pe_clause}" in template
    assert "{forward_pe}" not in template


def test_the_fetcher_and_the_prompt_agree_on_the_forward_figure(live):
    """End-to-end on the scripted path: what yfinance returned is what the
    canned sentence states, with no second rounding or reformatting."""
    live(_KTOS)
    profile = _profile_for_ticker("KTOS")
    assert "54.4x on consensus forward estimates" == _forward_pe_clause(profile).lstrip(", ")
