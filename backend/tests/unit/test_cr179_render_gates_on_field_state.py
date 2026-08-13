"""CR179 Leg 0 — two render sites that read a value on PRESENCE, not provenance.

CR104 made `field_state` the single per-field provenance mechanism: a value is
rendered only when its key says `live`, and absence means "not available"
rather than "render it anyway". `_field_is_live` is that gate. Two sites never
consulted it, and both were found by constructing the profile rather than by
reading the code — the combinations are unreachable from
`_profile_for_ticker` today, which is exactly why nothing had caught them:

  * `_sector_line` gated `sector` and rendered `industry` beside it ungated, so
    `field_state["industry"] == "unavailable"` still produced
    `Sector/industry (LIVE): Technology / GHOST-INDUSTRY`. A `(LIVE)` label over
    an unavailable value is worse than no line at all — it is precisely the
    fabrication the label exists to prevent, and the runner has always written
    that key (`room_runner.py:541-545`) with nothing reading it.

  * `_net_position_line` read `net_cash` on presence alone, rendering
    `Net debt $42000M` as fact under a header stating none was available live
    this call.

Both functions' contracts say they make no assumption about their caller, so
"unreachable from today's producer" is not a defence: it is the same
one-producer-away reasoning that DEF278 disproved on migrations. These tests
pin the gate in BOTH directions — live renders, unavailable does not — because
a gate asserted only in the refusing direction can be satisfied by a function
that renders nothing at all.
"""

from __future__ import annotations

from app.services.room_prompts import _net_position_line, _sector_line


def _profile(**state):
    return {"field_state": dict(state)}


class TestSectorIndustryGate:
    def test_unavailable_industry_is_not_rendered_under_a_live_label(self):
        line = _sector_line(
            {"sector": "Technology", "industry": "GHOST-INDUSTRY",
             **_profile(sector="live", industry="unavailable")}
        )
        assert "GHOST-INDUSTRY" not in line, (
            "an industry whose field_state says unavailable was rendered anyway, "
            "under a (LIVE) label — CR104's presence-only residue"
        )
        assert line == "Sector/industry (LIVE): Technology / —"

    def test_live_industry_still_renders(self):
        """The other direction: a gate that refuses everything is not a gate."""
        line = _sector_line(
            {"sector": "Technology", "industry": "Consumer Electronics",
             **_profile(sector="live", industry="live")}
        )
        assert line == "Sector/industry (LIVE): Technology / Consumer Electronics"

    def test_an_absent_industry_key_reads_as_not_live(self):
        """CR104's default is refusal: no key ⇒ not live ⇒ the em-dash."""
        line = _sector_line({"sector": "Technology", **_profile(sector="live")})
        assert line == "Sector/industry (LIVE): Technology / —"

    def test_the_whole_line_still_disappears_when_the_sector_is_not_live(self):
        assert _sector_line(
            {"sector": "Technology", "industry": "Consumer Electronics",
             **_profile(sector="unavailable", industry="live")}
        ) is None


class TestNetPositionGate:
    def test_unavailable_net_cash_is_not_stated_as_a_figure(self):
        line = _net_position_line({"net_cash": -42000, **_profile(net_cash="unavailable")})
        assert "42000" not in line, (
            "a net_cash whose field_state says unavailable was rendered as fact"
        )
        assert line == "Balance sheet: net cash not available"

    def test_live_net_debt_still_renders_sign_aware(self):
        line = _net_position_line({"net_cash": -42000, **_profile(net_cash="live")})
        assert line == "Net debt $42000M"

    def test_live_net_cash_still_renders_sign_aware(self):
        """Sign-awareness is the original point of this line (never
        'Net cash: $-42000M'), and the new gate must not disturb it."""
        line = _net_position_line({"net_cash": 944, **_profile(net_cash="live")})
        assert line.startswith("Net cash")
        assert "944" in line

    def test_an_absent_net_cash_key_reads_as_not_live(self):
        assert _net_position_line({"net_cash": 944}) == "Balance sheet: net cash not available"
