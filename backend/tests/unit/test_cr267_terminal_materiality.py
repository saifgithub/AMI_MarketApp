"""CR267 — the deterministic materiality check on a `debt_default` terminal yes (`terminal_materiality.py`).

Pure code, no network, no model. Numbers are $M.

1. Covered / uncovered / no schedule, with the reason text and the recorded inputs.
2. Cash: gross cash, else total debt less net debt, else unknown (zero, recorded).
3. FCF: positive adds, negative reduces, absent counts as zero (recorded).
4. Horizon bucket mapping and its edges.
5. Other categories, a "no", and an unknown horizon pass through; the closeness flag is cleared on a refusal.
6. Wired into the grader: version tag, DeepInfra and the v1 Ling path unchanged, the field on the record.
"""

from __future__ import annotations

import json

import pytest

from app.services import room_decision_rule as rule
from app.services.room_grader_contract import (
    Answer, QuestionAnswer, QuestionId, RoomTranscript, build_terminal_inputs,
)
from app.services.room_graders import deepinfra, ling
from app.services.room_graders import terminal_materiality as M
from app.services.room_runner import _coded_record
from tests.unit import test_cr267_ling_terminal_v2 as v2_test
from tests.unit import test_cr267_wp23_ling_grader as ling_test

Q = QuestionId.TERMINAL_VULNERABILITY
BA = {  # Boeing, from the WP-20 Room: $8,351M due within a year, $20,671M gross cash, FCF -$386M
    "horizon_days": 42, "ladder": [["Within 1 year", 8351.0], ["Year 2", 4000.0]],
    "total_cash": 20671.0, "fcf_ttm": -386.0,
}


def _yes(category="debt_default", close=False):
    return QuestionAnswer(
        Q, Answer.YES, close=close, rationale="3/5 phrasings yes",
        detail={"terminal_name": "n", "terminal_category": category, "terminal_evidence": "e",
                "terminal_open_because": "o", "terminal_rejected": None},
    )


def _check(**kw):
    return M.debt_default_check({**BA, **kw})


# 1. the decision


def test_covered_yes_becomes_no_with_the_reason_and_numbers():
    out = M.apply_materiality(_yes(), BA)
    assert out.answer is Answer.NO
    assert out.detail["terminal_rejected"] == (
        "debt_default covered: $8,351M due within the 42-day horizon; cash and cash flow cover "
        "2.47×, the minimum is 1.00× (cash $20,671M, available $20,627M)"
    )
    c = out.detail["terminal_check"]
    assert c["stands"] is False and c["due_in_horizon"] == 8351.0
    assert c["cash"] == 20671.0 and c["cash_source"] == "total_cash"
    assert c["available"] == pytest.approx(20671.0 - 386.0 * 42 / 365)
    assert c["coverage"] == pytest.approx(c["available"] / 8351.0)
    assert c["buckets_counted"] == ["Within 1 year"] and c["buckets_not_counted"] == ["Year 2"]
    assert out.detail["terminal_category"] == "debt_default"  # Ling's fields stay visible


def test_uncovered_yes_stands_and_records_the_numbers():
    out = M.apply_materiality(_yes(), {**BA, "total_cash": 2000.0})
    assert out.answer is Answer.YES
    c = out.detail["terminal_check"]
    assert c["stands"] is True and c["coverage"] == pytest.approx((2000 - 386 * 42 / 365) / 8351)
    assert "cover 0.23×, the minimum is 1.00×" in c["reason"]
    assert out.detail["terminal_rejected"] is None


def test_coverage_exactly_at_the_minimum_is_covered():
    out = M.apply_materiality(_yes(), {
        "horizon_days": 365, "ladder": [["Within 1 year", 100.0]], "total_cash": 50.0, "fcf_ttm": 50.0,
    })
    assert out.answer is Answer.NO and out.detail["terminal_check"]["coverage"] == 1.0


@pytest.mark.parametrize("inputs", [None, {}, {"horizon_days": 42, "ladder": None},
                                    {"horizon_days": 42, "ladder": []}])
def test_no_schedule_refuses_the_yes_and_says_so(inputs):
    out = M.apply_materiality(_yes(), inputs)
    assert out.answer is Answer.NO
    assert out.detail["terminal_rejected"] == (
        "debt_default not evidenced: no debt-maturity schedule on the sheet"
    )
    c = out.detail["terminal_check"]
    assert c["stands"] is False and c["due_in_horizon"] is None and c["coverage"] is None


