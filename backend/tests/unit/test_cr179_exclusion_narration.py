"""CR152 D7 / CR179 Leg 3 — the sourced exclusions, narrated to the agents.

**The largest "we already have it" gap outside the fact sheet.** DEF061 built a
four-state resolver over a sourced classification of the parent index. It is
fetched on every run (`room_runner.py:3729`), it is enforced by the mandate
check (`room_runner.py:2708`), and it was narrated to nobody: `_compliance_block`
printed the boolean INTENT — *"Exclude fossil fuels (oil & gas majors, coal)"* —
while the identically-shaped halal constraint, two lines above it in the same
function, got a full sourced three-state narration.

**Why that asymmetry is a defect and not a gap.** An agent told only "exclude
fossil fuels", with no way to ask what the screen said about THIS name, has two
options and both are wrong: assume the screen cleared it (DEF084-ROOM's failure
exactly, where narration claimed something enforcement never decided) or state a
verdict it never received. What makes it worse than an ordinary missing field is
that the enforcement is real — so the agent's silence is not tracking anything.

These tests pin the states rather than the wording. What must hold is that each
of the four resolver states produces a DIFFERENT instruction, that UNKNOWN is
never rendered as permission, and that a universe which cannot be resolved
degrades loudly instead of silently reading as "screen passed".
"""

from __future__ import annotations

from datetime import date

import pytest

from app.agents.overlay_generator import _compliance_block, _exclusion_narration
from app.schemas import Compliance
from app.schemas.classification import (
    ClassificationKind,
    ClassificationStatus,
    ClassificationVerdict,
)

_AS_OF = date(2026, 8, 12)
_SOURCE = "yfinance sector/industry"


class _Universe:
    """Stands in for `ClassificationUniverse`, returning one fixed state."""

    def __init__(self, status: ClassificationStatus) -> None:
        self._status = status
        self.calls: list[tuple[str, ClassificationKind]] = []

    def resolve(self, ticker: str, kind: ClassificationKind) -> ClassificationVerdict:
        self.calls.append((ticker, kind))
        return ClassificationVerdict(
            status=self._status, ticker=ticker, kind=kind, source=_SOURCE, as_of=_AS_OF
        )


def _fossil(status: ClassificationStatus, ticker: str = "XOM") -> str:
    return _exclusion_narration(
        _Universe(status), ticker, "fossil_fuels",
        "Exclude fossil fuels", "an oil & gas major or a coal name",
    )


# ── The four states are four different instructions ──────────────────────


def test_the_four_states_produce_four_distinct_narrations():
    """If two states render the same text, the agent cannot act on the
    difference and the whole narration is decoration."""
    texts = {s: _fossil(s) for s in ClassificationStatus}
    assert len({t.lower() for t in texts.values()}) == 4, (
        "two resolver states render identically — the agent cannot distinguish them"
    )


def test_excluded_says_the_mandate_will_not_trade_it():
    text = _fossil(ClassificationStatus.EXCLUDED)
    assert "SCREENED OUT" in text
    assert "will not trade it" in text
    assert _SOURCE in text and _AS_OF.isoformat() in text


def test_permitted_says_it_was_classified_and_passed():
    text = _fossil(ClassificationStatus.PERMITTED)
    assert "PASSES" in text
    assert _SOURCE in text and _AS_OF.isoformat() in text


def test_unknown_is_never_rendered_as_having_cleared_the_screen():
    """DEF084-ROOM's failure, in the direction that matters most.

    A name outside the parent set was never classified. Saying it "passes" is a
    claim the screen never made; saying it "fails" is worse. It is permitted AND
    unreviewed, and the narration has to carry both halves or an agent will
    supply the missing one itself.
    """
    text = _fossil(ClassificationStatus.UNKNOWN)
    assert "NOT REVIEWED" in text
    assert "PASSES" not in text
    assert "NOT a ruling" in text
    assert "permitted" in text.lower(), "the permissive half must survive too"
    assert "does not know" in text
    # And it must not scare the agent off the trade either — G3's rule for the
    # halal screen, which applies identically here.
    assert "never imply the trade is risky" in text


def test_unavailable_says_paused_and_forbids_claiming_a_screen_ran():
    text = _fossil(ClassificationStatus.UNAVAILABLE)
    assert "PAUSED" in text
    assert "do NOT tell them it was applied" in text


# ── Degrade loudly (CR040) ───────────────────────────────────────────────


