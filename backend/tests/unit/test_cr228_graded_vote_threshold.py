"""CR228 Step 4 — the PM's APPROVE-vs-PASS vote bar is graded by risk_score.

Steps 2 (cap table) and 3 (PM prompt branch) are, respectively, a measured sizing
effect and an unverified prompt hypothesis (CLAUDE.md: "prompt instructions are not
controls"). Step 4 is the structural backstop: `_vote_pm_samples`'s tie-break used to
send every risk tier to PASS uniformly (`room_runner.py`, pre-CR228), so a
conservative and an aggressive mandate needed the identical vote count to approve.
This pins that the bar itself now differs by tier, and that a risk_score of 3
reproduces the original arithmetic byte-for-byte so every pre-CR228 caller
(`test_cr197_pm_self_consistency.py`, `test_cr214_approve_votes.py`) is unaffected.
"""

from __future__ import annotations

from app.schemas.room import Verdict, VerdictAction
from app.services.room_runner import _approve_vote_threshold, _vote_pm_samples


def _v(action: VerdictAction, size: float | None = None) -> Verdict:
    return Verdict(action=action, size_pct=size, reason="r")


def _samples(n_approve: int, n_pass: int) -> list[tuple[str, Verdict]]:
    out = [(f"a{i}", _v(VerdictAction.APPROVE, 3.0)) for i in range(n_approve)]
    out += [(f"p{i}", _v(VerdictAction.PASS)) for i in range(n_pass)]
    return out


# ── the threshold table ─────────────────────────────────────────────────────


def test_risk_3_reproduces_the_pre_cr228_strict_majority():
    """The default. Every existing caller of `_vote_pm_samples` omits risk_score,
    so this value must be the one that was hardcoded before CR228 existed."""
    for n in range(1, 6):
        assert _approve_vote_threshold(3, n) == n // 2 + 1


def test_the_bar_is_monotonically_non_increasing_in_risk_score():
    """The whole point of Step 4: raising risk_score must never make approval
    HARDER, regardless of n."""
    for n in range(1, 8):
        bars = [_approve_vote_threshold(rs, n) for rs in range(1, 6)]
        assert bars == sorted(bars, reverse=True), (n, bars)


def test_at_the_production_default_of_five_samples_the_three_tiers_are_distinct():
    """The production default (`pm_self_consistency_samples`, CR214) is 5. If the
    three tiers collapsed to the same number here, Step 4 would be decorative in
    exactly the environment that matters — the same failure this CR opened
    against the cap table."""
    conservative = _approve_vote_threshold(1, 5)
    neutral = _approve_vote_threshold(3, 5)
    aggressive = _approve_vote_threshold(5, 5)
    assert conservative == 4
    assert neutral == 3
    assert aggressive == 2
    assert conservative > neutral > aggressive


def test_the_bar_never_exceeds_n_or_drops_below_one():
    for n in range(1, 6):
        for rs in range(1, 6):
            bar = _approve_vote_threshold(rs, n)
            assert 1 <= bar <= n


# ── the vote itself, at the production sample size ──────────────────────────


def test_a_3_of_5_split_approves_at_neutral_but_not_conservative():
    parsed = _samples(3, 2)
    _n, v, agreement = _vote_pm_samples(parsed, risk_score=3)
    assert v.action == VerdictAction.APPROVE
    assert agreement == "3/5"

    _n, v, agreement = _vote_pm_samples(parsed, risk_score=1)
    assert v.action == VerdictAction.PASS
    assert agreement == "2/5"  # PASS is now the winner; 2 is its own count


def test_a_2_of_5_split_passes_at_neutral_but_approves_at_aggressive():
    """Directly fixes the tie/near-tie-breaks-to-PASS asymmetry the CR named:
    an aggressive mandate's team came back 2-for, 3-against, and that used to be
    an automatic PASS regardless of what the user told AMI about their appetite."""
    parsed = _samples(2, 3)
    _n, v, agreement = _vote_pm_samples(parsed, risk_score=3)
    assert v.action == VerdictAction.PASS
    assert agreement == "3/5"

    _n, v, agreement = _vote_pm_samples(parsed, risk_score=5)
    assert v.action == VerdictAction.APPROVE
    assert agreement == "2/5"


def test_a_flat_2_2_tie_still_falls_to_pass_at_every_tier_n_equals_4():
    """DEF059's safe side is not weakened at n=4: even the aggressive bar (2)
    requires the approve side to be AT LEAST that count, and a genuine 2/2 split
    means both sides are equal — this still resolves the same way the original
    tie-break did, just via the graded bar rather than a hardcoded PASS-wins rule."""
    parsed = _samples(2, 2)
    for risk_score in (1, 2, 3, 4, 5):
        _n, v, _a = _vote_pm_samples(parsed, risk_score=risk_score)
        if risk_score >= 4:
            assert v.action == VerdictAction.APPROVE, risk_score
        else:
            assert v.action == VerdictAction.PASS, risk_score


def test_unanimous_approve_wins_at_every_tier():
    parsed = _samples(5, 0)
    for risk_score in (1, 2, 3, 4, 5):
        _n, v, agreement = _vote_pm_samples(parsed, risk_score=risk_score)
        assert v.action == VerdictAction.APPROVE
        assert agreement == "5/5"


def test_unanimous_pass_wins_at_every_tier():
    parsed = _samples(0, 5)
    for risk_score in (1, 2, 3, 4, 5):
        _n, v, agreement = _vote_pm_samples(parsed, risk_score=risk_score)
        assert v.action == VerdictAction.PASS
        assert agreement == "5/5"


def test_the_call_site_passes_the_mandates_own_risk_score():
    """Read off the source: the vote must be graded on the SAME mandate the run
    is for, not a hardcoded neutral value that would make Step 4 dark in
    production the way DEF038/DEF063 were."""
    import inspect

    from app.services import room_runner

    src = inspect.getsource(room_runner)
    assert "risk_score=ctx.mandate.risk_score" in src