def test_nothing_due_in_the_horizon_is_covered_without_a_ratio():
    out = M.apply_materiality(_yes(), {
        "horizon_days": 42, "ladder": [["Within 1 year", 0.0], ["Year 2", 1133.0]],
        "total_cash": 10.0, "fcf_ttm": 99.0,
    })
    assert out.answer is Answer.NO
    assert out.detail["terminal_check"]["coverage"] is None
    assert "no principal falls due within the 42-day horizon" in out.detail["terminal_rejected"]


# 2. cash


def test_cash_falls_back_to_total_debt_less_net_debt():
    c = _check(total_cash=None, total_debt=30000.0, net_cash=-9329.0)
    assert c["cash"] == 20671.0 and c["cash_source"] == "total_debt_less_net_debt"
    assert c["stands"] is False


def test_gross_cash_wins_over_the_derivation():
    c = _check(total_cash=5000.0, total_debt=30000.0, net_cash=-9329.0)
    assert c["cash"] == 5000.0 and c["cash_source"] == "total_cash"


def test_unknown_cash_is_zero_and_recorded():
    c = _check(total_cash=None, total_debt=30000.0, net_cash=None)
    assert c["cash"] == 0.0 and c["cash_source"] == "unknown"
    assert c["stands"] is True  # FCF is negative and there is no cash


# 3. free cash flow


def test_positive_fcf_adds_the_horizon_share():
    c = _check(total_cash=7000.0, fcf_ttm=3650.0, horizon_days=100)
    assert c["available"] == pytest.approx(7000 + 1000) and c["stands"] is True
    assert c["coverage"] == pytest.approx(8000 / 8351)  # 0.958 < 1, so the yes stands
    assert _check(total_cash=7400.0, fcf_ttm=3650.0, horizon_days=100)["stands"] is False


def test_negative_fcf_reduces_what_is_available_and_can_flip_the_answer():
    assert _check(total_cash=8400.0, fcf_ttm=0.0)["stands"] is False
    c = _check(total_cash=8400.0, fcf_ttm=-3650.0, horizon_days=100)
    assert c["available"] == pytest.approx(8400 - 1000) and c["stands"] is True


def test_absent_fcf_counts_as_zero_and_is_recorded():
    c = _check(fcf_ttm=None)
    assert c["available"] == 20671.0 and c["fcf_source"] == "unknown" and c["fcf_ttm"] is None


# 4. the horizon mapping


@pytest.mark.parametrize("label, day", [
    ("Within 1 year", 0), ("Year 2", 365), ("Year 3", 730), ("Year 5", 1460), ("year 4", 1095),
    ("Next twelve months", 0), ("Beyond", None), ("Year 0", None),
])
def test_bucket_start_days(label, day):
    assert M.bucket_start_day(label) == day


LADDER = [["Within 1 year", 10.0], ["Year 2", 20.0], ["Year 3", 40.0], ["Year 4", 80.0], ["Year 5", 160.0]]


@pytest.mark.parametrize("horizon, due", [
    (1, 10.0), (42, 10.0), (365, 10.0),        # Year 2 starts at day 365, which is the horizon's end
    (366, 30.0), (730, 30.0), (731, 70.0),
    (1460, 150.0), (1461, 310.0),
])
def test_horizon_bucket_edges(horizon, due):
    c = M.debt_default_check({"horizon_days": horizon, "ladder": LADDER, "total_cash": 0.0})
    assert c["due_in_horizon"] == due


def test_a_short_ladder_counts_what_it_discloses_and_an_unknown_label_counts_as_due():
    c = M.debt_default_check({
        "horizon_days": 42, "ladder": [["Within 1 year", 5.0], ["Mystery", 7.0]], "total_cash": 0.0,
    })
    assert c["due_in_horizon"] == 12.0 and c["unmapped_labels"] == ["Mystery"]


# 5. pass-through


@pytest.mark.parametrize("category", ["dilutive_restructuring", "going_concern_audit", "fraud_regulatory"])
def test_other_categories_are_untouched(category):
    ans = _yes(category)
    assert M.apply_materiality(ans, None) is ans


def test_a_no_answer_is_untouched():
    ans = QuestionAnswer(Q, Answer.NO, detail={"terminal_category": None})
    assert M.apply_materiality(ans, None) is ans


