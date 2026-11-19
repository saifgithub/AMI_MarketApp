"""DEF493 — the second-pass verdict review's provider on hosted-only (Beta) and
on-prem-only (Alpha) configs, and the no-Anthropic rule.

`pick_review_provider` considered only the `_PREFERENCE` slots (vllm,
anthropic, kimi). Beta runs a hosted model through the `vllm` slot
(`VLLM_KIND=openai`) with the CR272 backup `vllm_fallback` and no Anthropic or
Kimi key, so it returned None and every routed review was skipped as
`no_fallback_provider` (DEF059 class: a verdict the user may believe was
audited). What these pin:

1. Beta shape (hosted primary + backup, different models) -> the backup is the
   review provider (independent) and the review really runs over the wire.
2. A Room failed over to the backup is reviewed by the primary.
3. Saiful 2026-11-19: NO Anthropic model anywhere. A config that HAS an
   Anthropic key never reviews with it, structurally.
4. Only one model configured (on-prem Alpha, or hosted Beta without a backup,
   or a backup on the same model) -> the review runs on the desk's own model
   and says so (`same_model_review`, warning log): never presented as an
   independent opinion.
5. No real provider at all -> None, and the skip is visible: error log +
   `skipped_reason` on the verdict record, verdict unchanged, no call made.
"""

from __future__ import annotations

import json

import pytest
from app.core import config as cfg
from app.schemas import AgentId
from app.schemas.room import Verdict, VerdictAction
from app.services.llm_gateway import (
    FALLBACK_PROVIDER_NAME,
    LLMGateway,
    RoomFailoverState,
    arm_room_failover,
)
from app.services import room_runner as rr
from app.services.room_runner import _apply_verdict_review
from tests.unit.test_cr247_4_verdict_review import (
    BEAR_CASE,
    CONSERVATIVE_CASE,
    VETO_JSON,
    _handoff,
)
from tests.unit.test_cr272_provider_slots_failover import _ok, _SeqClient


def _config(
    monkeypatch, *, primary="hosted", backup=None, anthropic=False,
    backup_model="other/model",
):
    s = cfg.settings
    monkeypatch.setattr(s, "anthropic_api_key", "sk-test" if anthropic else "")
    monkeypatch.setattr(s, "kimi_api_key", "")
    monkeypatch.setattr(s, "vllm_base_url", "https://api.example-host.test")
    monkeypatch.setattr(s, "vllm_kind", "openai" if primary == "hosted" else "vllm")
    monkeypatch.setattr(s, "vllm_model", "primary/model")
    monkeypatch.setattr(s, "vllm_fallback_base_url", backup or "")
    monkeypatch.setattr(s, "vllm_fallback_model", backup_model if backup else "")
    monkeypatch.setattr(s, "vllm_fallback_api_key", "k" if backup else "")
    monkeypatch.setattr(s, "vllm_fallback_kind", "openai")
    return LLMGateway()


@pytest.fixture
def logs(monkeypatch):
    """Events logged by room_runner, as (level, event, kwargs). Patches the
    logger's methods rather than using structlog's capture_logs, which misses
    a logger already cached by an earlier test in the full suite."""
    events: list[tuple[str, str, dict]] = []
    for level in ("warning", "error"):
        real = getattr(rr.logger, level)

        def _cap(event, _level=level, _real=real, **kw):
            events.append((_level, event, kw))
            return _real(event, **kw)

        monkeypatch.setattr(rr.logger, level, _cap)
    return events


BETA_BACKUP = "https://api.example-host.test"


def test_beta_shape_picks_the_backup_slot(monkeypatch):
    g = _config(monkeypatch, backup=BETA_BACKUP)
    assert g._active_provider_name() == "vllm"
    assert g.pick_review_provider() == FALLBACK_PROVIDER_NAME
    assert g.review_is_independent(FALLBACK_PROVIDER_NAME) is True


def test_room_pinned_to_the_backup_is_reviewed_by_the_primary(monkeypatch):
    g = _config(monkeypatch, backup=BETA_BACKUP)
    arm_room_failover(RoomFailoverState(pinned_provider=FALLBACK_PROVIDER_NAME))
    try:
        assert g.pick_review_provider() == "vllm"
        assert g.review_is_independent("vllm") is True
    finally:
        arm_room_failover(None)


def test_the_provider_that_tripped_the_failover_is_not_asked_to_audit(monkeypatch):
    g = _config(monkeypatch, backup=BETA_BACKUP)
    arm_room_failover(RoomFailoverState(
        pinned_provider=FALLBACK_PROVIDER_NAME, tripped_provider="vllm",
    ))
    try:
        assert g.pick_review_provider() == FALLBACK_PROVIDER_NAME
        assert g.review_is_independent(FALLBACK_PROVIDER_NAME) is False
    finally:
        arm_room_failover(None)


def test_hosted_primary_alone_reviews_on_its_own_model_flagged_not_independent(
    monkeypatch,
):
    g = _config(monkeypatch, backup=None)
    assert g.pick_review_provider() == "vllm"
    assert g.review_is_independent("vllm") is False


def test_backup_on_the_same_model_is_not_independent(monkeypatch):
    g = _config(monkeypatch, backup=BETA_BACKUP, backup_model="primary/model")
    assert g.pick_review_provider() == "vllm"
    assert g.review_is_independent("vllm") is False


