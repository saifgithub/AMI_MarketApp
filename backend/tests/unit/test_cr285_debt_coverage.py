"""CR285 — debt-maturity coverage as a mandate setting.

Covers the acceptance list: defaults per mandate horizon and per risk score, a user override with its
`source`, the desk's horizon winning when longer, the ranges, the Room bank key following either
value (only under terminal v2), the readback line, the verdict wording that names the user's own
numbers, and BGS / BA through the check at the benchmark mandate.
"""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.mandate import Horizon
from app.services import room_bank
from app.services import room_decision_rule as rule
from app.services.coach_engine import hydrate_coach_mandate
from app.services.mandate_store import MandateStore
from app.services.room_graders import ling
from app.services.room_graders import terminal_materiality as M
from app.services.room_runner import _with_terminal_check_reasons
from app.trading_math.risk_limits import (
    DEFAULT_DEBT_HORIZON_MONTHS,
    DEFAULT_MIN_DEBT_COVERAGE,
    debt_horizon_days,
    debt_horizon_months_source,
    min_debt_coverage_source,
    resolved_debt_horizon_months,
    resolved_min_debt_coverage,
)
from app.services.room_grader_contract import Answer, QuestionAnswer, QuestionId
from tests.unit import test_cr267_ling_terminal_v2 as v2_test
from tests.unit import test_cr267_wp23_ling_grader as ling_test

Q = QuestionId.TERMINAL_VULNERABILITY

# BGS, the one labelled terminal case: $4M due in year 1, $1,133M in year 2, ~$99M a year of free cash flow.
BGS = {
    "ladder": [["Within 1 year", 4.0], ["Year 2", 1133.0]],
    "total_cash": 31.0, "fcf_ttm": 99.0,
}
# Boeing: $8,351M due within a year against $20.7bn of cash and negative cash flow.
BA = {
    "ladder": [["Within 1 year", 8351.0], ["Year 2", 4000.0]],
    "total_cash": 20671.0, "fcf_ttm": -386.0,
}


def _yes(category="debt_default"):
    return QuestionAnswer(
        Q, Answer.YES, rationale="3/5 phrasings yes",
        detail={"terminal_name": "n", "terminal_category": category, "terminal_evidence": "e",
                "terminal_open_because": "o", "terminal_rejected": None},
    )


def _inputs(base, *, desk=None, months=24, minimum=1.0, **kw):
    return {
        **base, "horizon_days": desk, "horizon_source": "desk" if desk else "default",
        "mandate_horizon_months": months, "mandate_horizon_source": "default",
        "min_coverage": minimum, "min_coverage_source": "default", **kw,
    }


def _mandate(risk=3, horizon="long", **kw):
    return hydrate_coach_mandate(
        {"plan": "trader", "risk_score": risk, "horizon": horizon, "single_name_cap_pct": 100.0, **kw}
    )


# 1. defaults and overrides


@pytest.mark.parametrize("horizon,months", [("short", 6), ("medium", 12), ("long", 24), ("very_long", 24)])
def test_the_horizon_default_follows_the_mandate_horizon(horizon, months):
    assert resolved_debt_horizon_months(horizon) == months
    assert resolved_debt_horizon_months(Horizon(horizon)) == months
    assert debt_horizon_months_source(None) == "default"


@pytest.mark.parametrize("risk,cover", [(1, 1.5), (2, 1.5), (3, 1.25), (4, 1.25), (5, 1.0)])
def test_the_coverage_default_follows_the_risk_score(risk, cover):
    assert resolved_min_debt_coverage(risk) == cover
    assert min_debt_coverage_source(None) == "default"


def test_a_user_value_wins_and_says_so():
    assert resolved_debt_horizon_months("short", 36) == 36
    assert resolved_min_debt_coverage(5, 2.0) == 2.0
    assert debt_horizon_months_source(36) == "user" and min_debt_coverage_source(2.0) == "user"


def test_an_unknown_horizon_falls_to_the_longest_default_never_a_shorter_one():
    assert resolved_debt_horizon_months("decades") == max(DEFAULT_DEBT_HORIZON_MONTHS.values())


def test_months_map_onto_the_ladder_year():
    assert debt_horizon_days(12) == 365 and debt_horizon_days(24) == 730 and debt_horizon_days(6) == 182


def test_the_tables_are_the_specs():
    assert DEFAULT_DEBT_HORIZON_MONTHS == {"short": 6, "medium": 12, "long": 24, "very_long": 24}
    assert DEFAULT_MIN_DEBT_COVERAGE == {1: 1.5, 2: 1.5, 3: 1.25, 4: 1.25, 5: 1.0}


