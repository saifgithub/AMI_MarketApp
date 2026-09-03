"""CR197 — the sized-option ladder that replaces the debate's arithmetic.

The ablation established that the risk debate's contribution to the DECISION is a
menu: strip it and the CIO, left with the Execution Desk's single size, refuses trades
it would otherwise approve (16.3% → 7.4%, p=0.004). The menu itself was never the
model's to invent — `risk_debator_sizes` computes it in code — so what the LLM was
adding was the arithmetic about it, which is the one thing it has repeatedly got wrong
(DEF066, DEF235, DEF241, CR166 Tier D; CR154 hand-read 4 of 9 numeric claims wrong).

These tests pin the two properties that make the ladder safe to substitute:

  1. every figure is computed, and matches the functions the safety floor enforces
     against, so the menu cannot drift from the ceilings that will judge the choice;
  2. it is offered as options and NOT as a decision — the rungs are explicitly not
     exhaustive, because 26% of observed approvals land between them.
"""

from __future__ import annotations

import pytest

from app.schemas.agents import AgentId
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_prompts import _render_option_ladder, build_room_messages
from app.trading_math.option_ladder import (
    build_option_ladder,
    reward_to_risk,
)
from app.trading_math.risk import drawdown_contribution
from app.trading_math.sizing import risk_debator_sizes

_CAP = 30.0


def _ladder(**kw):
    args = dict(
        reference_size_pct=3.0, entry=100.0, stop=94.0, target=113.0,
        cap_pts=_CAP, current_drawdown_pct=0.0,
    )
    args.update(kw)
    return build_option_ladder(**args)


# ── the rungs are the same spread the officers argue ─────────────────────────


def test_the_rungs_are_exactly_the_officers_spread():
    """If the menu and the debate disagreed about what the options ARE, swapping one
    for the other would change more than who does the arithmetic."""
    spread = risk_debator_sizes(3.0)
    assert [r.size_pct for r in _ladder()] == [
        spread.conservative, spread.neutral, spread.aggressive
    ]


def test_rows_are_ordered_smallest_first():
    sizes = [r.size_pct for r in _ladder()]
    assert sizes == sorted(sizes)


# ── every figure is computed, and agrees with the enforcing math ─────────────


@pytest.mark.parametrize("size", [1.5, 3.0, 5.0])
def test_contribution_matches_the_function_the_floor_uses(size):
    row = next(r for r in _ladder() if r.size_pct == size)
    expected = drawdown_contribution(size, 100.0, 94.0)
    assert row.contribution_pts == pytest.approx(expected.contribution_pts)


def test_headroom_is_precomputed_not_left_as_a_subtraction():
    """CR179 Leg 4's finding: agents asked to subtract the contribution from the
    headroom got it wrong, including attaching one position's figure to another's
    size. The remainder is supplied."""
    row = next(r for r in _ladder(current_drawdown_pct=4.0) if r.size_pct == 3.0)
    assert row.headroom_after_pts == pytest.approx(_CAP - 4.0 - row.contribution_pts)


def test_no_drawdown_supplied_means_no_headroom_claimed():
    """CR040/DEF053: absent beats fabricated. Assuming a flat book is how DEF292's
    'the risk budget is effectively empty' reading got made."""
    assert all(r.headroom_after_pts is None for r in _ladder(current_drawdown_pct=None))
    assert all(r.contribution_pts is not None for r in _ladder(current_drawdown_pct=None))


# ── §13(a): per-rung dollar risk, so no agent ever multiplies ────────────────


def test_dollar_risk_is_the_same_expression_the_option_budget_uses():
    """`portfolio_value * contribution_pts / 100` — the identical arithmetic
    already computed once, for one size only, at the option-strategist budget
    site (`room_runner.py`'s `budget = round(portfolio_value *
    contribution.contribution_pts / 100.0, 2)`). Pinned per rung here so a
    future edit to either site is caught by drift, not by inspection."""
    rows = _ladder(portfolio_value=100_000.0)
    for r in rows:
        assert r.dollar_risk_usd == pytest.approx(
            round(100_000.0 * r.contribution_pts / 100.0, 2)
        )
    # And the concrete figures, so a silent formula change still fails loudly.
    by_size = {r.size_pct: r.dollar_risk_usd for r in rows}
    assert by_size[1.5] == pytest.approx(90.0)
    assert by_size[3.0] == pytest.approx(180.0)
    assert by_size[5.0] == pytest.approx(300.0)