def test_alpha_onprem_only_reviews_on_vllm_flagged_not_independent(monkeypatch):
    g = _config(monkeypatch, primary="onprem", backup=None)
    assert g.pick_review_provider() == "vllm"
    assert g.review_is_independent("vllm") is False


@pytest.mark.parametrize("backup", [None, BETA_BACKUP])
def test_a_keyed_anthropic_is_never_the_review_provider(monkeypatch, backup):
    g = _config(monkeypatch, primary="onprem", backup=backup, anthropic=True)
    assert "anthropic" in g._providers
    picked = g.pick_review_provider()
    assert picked != "anthropic"
    assert picked == (FALLBACK_PROVIDER_NAME if backup else "vllm")


def test_anthropic_as_the_only_provider_leaves_no_review_provider(monkeypatch):
    s = cfg.settings
    monkeypatch.setattr(s, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(s, "kimi_api_key", "")
    monkeypatch.setattr(s, "vllm_base_url", "")
    monkeypatch.setattr(s, "vllm_fallback_base_url", "")
    g = LLMGateway()
    assert g._active_provider_name() == "anthropic"
    assert g.pick_review_provider() is None


def test_no_real_provider_at_all(monkeypatch):
    monkeypatch.setattr(cfg.settings, "anthropic_api_key", "")
    monkeypatch.setattr(cfg.settings, "kimi_api_key", "")
    monkeypatch.setattr(cfg.settings, "vllm_base_url", "")
    monkeypatch.setattr(cfg.settings, "vllm_fallback_base_url", "")
    assert LLMGateway().pick_review_provider() is None


_VERDICT = Verdict(
    action=VerdictAction.APPROVE, size_pct=3.0, entry=150.0,
    stop=141.0, target=172.0, time_horizon_days=42,
    reason="PM: APPROVE; synthesis defended.",
    kill_criterion="A close below $141.",
)


async def _review(g: LLMGateway):
    ctx, room_run = _handoff({
        AgentId.BEAR_RESEARCHER: BEAR_CASE,
        AgentId.CONSERVATIVE_DEBATOR: CONSERVATIVE_CASE,
    })
    return await _apply_verdict_review(
        verdict=_VERDICT, pm_outage=False, parsed=_VERDICT, live=True,
        run_id=__import__("uuid").uuid4(), ctx=ctx, profile={}, formatter={},
        mandate=ctx.mandate, run=room_run, gateway=g, agent_timeout_s=30.0,
    )


@pytest.mark.asyncio
async def test_beta_shape_review_runs_on_the_backup_over_the_wire(monkeypatch):
    g = _config(monkeypatch, backup=BETA_BACKUP)
    primary_wire = _SeqClient([])
    backup_wire = _SeqClient([_ok(VETO_JSON)])
    g._providers["vllm"]._client = primary_wire  # type: ignore[attr-defined]
    g._providers[FALLBACK_PROVIDER_NAME]._client = backup_wire  # type: ignore[attr-defined]

    final, _ = await _review(g)

    assert primary_wire.requests == [], "the desk's own model must not audit itself"
    assert len(backup_wire.requests) == 1
    assert backup_wire.requests[0]["model"] == "other/model"
    rec = final.verdict_review
    assert rec is not None and rec.skipped_reason is None
    assert rec.provider == FALLBACK_PROVIDER_NAME
    assert rec.same_model_review is False
    assert rec.decision == "veto"
    assert final.action == VerdictAction.PASS.value, "the audit's veto flips the approve"


@pytest.mark.asyncio
@pytest.mark.parametrize("primary", ["hosted", "onprem"])
async def test_single_model_review_runs_and_says_it_is_the_same_model(
    monkeypatch, primary, logs,
):
    g = _config(monkeypatch, primary=primary, backup=None, anthropic=True)
    wire = _SeqClient([_ok(VETO_JSON)])
    g._providers["vllm"]._client = wire  # type: ignore[attr-defined]

    final, _ = await _review(g)

    assert len(wire.requests) == 1
    rec = final.verdict_review
    assert rec is not None and rec.skipped_reason is None
    assert rec.provider == "vllm"
    assert rec.same_model_review is True
    assert rec.decision == "veto"
    warned = [e for e in logs if e[1] == "room_verdict_review_same_model"]
    assert len(warned) == 1 and warned[0][0] == "warning"
    assert json.loads(final.model_dump_json())["verdict_review"]["same_model_review"]


@pytest.mark.asyncio
async def test_no_provider_is_visibly_not_reviewed(monkeypatch, logs):
    s = cfg.settings
    monkeypatch.setattr(s, "anthropic_api_key", "sk-test")  # present, still ineligible
    monkeypatch.setattr(s, "kimi_api_key", "")
    monkeypatch.setattr(s, "vllm_base_url", "")
    monkeypatch.setattr(s, "vllm_fallback_base_url", "")
    g = LLMGateway()
    g._providers["anthropic"].stream_chat = None  # type: ignore[method-assign]  # must never be called

    final, override = await _review(g)

    errors = [e for e in logs if e[1] == "room_verdict_review_no_provider"]
    assert len(errors) == 1 and errors[0][0] == "error"
    rec = final.verdict_review
    assert rec is not None
    assert rec.skipped_reason == "no_fallback_provider"
    assert rec.provider is None and rec.decision is None
    assert rec.same_model_review is False
    assert final.action == VerdictAction.APPROVE.value
    assert override is None
    assert json.loads(final.model_dump_json())["verdict_review"]["skipped_reason"]