# 2. ranges


@pytest.mark.parametrize("field,bad", [
    ("debt_horizon_months", 2), ("debt_horizon_months", 61), ("debt_horizon_months", 0),
    ("min_debt_coverage", 0.4), ("min_debt_coverage", 3.1), ("min_debt_coverage", 0),
])
def test_the_ranges_are_enforced_so_the_check_cannot_be_switched_off(field, bad):
    with pytest.raises(ValidationError):
        _mandate(**{field: bad})
    with pytest.raises(Exception):
        MandateStore().patch(uuid4(), {field: bad})


@pytest.mark.parametrize("field,edge", [
    ("debt_horizon_months", 3), ("debt_horizon_months", 60),
    ("min_debt_coverage", 0.5), ("min_debt_coverage", 3.0),
])
def test_the_range_edges_are_allowed(field, edge):
    assert getattr(_mandate(**{field: edge}), field) == edge


def test_the_store_round_trips_and_unsets():
    store, uid = MandateStore(), uuid4()
    m = store.patch(uid, {"debt_horizon_months": 36, "min_debt_coverage": 2.0})
    assert (m.debt_horizon_months, m.min_debt_coverage) == (36, 2.0)
    m = store.patch(uid, {"debt_horizon_months": None, "min_debt_coverage": None})
    assert (m.debt_horizon_months, m.min_debt_coverage) == (None, None)


def test_the_mandate_read_says_where_each_number_came_from():
    from app.api.mandate import _with_plan_state
    from app.db import get_session
    from app.db.models import User
    from app.services.auth_service import AuthService

    user, _, _ = AuthService().ensure_anonymous(device_user_id=None)
    with get_session() as s:
        row = s.get(User, user.id)
        d = _with_plan_state(_mandate(5, "long"), row).resolved
        u = _with_plan_state(_mandate(5, "long", debt_horizon_months=36, min_debt_coverage=2.0), row).resolved
        short = _with_plan_state(_mandate(1, "short"), row).resolved
    assert (d.debt_horizon_months, d.debt_horizon_months_source) == (24, "default")
    assert (d.min_debt_coverage, d.min_debt_coverage_source) == (1.0, "default")
    assert (u.debt_horizon_months, u.debt_horizon_months_source) == (36, "user")
    assert (u.min_debt_coverage, u.min_debt_coverage_source) == (2.0, "user")
    assert (short.debt_horizon_months, short.min_debt_coverage) == (6, 1.5)
    assert d.debt_check_active is (settings.room_grader_ling_terminal == "v2")


def test_the_mandate_read_reports_the_check_active_only_under_terminal_v2(monkeypatch):
    from app.api.mandate import _with_plan_state
    from app.db import get_session
    from app.db.models import User
    from app.services.auth_service import AuthService

    user, _, _ = AuthService().ensure_anonymous(device_user_id=None)
    for value, expect in (("v1", False), ("v2", True)):
        monkeypatch.setattr(settings, "room_grader_ling_terminal", value)
        with get_session() as s:
            assert _with_plan_state(_mandate(), s.get(User, user.id)).resolved.debt_check_active is expect


# 3. the check


def test_the_benchmark_mandate_catches_bgs_that_six_weeks_missed():
    old = M.debt_default_check({**BGS, "horizon_days": 42})
    assert old["stands"] is False and old["due_in_horizon"] == 4.0
    new = M.debt_default_check(_inputs(BGS, desk=42, months=24, minimum=1.0))
    assert new["stands"] is True and new["due_in_horizon"] == 1137.0
    assert new["horizon_days"] == 730 and new["horizon_basis"] == "mandate"


def test_ba_is_refused_at_the_benchmark_mandate():
    out = M.apply_materiality(_yes(), _inputs(BA, desk=42, months=24, minimum=1.0))
    assert out.answer is Answer.NO
    assert out.detail["terminal_check"]["buckets_counted"] == ["Within 1 year", "Year 2"]