def test_no_portfolio_value_means_no_dollar_risk_claimed():
    """CR219 R59-§13(a)'s load-bearing caution: a figure this function cannot
    honestly compute stays None, never a fabricated $0 — the same rule
    `headroom_after_pts` already follows for a missing `current_drawdown_pct`."""
    rows = _ladder()  # portfolio_value not supplied at all
    assert all(r.dollar_risk_usd is None for r in rows)
    assert all(r.contribution_pts is not None for r in rows)  # the OTHER figures still compute


def test_a_zero_portfolio_value_also_means_no_dollar_risk():
    """Zero is not a real portfolio value any more than None is — both are
    'unusable', not 'a book worth $0'. Mirrors `_cap_in_shares_clause`'s
    `if not portfolio_value or portfolio_value <= 0` guard exactly."""
    assert all(r.dollar_risk_usd is None for r in _ladder(portfolio_value=0.0))


def test_a_negative_portfolio_value_also_means_no_dollar_risk():
    assert all(r.dollar_risk_usd is None for r in _ladder(portfolio_value=-1.0))


def test_an_incoherent_proposal_costs_the_dollar_figure_too():
    """When `contribution_pts` itself is None (incoherent stop), the dollar
    risk derived from it must also be None — there is nothing honest to
    multiply a real portfolio value by."""
    rows = _ladder(entry=100.0, stop=0.0, portfolio_value=100_000.0)
    assert all(r.contribution_pts is None for r in rows)
    assert all(r.dollar_risk_usd is None for r in rows)


def test_reward_risk_is_carried_on_every_row():
    rows = _ladder()
    assert all(r.reward_risk == pytest.approx(13.0 / 6.0) for r in rows)


@pytest.mark.parametrize(
    "entry,stop,target",
    [(100.0, 100.0, 113.0), (100.0, 101.0, 113.0), (100.0, 94.0, 99.0), (0.0, 0.0, 1.0)],
)
def test_incoherent_level_triples_yield_no_ratio(entry, stop, target):
    """A stop at or above entry is a malformed proposal. A ratio computed from it
    would be a fabricated reassurance, so None is the honest output."""
    assert reward_to_risk(entry, stop, target) is None


def test_no_target_means_no_ratio_rather_than_a_guess():
    assert all(r.reward_risk is None for r in _ladder(target=None))


def test_a_nonsensical_proposal_costs_the_figures_not_the_rows():
    rows = _ladder(entry=100.0, stop=0.0)
    assert [r.size_pct for r in rows]
    assert all(r.contribution_pts is None for r in rows)
    assert all(r.headroom_after_pts is None for r in rows)


def test_the_press_rung_respects_the_absolute_backstop():
    rows = build_option_ladder(
        reference_size_pct=49.0, entry=100.0, stop=94.0, cap_pts=_CAP, backstop_pct=50.0
    )
    assert max(r.size_pct for r in rows) <= 50.0


# ── rendering: options, never a decision ─────────────────────────────────────


def test_the_block_says_the_rungs_are_not_the_only_sizes():
    """26% of observed approvals land between rungs. A menu presented as closed
    would be MORE constraining than the prose it replaces."""
    text = _render_option_ladder(_ladder(), _CAP)
    assert "not the only sizes permitted" in text
    assert "land between them" in text


def test_the_block_claims_the_arithmetic_as_amis_own():
    text = _render_option_ladder(_ladder(), _CAP)
    assert "AMI computed" in text
    assert "do not" in text and "recompute" in text


