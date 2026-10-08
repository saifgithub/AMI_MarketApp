"""CR253 D29 — the disclosed narrow-SIC peer-group fallback.

AAPL's real case: SIC 3571 (electronic computers) has too few same-SIC
US-listed names for a defensible median, so the Fundamentals lane's "Peer
comparison" line was permanently not-available. D29 lets a hand-maintained
`_PEER_GROUP_BY_SIC` mapping pool candidates across a small set of sibling
SICs — but ONLY when the strict same-SIC screen lands fewer than
`_MIN_PEERS` verified peers, every pooled candidate still live-verified
against its own submissions JSON, and the rendered line + the basket record
name the group basis. A strict success never widens.

The rules pinned here:

**Strict success never widens.** A target whose own SIC assembles three or
more verified peers resolves exactly as before — `group_sics` stays None and
the line never mentions a peer group.

**The fallback is live-verified, not list-trusted.** A pooled candidate
whose own filings read back a SIC outside the group is dropped like any
strict-pass candidate; an unreadable one counts as an unverified fetch
failure, the same throttling-vs-coverage distinction the strict pass makes.

**The widening is disclosed.** A group basket carries `group_sics` and the
rendered line names "the disclosed peer group (SIC 3571/3572)" — never a
silent basket.

**Below the floor on both passes, the reason says so.** The failure reason
names the peer-group basis and the verified count, never a bare "insufficient
peer coverage" that hides the widening was tried.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.config import settings
from app.schemas.agents import AgentId
from app.services import peer_basket, room_prompts, room_runner
from app.services.fundamentals import peer_comparison_line

_T0 = datetime(2026, 10, 8, 12, 0, 0, tzinfo=UTC)

# The 3571 group, built FROM the module's own tuples so a universe edit
# cannot silently desync the fixtures.
_GROUP = peer_basket._PEER_GROUP_BY_SIC["3571"]
_3571 = peer_basket._CANDIDATES_BY_SIC["3571"]
_3572 = peer_basket._CANDIDATES_BY_SIC["3572"]

_QUOTES = {
    "HPE":  {"cap": 2.4e10, "pe": 11.0, "ev": 7.0, "margin": 0.06},
    "HPQ":  {"cap": 3.6e10, "pe": 13.0, "ev": 8.0, "margin": 0.07},
    "DELL": {"cap": 9.0e10, "pe": 18.0, "ev": 11.0, "margin": 0.05},
    "STX":  {"cap": 2.0e10, "pe": 15.0, "ev": 9.0, "margin": 0.10},
    "WDC":  {"cap": 1.8e10, "pe": 17.0, "ev": 10.0, "margin": 0.08},
}


def _install_group_universe(monkeypatch, *, member_sics: dict[str, str | None]):
    """Fake the network surface for a target in SIC 3571.

    `member_sics` maps each group candidate to the SIC its own submissions
    JSON reads back (None = unreadable this call). Every candidate resolves a
    CIK so the submissions fetcher is always reached; quotes serve `_QUOTES`.
    """
    cik_map = {"AAPL": 1}
    sic_by_cik: dict[int, dict | None] = {
        1: {"sic": "3571", "sicDescription": "Electronic Computers"},
    }
    for i, cand in enumerate((*_3571, *_3572)):
        cik = 100 + i
        cik_map[cand] = cik
        sic = member_sics.get(cand)
        sic_by_cik[cik] = {"sic": sic} if sic is not None else None

    monkeypatch.setattr(peer_basket, "resolve_cik", lambda t: cik_map.get(t.upper()))
    peer_basket.set_peer_fetchers(
        submissions=lambda cik: sic_by_cik.get(cik),
        info=lambda t: (
            {
                "marketCap": _QUOTES[t]["cap"],
                "trailingPE": _QUOTES[t]["pe"],
                "enterpriseToEbitda": _QUOTES[t]["ev"],
                "profitMargins": _QUOTES[t]["margin"],
            } if t in _QUOTES else None
        ),
    )
    peer_basket.clear_peer_basket_store()


def _resolve():
    return peer_basket.refresh_peer_basket("AAPL", target_market_cap=5.0e10, now=_T0)


class TestTheFallbackFiresOnlyBelowTheStrictFloor:
    def test_two_strict_peers_pools_the_group(self, monkeypatch):
        """Only HPE and HPQ file 3571 (below the floor of 3); the fallback
        pools 3572 and every group candidate is still live-verified."""
        member_sics = {
            "HPE": "3571", "HPQ": "3571",
            "DELL": "9999", "SMCI": "9999", "IBM": "0100",  # not members
            "STX": "3572", "WDC": "3572", "SNDK": "0100",
        }
        _install_group_universe(monkeypatch, member_sics=member_sics)
        result = _resolve()
        assert result.basket is not None
        basket = result.basket
        assert basket.sic == "3571"
        assert basket.group_sics == ("3571", "3572")
        members = {m.ticker: m for m in basket.members}
        # The strict pair plus the 3572 siblings; non-members never enter.
        assert set(members) == {"HPE", "HPQ", "STX", "WDC"}
        # Each row carries the member's OWN verified SIC, not the target's.
        assert members["STX"].sic == "3572"
        assert members["HPE"].sic == "3571"

    def test_a_strict_success_never_widens(self, monkeypatch):
        """Three verified same-SIC peers is enough — the group mapping must
        not even be consulted, and the basket record stays strict."""
        _install_group_universe(monkeypatch, member_sics={
            "HPE": "3571", "HPQ": "3571", "DELL": "3571",
            "SMCI": "9999", "IBM": "0100",
            "STX": "3572", "WDC": "3572", "SNDK": "3572",
        })
        result = _resolve()
        assert result.basket is not None
        assert result.basket.group_sics is None
        assert {m.ticker for m in result.basket.members} == {"HPE", "HPQ", "DELL"}

    def test_group_membership_is_live_verified_not_list_trusted(self, monkeypatch):
        """Every pooled candidate files a non-group SIC: the fallback finds
        nobody either, and the reason names the group basis and the count."""
        _install_group_universe(monkeypatch, member_sics={
            cand: "0100" for cand in (*_3571, *_3572)
        })
        result = _resolve()
        assert result.basket is None
        reason = result.reason or ""
        assert "insufficient peer coverage" in reason
        assert "peer group SIC 3571/3572" in reason
        assert "0 verified peers" in reason

    def test_unreadable_group_candidates_are_unverified_not_absent(self, monkeypatch):
        _install_group_universe(monkeypatch, member_sics={
            cand: None for cand in (*_3571, *_3572)
        })
        result = _resolve()
        assert result.basket is None
        reason = result.reason or ""
        assert "unverified" in reason
        assert "SIC 3571/3572" in reason

    def test_the_groups_own_sic_is_always_in_the_mapping(self):
        """The fallback is only sound because the target's own SIC is a member
        of its group — the mapping is keyed by it, and this pins the shape so
        a hand-edit cannot map a target into a group that excludes it."""
        for sic, group in peer_basket._PEER_GROUP_BY_SIC.items():
            assert sic in group


# ── The rendered line ────────────────────────────────────────────────────────


def _line_args(**over):
    args = {
        "ticker": "AAPL", "sic": "3571", "sic_description": "Electronic Computers",
        "basket_size": 5, "basket_as_of": "2026-10-08",
        "median_trailing_pe": 15.0, "n_trailing_pe": 5,
        "median_ev_ebitda": 9.0, "n_ev_ebitda": 5,
        "median_net_margin": 7.0, "n_net_margin": 5,
        "own_trailing_pe": "38.8",
    }
    args.update(over)
    return peer_comparison_line(**args)


def test_the_group_line_discloses_the_basis() -> None:
    line = _line_args(peer_group=("3571", "3572"))
    assert "Peer comparison (LIVE)" in line
    assert "across 5 peers in the disclosed peer group (SIC 3571/3572)" in line
    assert "strict same-SIC screen found fewer than three verified peers" in line
    assert "every member still live-verified" in line


def test_the_strict_line_is_unchanged() -> None:
    line = _line_args()
    assert "across 5 peers in SIC 3571 (Electronic Computers)" in line
    assert "peer group" not in line
    assert "same-4-digit-SIC market-cap neighbours" in line


def test_group_default_is_none_and_renders_strict() -> None:
    """positional callers keep the strict rendering — the new parameter is
    keyword-only with a None default."""
    line = peer_comparison_line(
        "AAPL", "3571", "Electronic Computers", 5, "2026-10-08",
        15.0, 5, 9.0, 5, 7.0, 5, "38.8",
    )
    assert "disclosed peer group" not in (line or "")


# ── The overlay + the sheet ──────────────────────────────────────────────────


@pytest.fixture
def real_market_data():
    prior = settings.use_real_market_data
    settings.use_real_market_data = True
    yield
    settings.use_real_market_data = prior


def _profile_with_live_cap() -> dict:
    return {
        "ticker": "AAPL",
        "market_cap": 50_000,  # $M, the sheet's own convention
        "field_state": {"market_cap": "live"},
    }


def test_the_overlay_carries_the_group_basis(monkeypatch, real_market_data) -> None:
    _install_group_universe(monkeypatch, member_sics={
        "HPE": "3571", "HPQ": "3571", "DELL": "9999", "SMCI": "9999",
        "IBM": "0100", "STX": "3572", "WDC": "3572", "SNDK": "0100",
    })
    profile = _profile_with_live_cap()
    fs = profile["field_state"]
    room_runner._overlay_peer_comparison(profile, fs, "AAPL", None)
    assert fs["peer_comparison"] == "live"
    assert profile["peer_comparison_sic"] == "3571"
    assert profile["peer_comparison_peer_group"] == ["3571", "3572"]


def test_the_overlay_leaves_the_key_absent_on_a_strict_basket(monkeypatch, real_market_data) -> None:
    _install_group_universe(monkeypatch, member_sics={
        "HPE": "3571", "HPQ": "3571", "DELL": "3571",
        "SMCI": "9999", "IBM": "0100",
        "STX": "3572", "WDC": "3572", "SNDK": "3572",
    })
    profile = _profile_with_live_cap()
    fs = profile["field_state"]
    room_runner._overlay_peer_comparison(profile, fs, "AAPL", None)
    assert fs["peer_comparison"] == "live"
    assert "peer_comparison_peer_group" not in profile


def test_the_sheet_discloses_the_group_basis(monkeypatch, real_market_data) -> None:
    _install_group_universe(monkeypatch, member_sics={
        "HPE": "3571", "HPQ": "3571", "DELL": "9999", "SMCI": "9999",
        "IBM": "0100", "STX": "3572", "WDC": "3572", "SNDK": "0100",
    })
    profile = _profile_with_live_cap()
    fs = profile["field_state"]
    room_runner._overlay_peer_comparison(profile, fs, "AAPL", None)
    sheet = room_prompts._format_profile(profile, AgentId.FUNDAMENTALS_ANALYST)
    assert "disclosed peer group (SIC 3571/3572)" in sheet


def test_the_sheet_never_mentions_a_group_for_a_strict_basket(monkeypatch, real_market_data) -> None:
    _install_group_universe(monkeypatch, member_sics={
        "HPE": "3571", "HPQ": "3571", "DELL": "3571",
        "SMCI": "9999", "IBM": "0100",
        "STX": "3572", "WDC": "3572", "SNDK": "3572",
    })
    profile = _profile_with_live_cap()
    fs = profile["field_state"]
    room_runner._overlay_peer_comparison(profile, fs, "AAPL", None)
    sheet = room_prompts._format_profile(profile, AgentId.FUNDAMENTALS_ANALYST)
    assert "peer group" not in sheet
    assert "Peer comparison (LIVE)" in sheet