def test_the_larger_of_the_mandate_and_the_desk_horizon_governs():
    ladder = {"ladder": [["Within 1 year", 1.0], ["Year 2", 1.0], ["Year 3", 500.0]],
              "total_cash": 10.0, "fcf_ttm": 0.0}
    mandate_wins = M.debt_default_check(_inputs(ladder, desk=200, months=12))
    assert mandate_wins["horizon_basis"] == "mandate" and mandate_wins["horizon_days"] == 365
    assert mandate_wins["due_in_horizon"] == 1.0
    desk_wins = M.debt_default_check(_inputs(ladder, desk=900, months=12))
    assert desk_wins["horizon_basis"] == "desk" and desk_wins["horizon_days"] == 900
    assert desk_wins["due_in_horizon"] == 502.0 and desk_wins["stands"] is True
    assert "the desk's 900-day horizon (longer than your 12-month setting)" in desk_wins["reason"]


def test_an_unread_desk_horizon_leaves_the_mandates():
    c = M.debt_default_check(_inputs(BGS, desk=None, months=24))
    assert c["horizon_basis"] == "mandate" and c["desk_horizon_days"] is None
    assert c["desk_horizon_source"] == "default"


def test_the_users_minimum_decides_and_exactly_at_it_is_covered():
    base = {"ladder": [["Within 1 year", 100.0]], "total_cash": 150.0, "fcf_ttm": 0.0}
    for minimum, stands in ((1.0, False), (1.5, False), (1.51, True), (3.0, True)):
        c = M.debt_default_check(_inputs(base, desk=42, months=12, minimum=minimum))
        assert c["stands"] is stands and c["coverage"] == 1.5 and c["min_coverage"] == minimum


def test_the_reason_names_your_horizon_and_your_minimum():
    c = M.debt_default_check(_inputs(
        {"ladder": [["Within 1 year", 4.0], ["Year 2", 1129.0]], "total_cash": 31.0, "fcf_ttm": 0.0},
        desk=42, months=24, minimum=1.5,
    ))
    assert c["reason"].startswith(
        "debt_default stands: $1,133M due within your 24-month horizon; cash and cash flow cover "
        "0.03×, your minimum is 1.50×"
    )
    covered = M.debt_default_check(_inputs(BA, desk=42, months=12, minimum=1.0))
    assert "debt_default covered: $8,351M due within your 12-month horizon" in covered["reason"]
    assert "your minimum is 1.00×" in covered["reason"]


def test_a_coverage_that_prints_like_the_minimum_but_is_below_it_shows_more_digits():
    base = {"ladder": [["Within 1 year", 10000.0]], "total_cash": 9990.0, "fcf_ttm": 0.0}
    c = M.debt_default_check(_inputs(base, desk=42, months=12, minimum=1.0))
    assert c["stands"] is True and c["coverage"] == pytest.approx(0.999)
    assert "cover 0.9990×, your minimum is 1.00×" in c["reason"]


def test_the_record_carries_every_number_and_its_source():
    c = M.debt_default_check(_inputs(BGS, desk=100, months=24, minimum=1.25))
    assert c["mandate_horizon_months"] == 24 and c["mandate_horizon_days"] == 730
    assert c["mandate_horizon_source"] == "default" and c["min_coverage_source"] == "default"
    assert (c["desk_horizon_days"], c["desk_horizon_source"]) == (100, "desk")
    assert c["min_coverage"] == 1.25


def test_no_numbers_from_the_mandate_reads_as_the_old_check_and_says_so():
    c = M.debt_default_check({**BA, "horizon_days": 42})
    assert c["min_coverage"] == 1.0 and c["min_coverage_source"] == "check_default"
    assert c["mandate_horizon_months"] is None and c["horizon_days"] == 42


def test_no_horizon_at_all_stands_as_skipped_and_says_so():
    c = M.debt_default_check({**BA, "horizon_days": None, "mandate_horizon_months": None})
    assert c["stands"] is True and c.get("skipped") is True


# 4. the verdict wording


def _graded(inputs):
    _, res, _ = v2_test._grade(v2_test.GOOD, inputs=inputs)
    return res


def test_the_verdict_reasons_carry_the_numbers_when_the_yes_stands():
    res = _graded(_inputs(
        {"ladder": [["Within 1 year", 4.0], ["Year 2", 1129.0]], "total_cash": 31.0, "fcf_ttm": 0.0},
        desk=42, months=24, minimum=1.5,
    ))
    decision = _with_terminal_check_reasons(rule.decide(res, 5), res)
    assert decision.outcome == rule.Outcome.PASS
    assert any(
        "$1,133M due within your 24-month horizon; cash and cash flow cover 0.03×, your minimum is 1.50×" in r
        for r in decision.reasons
    )
    assert decision.reasons[0] == "whether an unresolved terminal vulnerability remains: yes"