def test_the_block_repeats_the_def066_warning():
    """DEF066's error — a raw stop distance compared against the portfolio cap —
    made 16 of 64 benchmark names un-buyable and has recurred four times."""
    assert "never compare a raw stop distance against the cap" in _render_option_ladder(
        _ladder(), _CAP
    )


def test_share_of_cap_never_rounds_a_real_contribution_to_zero():
    """DEF292: `:.0f` printed '(~0% of it)' for 40 nonzero contributions, and an
    Aggressive read it as 'the risk budget is effectively empty and ours to fill'.
    The renderer must go through `_share_of_cap_phrase`, which floors at one decimal."""
    text = _render_option_ladder(_ladder(), _CAP)
    assert "(0% of it)" not in text
    assert "(0.3% of it)" in text  # the 1.5% rung: 0.09 pt of 30


def test_empty_rows_render_nothing():
    assert _render_option_ladder([], _CAP) == ""


# ── scope: only the agent that must choose a size gets the menu ──────────────


@pytest.fixture(autouse=True)
def _ladder_on(monkeypatch):
    """The ladder ships gated OFF — it is a measured behaviour change (approvals
    16.3% -> 21.1%), not a pure fix. These tests exercise it enabled; the default
    itself is pinned by `test_the_ladder_is_off_by_default` below."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "pm_option_ladder_enabled", True)


def _prompt(agent_id: AgentId, *, proposal=None):
    system, _ = build_room_messages(
        agent_id=agent_id,
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        user_id=None,
        ticker="MSFT",
        profile={"base_price": 100.0},
        transcript=[],
        trade_proposal=(
            {"size_pct": 3.0, "entry": 100.0, "stop": 94.0, "target": 113.0}
            if proposal is None else proposal
        ),
        agent_size_pct=3.0,
        current_drawdown_pct=0.0,
    )
    return system


def test_the_decision_maker_gets_the_ladder():
    assert "## Sized options" in _prompt(AgentId.PORTFOLIO_MANAGER)


@pytest.mark.parametrize(
    "agent_id",
    [
        AgentId.AGGRESSIVE_DEBATOR,
        AgentId.CONSERVATIVE_DEBATOR,
        AgentId.NEUTRAL_DEBATOR,
        AgentId.TRADER,
        AgentId.BULL_RESEARCHER,
        AgentId.RESEARCH_MANAGER,
    ],
)
def test_nobody_else_does(agent_id):
    """The risk officers already carry their own figure via `agent_size_pct`. Handing
    them the whole menu would replace the judgement their turn exists to exercise —
    and the ablation showed the CIO is the one who needs the options."""
    assert "## Sized options" not in _prompt(agent_id)


def test_the_ladder_precedes_the_transcript():
    """Computed figures placed after eleven turns of prose read as one more voice's
    claim. The menu is a fact about the mandate and sits with the snapshot."""
    text = _prompt(AgentId.PORTFOLIO_MANAGER)
    assert text.index("## Sized options") < text.index("Transcript so far:")


def test_no_proposal_means_no_ladder():
    """Before EXECUTION there is nothing to size, and a ladder built on zeros would
    invent a reference position that no one proposed."""
    assert "## Sized options" not in _prompt(AgentId.PORTFOLIO_MANAGER, proposal={})


def test_a_malformed_proposal_suppresses_the_ladder_entirely():
    text = _prompt(
        AgentId.PORTFOLIO_MANAGER,
        proposal={"size_pct": 3.0, "entry": 100.0, "stop": 120.0},
    )
    assert "## Sized options" not in text


def test_the_ladder_is_off_by_default():
    """A change that moves the approval rate ~5pp and thins interpolation from 32%
    to 11% of approvals is an operator's call, not a silent upgrade."""
    from app.core.config import Settings

    assert Settings().pm_option_ladder_enabled is False


def test_the_flag_actually_gates_it(monkeypatch):
    """A gate nothing tests is a gate that quietly stops gating."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "pm_option_ladder_enabled", False)
    assert "## Sized options" not in _prompt(AgentId.PORTFOLIO_MANAGER)
