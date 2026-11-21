"""CR267 WP-25 — the flip explainer.

1. Pure diff: a forced price / news / filings / mandate change names the changed
   input; coded answers on both Rooms name the changed answer; the coded rule off
   leaves `answers_available` false and the explainer still carries its inputs; an
   identical-inputs flip is recorded explicitly (`same_inputs_flip`) and an
   unstored side is `inputs_compared=False`, never "nothing changed"; card changes
   appear only when both Rooms ran with cards.
2. Stamping against stored Rooms (real rows): a flip carries an explainer, a
   non-flip carries `previous_action` and no explainer, an outage-shaped verdict
   and a first Room carry neither.
3. The write path refuses a flip stored without an explainer.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.db import get_session
from app.db.models import RoomFactSheetRow, User
from app.schemas.room import (
    CodedAnswer,
    CodedDecisionRecord,
    FlipExplainer,
    RoomRun,
    RoomStatus,
    Verdict,
    VerdictAction,
)
from app.services import flip_explainer as fx
from app.services import room_runner as rr
from app.services.auth_service import AuthService
from app.services.coach_engine import hydrate_coach_mandate
from app.services.mandate_store import get_mandate_store
from app.services.room_bank import _HASHED_PARTS

PARTS = {p: f"{p}-1" for p in _HASHED_PARTS}


def _verdict(action=VerdictAction.PASS, price=None, coded=None, cards=None) -> Verdict:
    return Verdict(
        action=action, reason="r", reference_price=price,
        coded_decision=coded, claim_summary=cards,
    )


def _coded(**answers: str) -> CodedDecisionRecord:
    return CodedDecisionRecord(
        outcome="PASS", rule_version="r1", policy_version="p1", risk_level="R3",
        answers=[CodedAnswer(question=q, answer=a) for q, a in answers.items()],
    )


def _side(verdict, *, parts=None, sheet=None, mandate=None, run_id="prev") -> fx.RoomSide:
    return fx.RoomSide(
        run_id=run_id, verdict=verdict,
        bank_inputs=dict(PARTS) if parts is None else parts, sheet=sheet, mandate=mandate,
    )


def _kinds(explainer: FlipExplainer) -> set[str]:
    return {i.kind for i in explainer.changed_inputs}


def _text(explainer: FlipExplainer) -> str:
    return " | ".join(i.summary for i in explainer.changed_inputs)


# ── 1. the pure diff ──────────────────────────────────────────────────────────


def test_forced_price_change_names_the_input_with_numbers():
    prev = _side(_verdict(VerdictAction.PASS, price=100.0))
    cur = _side(
        _verdict(VerdictAction.APPROVE, price=112.5),
        parts={**PARTS, "fact_sheet": "fact_sheet-2"}, run_id="cur",
    )
    ex = fx.explain_flip(prev, cur)
    assert ex.previous_action == "PASS" and ex.new_action == "APPROVE"
    assert "price" in _kinds(ex)
    assert "$100.00 to $112.50 (+12.5%)" in _text(ex)
    assert not ex.same_inputs_flip and ex.inputs_compared


def test_news_and_filings_changes_are_named_from_the_two_sheets():
    old = {
        "news_headlines": [{"title": "Old story"}],
        "recent_filings_items": [{"form": "10-Q", "label": "Quarterly", "filed_date": "2026-08-01"}],
    }
    new = {
        "news_headlines": [{"title": "CEO steps down"}, {"title": "Old story"}],
        "recent_filings_items": [
            {"form": "8-K", "label": "Item 5.02", "filed_date": "2026-11-20"},
            {"form": "10-Q", "label": "Quarterly", "filed_date": "2026-08-01"},
        ],
        "pe_ratio": 31.0,
    }
    ex = fx.explain_flip(
        _side(_verdict(price=10.0), sheet=old),
        _side(_verdict(VerdictAction.REJECT, price=10.0), sheet=new,
              parts={**PARTS, "fact_sheet": "fact_sheet-2"}),
    )
    assert {"news", "filings", "other"} <= _kinds(ex)
    text = _text(ex)
    assert "1 new news item" in text and "CEO steps down" in text
    assert "1 new SEC filing: 8-K filed 2026-11-20" in text
    assert "pe ratio" in text


def test_mandate_change_names_the_field_and_both_values():
    prev = _side(_verdict(), mandate={"single_name_cap_pct": 10.0, "risk_score": 3})
    cur = _side(
        _verdict(VerdictAction.REJECT),
        mandate={"single_name_cap_pct": 3.0, "risk_score": 3},
        parts={**PARTS, "mandate": "mandate-2"},
    )
    ex = fx.explain_flip(prev, cur)
    assert _kinds(ex) == {"mandate"}
    assert "single-name cap 10% → 3%" in _text(ex)


def test_other_parts_map_to_their_kinds():
    cur_parts = {
        **PARTS, "portfolio": "x", "brief": "x", "policy": "x", "model_root": "m2", "tier": "x",
    }
    ex = fx.explain_flip(
        _side(_verdict()), _side(_verdict(VerdictAction.APPROVE), parts=cur_parts),
    )
    assert _kinds(ex) == {"portfolio", "brief", "policy", "model"}


def test_coded_answers_on_both_rooms_name_the_changed_answer():
    prev = _side(_verdict(coded=_coded(bear_objection_answered="NO", catalyst_in_horizon="YES")))
    cur = _side(_verdict(
        VerdictAction.APPROVE,
        coded=_coded(bear_objection_answered="YES", catalyst_in_horizon="YES"),
    ))
    ex = fx.explain_flip(prev, cur)
    assert ex.answers_available and ex.answers_unavailable_reason is None
    assert [(a.question, a.before, a.after) for a in ex.changed_answers] == [
        ("bear_objection_answered", "NO", "YES"),
    ]


def test_flag_off_has_no_answers_and_says_so_but_keeps_its_inputs():
    prev = _side(_verdict(price=50.0))
    cur = _side(
        _verdict(VerdictAction.APPROVE, price=55.0),
        parts={**PARTS, "fact_sheet": "fact_sheet-2"},
    )
    ex = fx.explain_flip(prev, cur)
    assert ex.answers_available is False and ex.changed_answers == []
    assert "coded rule was off" in ex.answers_unavailable_reason
    assert "price" in _kinds(ex)


def test_one_sided_answers_are_unavailable_not_invented():
    ex = fx.explain_flip(
        _side(_verdict(coded=_coded(a="YES"))), _side(_verdict(VerdictAction.APPROVE)),
    )
    assert ex.answers_available is False and ex.changed_answers == []


def test_same_inputs_flip_is_recorded_explicitly():
    ex = fx.explain_flip(_side(_verdict()), _side(_verdict(VerdictAction.APPROVE)))
    assert ex.changed_inputs == []
    assert ex.inputs_compared is True and ex.same_inputs_flip is True


def test_uncompared_inputs_are_never_reported_as_same_inputs():
    ex = fx.explain_flip(
        fx.RoomSide(run_id="p", verdict=_verdict(), bank_inputs=None),
        _side(_verdict(VerdictAction.APPROVE)),
    )
    assert ex.inputs_compared is False and ex.same_inputs_flip is False


def test_cards_changes_only_when_both_rooms_ran_with_cards():
    before = {"fundamentals_analyst": {"eq": "support/well", "vc": "neutral/partial"}}
    after = {"fundamentals_analyst": {"eq": "oppose/well", "vc": "neutral/partial"}}
    both = fx.explain_flip(
        _side(_verdict(cards=before)), _side(_verdict(VerdictAction.REJECT, cards=after)),
    )
    assert [(c.desk, c.item, c.before, c.after) for c in both.cards_changes] == [
        ("fundamentals_analyst", "eq", "support/well", "oppose/well"),
    ]
    one = fx.explain_flip(_side(_verdict(cards=before)), _side(_verdict(VerdictAction.REJECT)))
    assert one.cards_changes is None
    none = fx.explain_flip(_side(_verdict()), _side(_verdict(VerdictAction.REJECT)))
    assert none.cards_changes is None


# ── 2. stamping against stored Rooms ──────────────────────────────────────────


def _user() -> UUID:
    u, _, _ = AuthService().ensure_anonymous(device_user_id=None)
    with get_session() as s:
        s.get(User, u.id).plan = "trader"
    return u.id


def _decision(_v: dict) -> bool:
    return not rr.is_outage_shaped_verdict(_v)


def _bank_prior(
    user_id: UUID, verdict: Verdict, *, parts: dict, mandate_version: int = 1,
    sheet: dict | None = None, minutes_ago: int = 60, ticker: str = "AAPL",
) -> UUID:
    now = datetime.now(timezone.utc)
    if sheet is not None:
        with get_session() as s:
            s.add(RoomFactSheetRow(
                ticker=ticker, trading_date=now.date(), variant="v",
                sheet=sheet, sheet_hash=parts["fact_sheet"],
            ))
    run = RoomRun(
        id=uuid4(), user_id=user_id, ticker=ticker, triggered_at=now,
        started_at=now - timedelta(minutes=minutes_ago),
        finished_at=now - timedelta(minutes=minutes_ago), mandate_version=mandate_version,
        model_tier="cheap", credit_cost=0, status=RoomStatus.COMPLETED,
        verdict=verdict, bank_inputs=parts,
    )
    rr._persist_run(run)
    return run.id


def _stamp(user_id, verdict, *, parts, mandate_version=1, sheet=None) -> Verdict:
    return fx.stamp_flip(
        verdict=verdict, run_id=uuid4(), user_id=user_id, ticker="AAPL",
        finished_at=datetime.now(timezone.utc), mandate_version=mandate_version,
        bank_inputs=parts, sheet=sheet, is_decision=_decision,
    )


def test_stored_prior_forced_input_change_yields_a_named_flip():
    user = _user()
    store = get_mandate_store()
    m1 = store.upsert(user, hydrate_coach_mandate({"plan": "trader", "risk_score": 3, "single_name_cap_pct": 10.0}))
    m2 = store.upsert(user, m1.model_copy(update={"single_name_cap_pct": 3.0}))
    prior_parts = {**PARTS, "fact_sheet": "sheet-A", "mandate": "mandate-A"}
    prior_id = _bank_prior(
        user, _verdict(VerdictAction.APPROVE, price=100.0), parts=prior_parts,
        mandate_version=m1.version,
        sheet={"news_headlines": [], "recent_filings_items": []},
    )
    new_parts = {**PARTS, "fact_sheet": "sheet-B", "mandate": "mandate-B"}
    out = _stamp(
        user, _verdict(VerdictAction.PASS, price=92.0), parts=new_parts,
        mandate_version=m2.version,
        sheet={"news_headlines": [{"title": "Guidance cut"}], "recent_filings_items": []},
    )
    ex = out.flip_explainer
    assert out.previous_action == "APPROVE" and ex is not None
    assert ex.previous_run_id == str(prior_id)
    assert {"price", "mandate"} <= _kinds(ex)
    assert "single-name cap 10% → 3%" in _text(ex)
    assert ex.changed_inputs and ex.changed_answers == [] and not ex.answers_available


def test_same_action_records_previous_action_and_no_explainer():
    user = _user()
    _bank_prior(user, _verdict(VerdictAction.PASS), parts=dict(PARTS))
    out = _stamp(user, _verdict(VerdictAction.PASS), parts=dict(PARTS))
    assert out.previous_action == "PASS" and out.flip_explainer is None
    fx.assert_flip_recorded(out)


def test_first_room_and_outage_shaped_verdicts_carry_nothing():
    user = _user()
    first = _stamp(user, _verdict(VerdictAction.APPROVE), parts=dict(PARTS))
    assert first.previous_action is None and first.flip_explainer is None
    _bank_prior(user, _verdict(VerdictAction.APPROVE), parts=dict(PARTS))
    outage = Verdict(
        action=VerdictAction.PASS, reason=rr.PM_DECISION_UNAVAILABLE_REASON, overridden_from_llm=True,
    )
    out = _stamp(user, outage, parts=dict(PARTS))
    assert out.previous_action is None and out.flip_explainer is None
    abstain = _stamp(user, Verdict(action=VerdictAction.NO_VERDICT, reason="x"), parts=dict(PARTS))
    assert abstain.flip_explainer is None


def test_an_outage_prior_is_not_a_previous_decision():
    user = _user()
    _bank_prior(user, _verdict(VerdictAction.APPROVE), parts=dict(PARTS), minutes_ago=120)
    _bank_prior(
        user,
        Verdict(action=VerdictAction.PASS, reason=rr.PM_DECISION_UNAVAILABLE_REASON, overridden_from_llm=True),
        parts=dict(PARTS), minutes_ago=30,
    )
    out = _stamp(user, _verdict(VerdictAction.REJECT), parts=dict(PARTS))
    assert out.previous_action == "APPROVE" and out.flip_explainer is not None
    assert out.flip_explainer.same_inputs_flip is True


def test_a_failed_comparison_still_stores_an_explainer(monkeypatch):
    user = _user()
    _bank_prior(user, _verdict(VerdictAction.APPROVE), parts=dict(PARTS))

    def boom(*_a, **_k):
        raise RuntimeError("diff broke")

    monkeypatch.setattr(fx, "explain_flip", boom)
    out = _stamp(user, _verdict(VerdictAction.REJECT), parts=dict(PARTS))
    assert out.flip_explainer is not None
    assert out.flip_explainer.inputs_compared is False
    assert out.flip_explainer.same_inputs_flip is False
    assert out.flip_explainer.changed_inputs


# ── 3. the write path refuses a flip without an explainer ─────────────────────


def _run_with(verdict: Verdict) -> RoomRun:
    now = datetime.now(timezone.utc)
    return RoomRun(
        id=uuid4(), user_id=uuid4(), ticker="AAPL", triggered_at=now,
        mandate_version=1, model_tier="cheap", credit_cost=0,
        status=RoomStatus.COMPLETED, finished_at=now, verdict=verdict,
    )


def test_a_flip_without_an_explainer_is_refused_by_the_write_path():
    flip = _verdict(VerdictAction.APPROVE).model_copy(update={"previous_action": "PASS"})
    with pytest.raises(fx.FlipWithoutExplainer):
        rr._persist_run(_run_with(flip))
    with pytest.raises(fx.FlipWithoutExplainer):
        rr._snapshot_run(_run_with(flip))


def test_a_flip_with_an_explainer_and_a_non_flip_are_stored():
    ex = FlipExplainer(previous_run_id="p", previous_action="PASS", new_action="APPROVE")
    flip = _verdict(VerdictAction.APPROVE).model_copy(
        update={"previous_action": "PASS", "flip_explainer": ex},
    )
    rr._persist_run(_run_with(flip))
    same = _verdict(VerdictAction.PASS).model_copy(update={"previous_action": "PASS"})
    rr._persist_run(_run_with(same))
    rr._persist_run(_run_with(_verdict(VerdictAction.APPROVE)))


def test_the_explainer_round_trips_through_the_stored_verdict_json():
    ex = fx.explain_flip(
        _side(_verdict(price=10.0)),
        _side(_verdict(VerdictAction.APPROVE, price=11.0), parts={**PARTS, "fact_sheet": "s2"}),
    )
    stored = _verdict(VerdictAction.APPROVE).model_copy(
        update={"previous_action": "PASS", "flip_explainer": ex},
    ).model_dump(mode="json")
    back = Verdict.model_validate(stored)
    assert back.flip_explainer == ex
    assert set(stored["flip_explainer"]) == {
        "previous_run_id", "previous_action", "new_action", "changed_inputs",
        "inputs_compared", "same_inputs_flip", "changed_answers", "answers_available",
        "answers_unavailable_reason", "cards_changes",
    }


# ── 4. the runner's stamp, and where the explainer surfaces ───────────────────


def test_runner_stamp_persists_the_explainer_and_the_journal_payload_carries_it():
    user = _user()
    _bank_prior(user, _verdict(VerdictAction.APPROVE, price=20.0), parts=dict(PARTS))
    now = datetime.now(timezone.utc)
    run = RoomRun(
        id=uuid4(), user_id=user, ticker="AAPL", triggered_at=now, started_at=now,
        finished_at=now, mandate_version=1, model_tier="cheap", credit_cost=0,
        status=RoomStatus.COMPLETED, verdict=_verdict(VerdictAction.PASS, price=21.0),
        bank_inputs={**PARTS, "fact_sheet": "fact_sheet-2"},
    )
    rr._stamp_flip_explainer(run, {}, {"bull_researcher": {"eq": "support/well"}})
    assert run.verdict.flip_explainer is not None
    assert run.verdict.claim_summary == {"bull_researcher": {"eq": "support/well"}}
    rr._persist_run(run)

    entry = rr.build_journal_entry_for_run(run, user)
    stored = entry.payload["verdict"]["flip_explainer"]
    assert stored["previous_action"] == "APPROVE" and stored["new_action"] == "PASS"
    assert "price moved from $20.00 to $21.00 (+5.0%)" in stored["changed_inputs"][0]["summary"]