@pytest.mark.parametrize("universe", [None, object(), set(), {"XOM"}])
def test_a_universe_with_no_resolver_degrades_loudly(universe):
    """Silence here is what lets an agent assume a screen ran.

    A bare set has no provenance and cannot answer per-ticker; the agent is told
    the filter could not be confirmed rather than being left to infer.
    """
    text = _exclusion_narration(
        universe, "XOM", "fossil_fuels", "Exclude fossil fuels", "an oil & gas major",
    )
    assert "NOT attached" in text
    assert "do not treat any name as screened or as cleared" in text


def test_a_resolver_that_raises_does_not_take_the_prompt_down():
    class _Exploding:
        def resolve(self, ticker, kind):
            raise RuntimeError("classification store is having a day")

    text = _exclusion_narration(
        _Exploding(), "XOM", "fossil_fuels", "Exclude fossil fuels", "an oil & gas major",
    )
    assert "could not resolve" in text
    assert "do not treat any name as screened" in text


# ── Wiring: the block asks the right question for each flag ──────────────


def test_each_mandate_flag_resolves_its_own_kind():
    universe = _Universe(ClassificationStatus.PERMITTED)
    _compliance_block(
        Compliance(no_fossil_fuels=True, no_tobacco_alcohol_gambling=True, esg_lite=True),
        ticker="XOM",
        classification_universe=universe,
    )
    kinds = {k for _, k in universe.calls}
    assert kinds == {
        ClassificationKind.FOSSIL_FUELS,
        ClassificationKind.SIN,
        ClassificationKind.ESG_LITE,
    }, f"a mandate flag resolved the wrong exclusion kind: {kinds}"


def test_a_flag_that_is_off_asks_nothing():
    universe = _Universe(ClassificationStatus.PERMITTED)
    _compliance_block(
        Compliance(no_fossil_fuels=True), ticker="XOM", classification_universe=universe
    )
    assert {k for _, k in universe.calls} == {ClassificationKind.FOSSIL_FUELS}


def test_the_ticker_under_discussion_reaches_the_resolver():
    """The narration must be about THIS name. A per-ticker verdict rendered for
    the wrong ticker is worse than no verdict."""
    universe = _Universe(ClassificationStatus.EXCLUDED)
    text = _compliance_block(
        Compliance(no_fossil_fuels=True), ticker="CVX", classification_universe=universe
    )
    assert universe.calls[0][0] == "CVX"
    assert "CVX" in text


def test_the_boolean_intent_line_is_gone():
    """The exact string this defect is about. Its survival anywhere in the block
    would mean an agent is still being told the rule without the verdict."""
    text = _compliance_block(
        Compliance(no_fossil_fuels=True),
        ticker="XOM",
        classification_universe=_Universe(ClassificationStatus.EXCLUDED),
    )
    assert "Exclude fossil fuels (oil & gas majors, coal)." not in text


def test_the_narration_cannot_contradict_what_enforcement_decided():
    """Single-sourcing, asserted rather than assumed.

    The narration and the mandate check resolve against the SAME object, so a
    universe that says EXCLUDED cannot produce a prompt that says the name
    passed — which is precisely the contradiction DEF084-ROOM was, pointing the
    other way.
    """
    for status, forbidden in (
        (ClassificationStatus.EXCLUDED, "PASSES"),
        (ClassificationStatus.PERMITTED, "SCREENED OUT"),
    ):
        text = _compliance_block(
            Compliance(no_fossil_fuels=True),
            ticker="XOM",
            classification_universe=_Universe(status),
        )
        assert forbidden not in text, f"{status.value} narrated as {forbidden}"


# ── End-to-end: it must actually REACH the prompt ────────────────────────


def _room_prompt(base_mandate, universe):
    from app.schemas import AgentId
    from app.services.room_prompts import build_room_messages

    base_mandate.compliance.no_fossil_fuels = True
    system_prompt, _ = build_room_messages(
        agent_id=AgentId.PORTFOLIO_MANAGER,
        mandate=base_mandate,
        user_id=None,
        ticker="XOM",
        profile={"ticker": "XOM", "field_state": {}},
        transcript=[],
        classification_universe=universe,
    )
    return system_prompt


def test_the_verdict_reaches_a_real_assembled_room_prompt(base_mandate):
    """The defect was never that the narration was wrong — it was that the
    object never arrived.

    Every test above exercises `_compliance_block` directly, so all of them
    would pass with the universe still stranded four call frames away in
    `room_runner`. This one drives the real builder end to end, which is the
    only assertion that can fail if the threading breaks.
    """
    universe = _Universe(ClassificationStatus.EXCLUDED)
    system_prompt = _room_prompt(base_mandate, universe)
    assert universe.calls, "the classification universe never reached the prompt builder"
    assert "SCREENED OUT" in system_prompt
    assert _SOURCE in system_prompt