def test_unknown_horizon_leaves_the_yes_standing_and_says_why():
    out = M.apply_materiality(_yes(), {**BA, "horizon_days": None})
    assert out.answer is Answer.YES
    c = out.detail["terminal_check"]
    assert c["stands"] is True and c["skipped"] is True and "horizon is unknown" in c["reason"]


def test_a_refused_close_yes_is_no_longer_close_and_keeps_earlier_refusals():
    ans = _yes(close=True)
    ans = QuestionAnswer(Q, Answer.YES, close=True, detail={
        **ans.detail, "terminal_rejected": "1 of 5 yes votes refused: evidence_not_grounded x1"})
    out = M.apply_materiality(ans, BA)
    assert out.answer is Answer.NO and out.close is False
    assert out.detail["terminal_rejected"].endswith("; 1 of 5 yes votes refused: evidence_not_grounded x1")


# the profile -> inputs bridge


def test_inputs_are_taken_from_live_profile_fields_only():
    profile = {
        "field_state": {"debt_maturity": "live", "total_cash": "live", "total_debt": "unavailable",
                        "net_cash": "live", "free_cash_flow": "unavailable",
                        "free_cash_flow_ttm": "live"},
        "debt_maturity_labels": ["Within 1 year", "Year 2"], "debt_maturity_values": [8351, 1133],
        "debt_maturity_period_end": "2026-09-30", "debt_maturity_excluded_st": 0,
        "total_cash": 20671, "total_debt": 99999, "net_cash": -9329,
        "free_cash_flow": 1, "free_cash_flow_ttm": -386,
    }
    got = build_terminal_inputs(profile, 42)
    assert got["ladder"] == [["Within 1 year", 8351.0], ["Year 2", 1133.0]]
    assert got["total_cash"] == 20671 and got["total_debt"] is None and got["net_cash"] == -9329
    assert got["fcf_ttm"] == -386 and got["fcf_field"] == "free_cash_flow_ttm"
    assert got["horizon_days"] == 42


@pytest.mark.parametrize("profile", [None, {}, {"field_state": {"debt_maturity": "unavailable"},
                                                "debt_maturity_labels": ["Within 1 year"],
                                                "debt_maturity_values": [5]}])
def test_a_dark_schedule_gives_no_ladder(profile):
    assert build_terminal_inputs(profile, 42)["ladder"] is None


# 6. wiring


def test_the_tag_carries_the_check_revision_and_only_rides_term_v2():
    assert M.CHECK_TAG == "termchk=d2"
    base = ling.grader_version(ling_test.MODEL)
    assert "termchk" not in base
    assert ling.grader_version(ling_test.MODEL, terminal_variant=True) == (
        base + "|term=v2|termchk=d2"
    )
    assert "termchk" not in deepinfra.grader_version("m")


def test_the_v1_ling_path_never_sees_the_check():
    wire = ling_test.Wire()
    g = ling_test.make_grader(wire)
    res = g.grade(ling_test.transcript())
    assert res.error is None and "terminal_materiality" not in res.extra
    assert (res.get(Q).detail or {}).get("terminal_check") is None
    assert "termchk" not in g.version


def test_a_covered_yes_is_refused_end_to_end_and_counted_in_the_result():
    _, res, _ = v2_test._grade(v2_test.GOOD, inputs={**BA, "ladder": [["Within 1 year", 10.0]]})
    ans = res.get(Q)
    assert ans.answer is Answer.NO and not ans.close
    assert ans.detail["terminal_check"]["stands"] is False
    assert res.extra["terminal_materiality"]["stood"] is False
    assert "covered" in res.extra["terminal_materiality"]["reason"]


def test_no_schedule_refuses_end_to_end_and_the_record_carries_the_check():
    _, res, _ = v2_test._grade(v2_test.GOOD, inputs=None)
    rec = _coded_record(res, rule.decide(res, 5))
    term = next(a for a in rec.answers if a.question == "terminal_vulnerability")
    assert term.answer == "no"
    assert term.terminal_rejected == "debt_default not evidenced: no debt-maturity schedule on the sheet"
    assert term.terminal_check["stands"] is False
    json.dumps(term.model_dump())


def test_an_uncovered_yes_stands_end_to_end():
    _, res, _ = v2_test._grade(v2_test.GOOD)
    assert res.get(Q).answer is Answer.YES
    assert res.extra["terminal_materiality"]["stood"] is True


def test_a_transcript_without_inputs_is_allowed():
    assert RoomTranscript(room_id="r", ticker="A", risk_score=3, horizon=None, turns=[]
                          ).terminal_inputs is None
