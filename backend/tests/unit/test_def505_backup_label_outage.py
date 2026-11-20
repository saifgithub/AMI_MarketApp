"""DEF505 — `llm_backup_used` must mean "the backup model produced this Room".

Found by the CR267 WP-14 forced-failover acceptance on Alpha: with the primary
AND the backup both unreachable, the Room restarted onto the backup, every desk
fell to its scripted turn, and the R51 NO_VERDICT verdict still carried
`llm_backup_used=true` plus the backup's model name. A client reading that told
the user the backup ran their Room. The stamp now requires at least one desk
the backup actually answered; the `provider_switch` event is unchanged.
"""

from __future__ import annotations

import asyncio

import pytest

from app.core import config as cfg
from app.schemas.room import VerdictAction
from app.services.credit_service import balance_for
from app.services.llm_gateway import FALLBACK_PROVIDER_NAME
from app.services.room_runner import RoomRunner, is_outage_shaped_verdict
from tests.unit.test_cr237_cio_retry import _seed_stored_mandate
from tests.unit.test_cr272_provider_slots_failover import (
    _FakeProvider,
    _gateway,
    _run_room,
)
from tests.unit.test_def425_shutdown_cancel_no_refund_gap import _billed_user


class _CioSilentProvider(_FakeProvider):
    """Desks answer; the CIO's stream is empty (DEF059 outage PASS shape)."""

    async def stream_chat(self, *, system_prompt, **kw):
        if "speak as the chief investment officer" in system_prompt.lower():
            return
            yield  # pragma: no cover
        async for c in super().stream_chat(system_prompt=system_prompt, **kw):
            yield c


def test_primary_down_backup_answers_keeps_the_label():
    g, _ = _gateway("http503", "ok")
    events, run, _u, _b, _c = _run_room(g)
    assert len([e for e in events if e.kind == "provider_switch"]) == 1
    assert run.verdict.action == VerdictAction.APPROVE.value
    assert run.verdict.llm_backup_used is True
    assert run.verdict.llm_backup_model == (cfg.settings.vllm_fallback_model or None)


def test_both_down_is_a_no_verdict_with_no_backup_label():
    g, _ = _gateway("http503", "http503")
    events, run, user_id, before, _c = _run_room(g)

    assert len([e for e in events if e.kind == "provider_switch"]) == 1
    v = run.verdict
    assert v.action == VerdictAction.NO_VERDICT.value
    assert is_outage_shaped_verdict(v.model_dump())
    assert v.llm_backup_used is False
    assert v.llm_backup_model is None
    assert run.refund_recorded is True
    assert balance_for(user_id)[0] == before
    streamed = [e for e in events if e.kind == "verdict"][0].verdict
    assert streamed.llm_backup_used is False and streamed.llm_backup_model is None


def _outage_pass_on_backup(monkeypatch, backup_cls_or_mode):
    """Primary down; backup restart ends in a CIO-outage PASS (cap disabled so
    an all-scripted Room is the PASS shape the CIO retry is offered on)."""
    monkeypatch.setattr(cfg.settings, "room_max_scripted_turns", 0)
    g, fakes = _gateway("http503", None)
    backup = (
        backup_cls_or_mode(FALLBACK_PROVIDER_NAME, "ok")
        if isinstance(backup_cls_or_mode, type)
        else _FakeProvider(FALLBACK_PROVIDER_NAME, backup_cls_or_mode)
    )
    g._providers[FALLBACK_PROVIDER_NAME] = backup
    user_id = _billed_user()
    mandate = _seed_stored_mandate(user_id)
    runner = RoomRunner(llm=g)
    from app.services.credit_service import spend
    spend(user_id, 12, reason="room:AAPL:test-charge")

    async def go():
        return [ev async for ev in runner.run(
            user_id=user_id, ticker="AAPL", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0, credit_cost=12,
        )]

    events = asyncio.run(go())
    run = runner.get_run(events[0].run_id)
    return g, fakes, runner, run, user_id


def _retry(runner, run_id, user_id):
    async def go():
        return [ev async for ev in runner.retry_cio_step(run_id, user_id=user_id)]
    return asyncio.run(go())


def test_retry_after_both_down_outage_carries_no_backup_label(monkeypatch):
    g, fakes, runner, run, user_id = _outage_pass_on_backup(monkeypatch, "http503")
    assert run.verdict.llm_backup_used is False

    fakes["vllm"].mode = "ok"  # primary recovers for the retry
    _retry(runner, run.id, user_id)

    run = runner.get_run(run.id)
    assert run.cio_retried is True
    assert run.verdict.action == VerdictAction.APPROVE.value
    assert run.verdict.llm_backup_used is False
    assert run.verdict.llm_backup_model is None


def test_retry_after_real_backup_desks_still_carries_the_label(monkeypatch):
    g, fakes, runner, run, user_id = _outage_pass_on_backup(monkeypatch, _CioSilentProvider)
    assert run.verdict.llm_backup_used is True  # the backup really answered the desks

    fakes["vllm"].mode = "ok"
    _retry(runner, run.id, user_id)

    run = runner.get_run(run.id)
    assert run.cio_retried is True
    assert run.verdict.llm_backup_used is True
    assert run.verdict.llm_backup_model == (cfg.settings.vllm_fallback_model or None)