def test_without_threading_the_prompt_degrades_loudly_rather_than_silently(base_mandate):
    """The pre-fix state, asserted: no universe passed means the agent is TOLD
    the screen could not be confirmed — never left with a bare rule it might
    read as 'a screen ran and it passed'."""
    system_prompt = _room_prompt(base_mandate, None)
    assert "NOT attached" in system_prompt


# ── CR152 D8 — the locale universe, which can veto a trade in silence ────


def _locale_lines(base_mandate, universe):
    from app.schemas import AgentId
    from app.services.room_prompts import build_room_messages

    system_prompt, _ = build_room_messages(
        agent_id=AgentId.PORTFOLIO_MANAGER,
        mandate=base_mandate,
        user_id=None,
        ticker="AAPL",
        profile={"ticker": "AAPL", "field_state": {}},
        transcript=[],
        locale_allowed_universe=universe,
    )
    return [ln for ln in system_prompt.splitlines() if "Tradable universe" in ln]


def test_a_ticker_outside_the_locale_universe_is_named_as_unpurchasable(base_mandate):
    """`safety_floor.py:336` blocks the trade with `blocked_by="locale"`.

    Twelve agents could argue a name all the way to a sized APPROVE with no way
    to know it was not purchasable at all — the same unfollowable-by-
    construction shape as the microcap rule before CR145 Tier A supplied market
    cap.
    """
    lines = _locale_lines(base_mandate, {"MSFT", "NVDA"})
    assert lines and "NOT available" in lines[0]
    assert "BLOCKED" in lines[0]


def test_a_ticker_inside_the_locale_universe_says_so(base_mandate):
    lines = _locale_lines(base_mandate, {"AAPL", "MSFT"})
    assert lines and "AAPL is one of them" in lines[0]
    assert "NOT available" not in lines[0]


def test_the_empty_case_is_stated_rather_than_omitted(base_mandate):
    """CR149 A.4's rule. `None` is the alpha default, but an agent reading
    silence cannot tell "no restriction" from "the restriction was not
    attached", and those call for different behaviour."""
    lines = _locale_lines(base_mandate, None)
    assert lines and "no locale restriction is in force" in lines[0]


def test_an_unreadable_locale_universe_degrades_loudly(base_mandate):
    lines = _locale_lines(base_mandate, 42)
    assert lines and "could not read it" in lines[0]


# ── CR152 D9 — the sector allocation eleven agents never saw ─────────────


def _has_sector_line(base_mandate, agent_id):
    from app.services.room_prompts import build_room_messages

    system_prompt, _ = build_room_messages(
        agent_id=agent_id,
        mandate=base_mandate,
        user_id=None,
        ticker="AAPL",
        profile={"ticker": "AAPL", "field_state": {}},
        transcript=[],
        sector_weights={"Technology": 0.62, "Financials": 0.38},
    )
    return "current sector allocation" in system_prompt


def test_every_agent_that_argues_a_size_sees_the_sector_state(base_mandate):
    """All twelve are told the sector-concentration RULE; eleven were never
    told the current STATE.

    Worse than a plain gap, because CR055 injects the real holdings into every
    prompt unconditionally — so an agent could read `GME x500` a few lines up
    and still not know that is 95% of one sector. It had the evidence and not
    the aggregate.
    """
    from app.schemas import AgentId

    for agent in (
        AgentId.PORTFOLIO_MANAGER, AgentId.TRADER, AgentId.BULL_RESEARCHER,
        AgentId.BEAR_RESEARCHER, AgentId.RESEARCH_MANAGER,
        AgentId.AGGRESSIVE_DEBATOR, AgentId.CONSERVATIVE_DEBATOR,
        AgentId.NEUTRAL_DEBATOR,
    ):
        assert _has_sector_line(base_mandate, agent), (
            f"{agent.value} argues or vetoes a size and cannot see the sector state"
        )


def test_the_firewalled_analysts_still_do_not_get_it(base_mandate):
    """Gated on the FULL SHEET, not widened to everyone. The four analysts are
    not asked for a size, and CR145 Tier C's measured 97.5% role-identifiability
    is what their firewall bought — this must not quietly reverse it."""
    from app.schemas import AgentId

    for agent in (
        AgentId.FUNDAMENTALS_ANALYST, AgentId.MARKET_ANALYST,
        AgentId.NEWS_ANALYST, AgentId.SOCIAL_MEDIA_ANALYST,
    ):
        assert not _has_sector_line(base_mandate, agent), (
            f"{agent.value} is firewalled and received cross-lane portfolio data"
        )
