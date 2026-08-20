"""CR197 — mechanical aggregation over N independent CIO samples.

The ablation's baseline arms measured something nobody set out to look for. Replaying
136 committed convenes three times each on BYTE-IDENTICAL prompts, 26 of 132 (19.7%)
came back non-unanimous, and a single draw disagrees with the 3-vote majority 6.6% of
the time. The approval RATE held steady across samples (22 / 21 / 25 of ~135) while
WHICH ticker got approved did not — so roughly one verdict in five is decided by the
sampler, and the user reads the same confident prose either way.

That is a larger and better-established defect than anything the risk debate fixes,
and `docs/Research/benchmark/kimi/04_academic_forecasts.md` names the remedy: the
reliable ordering puts "best structured aggregation of independent forecasts" first
and "deliberating unstructured group" last, conditional on the aggregation being
"mechanical rather than consensus-seeking".

These tests pin the mechanics and, just as importantly, the two safety properties:
ties fall to PASS (DEF059 — an uncertain path must never mint a confident buy), and
the default of 1 sample leaves today's single-call behaviour byte-identical.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.schemas.room import Verdict, VerdictAction
from app.services.room_runner import _vote_pm_samples


def _v(action: VerdictAction, size: float | None = None, reason: str = "r") -> Verdict:
    return Verdict(action=action, size_pct=size, reason=reason)


def _sample(action, size=None, narration="n"):
    return (narration, _v(action, size))


# ── the vote ─────────────────────────────────────────────────────────────────


def test_unanimous_samples_return_that_action():
    parsed = [_sample(VerdictAction.APPROVE, s) for s in (3.0, 3.0, 3.0)]
    _n, v, agreement = _vote_pm_samples(parsed)
    assert v.action == VerdictAction.APPROVE
    assert agreement == "3/3"


def test_majority_wins_over_a_dissenter():
    parsed = [
        _sample(VerdictAction.APPROVE, 3.0),
        _sample(VerdictAction.APPROVE, 2.0),
        _sample(VerdictAction.PASS),
    ]
    _n, v, agreement = _vote_pm_samples(parsed)
    assert v.action == VerdictAction.APPROVE
    assert agreement == "2/3"


def test_a_lone_approve_loses_to_two_passes():
    """The 19.7% case, in the direction that matters: one bullish draw must not
    carry a verdict the other two independent reads declined."""
    parsed = [
        _sample(VerdictAction.APPROVE, 5.0),
        _sample(VerdictAction.PASS),
        _sample(VerdictAction.PASS),
    ]
    _n, v, agreement = _vote_pm_samples(parsed)
    assert v.action == VerdictAction.PASS
    assert agreement == "2/3"


def test_the_chosen_narration_belongs_to_the_chosen_numbers():
    """The user must not read one sample's reasoning attached to another's size —
    that would be a verdict nobody actually wrote."""
    parsed = [
        ("cheap-at-1.5", _v(VerdictAction.APPROVE, 1.5)),
        ("fair-at-3.0", _v(VerdictAction.APPROVE, 3.0)),
        ("rich-at-5.0", _v(VerdictAction.APPROVE, 5.0)),
    ]
    narration, v, _a = _vote_pm_samples(parsed)
    assert (narration, v.size_pct) == ("fair-at-3.0", 3.0)


def test_the_winning_size_is_the_median_not_the_mean():
    """A mean would invent a size no sample proposed, and the simulator would then
    act on a number no reasoning supports."""
    parsed = [
        _sample(VerdictAction.APPROVE, 1.5),
        _sample(VerdictAction.APPROVE, 2.0),
        _sample(VerdictAction.APPROVE, 5.0),
    ]
    _n, v, _a = _vote_pm_samples(parsed)
    assert v.size_pct == 2.0


def test_losing_samples_do_not_contribute_their_size():
    parsed = [
        _sample(VerdictAction.PASS),
        _sample(VerdictAction.APPROVE, 3.0),
        _sample(VerdictAction.APPROVE, 3.5),
    ]
    _n, v, _a = _vote_pm_samples(parsed)
    assert v.action == VerdictAction.APPROVE
    assert v.size_pct in (3.0, 3.5)


# ── safety ───────────────────────────────────────────────────────────────────


def test_a_tie_falls_to_pass():
    """DEF059's rule generalised: where the samples do not settle it, the safe side
    wins. An even split is exactly the case where confidence is unearned."""
    parsed = [_sample(VerdictAction.APPROVE, 3.0), _sample(VerdictAction.PASS)]
    _n, v, agreement = _vote_pm_samples(parsed)
    assert v.action == VerdictAction.PASS
    assert agreement == "1/2"


def test_a_single_sample_is_returned_unchanged():
    parsed = [("only", _v(VerdictAction.APPROVE, 4.0))]
    narration, v, agreement = _vote_pm_samples(parsed)
    assert (narration, v.size_pct, agreement) == ("only", 4.0, "1/1")


def test_agreement_is_reported_as_a_fraction_of_all_samples():
    parsed = [
        _sample(VerdictAction.PASS),
        _sample(VerdictAction.PASS),
        _sample(VerdictAction.PASS),
        _sample(VerdictAction.APPROVE, 2.0),
    ]
    _n, _v_, agreement = _vote_pm_samples(parsed)
    assert agreement == "3/4"


# ── the default must not change today's behaviour ────────────────────────────


def test_the_default_is_one_sample():
    """Anything above 1 multiplies the most expensive call in the run, so the knob
    ships off. Raising it is an operator decision, not a silent upgrade."""
    assert Settings().pm_self_consistency_samples == 1


def test_the_setting_is_bounded():
    with pytest.raises(Exception):
        Settings(pm_self_consistency_samples=0)
    with pytest.raises(Exception):
        Settings(pm_self_consistency_samples=99)


def test_the_runner_only_votes_above_one_sample():
    """The guard is an inequality in `_run_impl`; if it ever became `>= 1` every run
    would silently triple its verdict cost."""
    import inspect

    from app.services import room_runner

    src = inspect.getsource(room_runner)
    assert "_pm_samples > 1" in src


def test_a_split_verdict_says_so_in_the_reason():
    """CR040 — a split team is a real finding about how marginal the call is. Hiding
    it behind confident prose is the failure this CR exists to name."""
    import inspect

    from app.services import room_runner

    src = inspect.getsource(room_runner)
    assert "Your team was split on" in src