def test_the_verdict_reasons_carry_the_numbers_when_the_yes_is_refused():
    res = _graded(_inputs(BA, desk=42, months=24, minimum=1.0))
    decision = _with_terminal_check_reasons(rule.decide(res, 5), res)
    assert any("debt_default covered: $12,351M due within your 24-month horizon" in r for r in decision.reasons)


def test_a_room_with_no_terminal_check_is_left_alone():
    _, res, _ = v2_test._grade(
        {**v2_test.GOOD, "answer": "no", "terminal_name": "", "terminal_category": "",
         "terminal_evidence": "", "terminal_open_because": ""},
    )
    decision = rule.decide(res, 5)
    assert _with_terminal_check_reasons(decision, res) is decision


def test_an_unavailable_decision_is_never_decorated():
    res = _graded(_inputs(BGS, desk=42))
    unavailable = replace(rule.decide(res, 5), outcome=rule.Outcome.UNAVAILABLE)
    assert _with_terminal_check_reasons(unavailable, res) is unavailable


# 5. the bank key and the version tag


def test_the_bank_key_follows_either_value_under_terminal_v2(monkeypatch):
    monkeypatch.setattr(settings, "room_grader_ling_terminal", "v2")
    m = _mandate(3, "long")
    base = room_bank.mandate_digest(m)
    assert base != room_bank.mandate_digest(m.model_copy(update={"debt_horizon_months": 36}))
    assert base != room_bank.mandate_digest(m.model_copy(update={"min_debt_coverage": 2.0}))
    # an unset value follows the horizon and risk score, so those re-key it too
    assert base != room_bank.mandate_digest(m.model_copy(update={"horizon": Horizon.SHORT}))
    assert base != room_bank.mandate_digest(m.model_copy(update={"risk_score": 5}))
    # an explicit value equal to the default is the same Room (same numbers)
    assert room_bank.mandate_digest(m.model_copy(update={"debt_horizon_months": 24, "min_debt_coverage": 1.25})) == (
        room_bank.mandate_digest(m.model_copy(update={"debt_horizon_months": None, "min_debt_coverage": None}))
    )


def test_the_bank_key_is_unchanged_under_v1(monkeypatch):
    """Nothing re-keys on Alpha until ROOM_GRADER_LING_TERMINAL=v2: under v1 the two fields are
    not part of the key at all."""
    monkeypatch.setattr(settings, "room_grader_ling_terminal", "v1")
    m = _mandate(3, "long")
    base = room_bank.mandate_digest(m)
    for update in ({"debt_horizon_months": 36}, {"min_debt_coverage": 2.0}):
        assert room_bank.mandate_digest(m.model_copy(update=update)) == base


def test_the_check_revision_changes_the_grader_version_so_older_rooms_key_apart():
    v = ling.grader_version(ling_test.MODEL, terminal_variant=True)
    assert v.endswith("|term=v2|termchk=d2") and "d1c1.00" not in v
    assert "termchk" not in ling.grader_version(ling_test.MODEL)


# 6. the readback


@pytest.mark.parametrize("horizon,risk,months,cover", [
    ("short", 1, 6, "1.5"), ("medium", 3, 12, "1.25"), ("long", 5, 24, "1.0"),
])
def test_the_onboarding_readback_names_the_defaults_under_terminal_v2(monkeypatch, horizon, risk, months, cover):
    from app.services.concierge_engine import _readback_text

    monkeypatch.setattr(settings, "room_grader_ling_terminal", "v2")
    text = _readback_text({
        "primary_goal": "long_term_wealth", "horizon": horizon, "risk_score": risk,
        "max_drawdown_pct": 20, "compliance": {"long_only": True},
    })
    assert f"Debt cover: debt falling due within {months} months must be covered at least {cover}×" in text
    assert "change this in Settings" in text


def test_the_readback_says_nothing_of_the_check_while_it_is_off(monkeypatch):
    from app.services.concierge_engine import _readback_text

    monkeypatch.setattr(settings, "room_grader_ling_terminal", "v1")
    text = _readback_text({
        "primary_goal": "long_term_wealth", "horizon": "long", "risk_score": 3,
        "max_drawdown_pct": 20, "compliance": {"long_only": True},
    })
    assert "Debt cover" not in text


def test_the_journal_diff_names_the_two_fields_in_their_units():
    import inspect

    from app.api import mandate as api

    src = inspect.getsource(api.patch_mandate)
    assert '"debt-maturity horizon", " months"' in src and '"minimum debt coverage", "×"' in src
