"""CR272 (CR267 WP-14) — provider slot kind, backup slot, retry, automatic failover.

What these pin, in the order a regression would hurt:

1. A `vllm`-kind slot is byte-identical to before; an `openai`-kind slot sends no
   vLLM-only body field and advertises JSON-schema grammar only.
2. Transient failures (503/429/connect) are retried before the first chunk and
   never after one; a slot that has not opted in (`max_retries=0`) is untouched.
3. Outside a Room, a call whose provider fails before any chunk is re-issued once
   on the backup slot, logged `llm_failover`, and the backup is named in `meta`.
   No backup, a pinned call, an in-band refusal, or a failure after a chunk: no
   failover.
4. Inside a Room the call is NOT re-issued — the whole Room restarts on the
   backup (one model per Room), once, charged once; a backup that also fails ends
   in the existing outage state with the existing refund; with no backup the
   existing scripted-fallback behaviour is unchanged.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx
import pytest
from pydantic import ValidationError

from app.core import config as cfg
from app.core.config import Settings
from app.schemas.room import VerdictAction
from app.services import llm_gateway as gw
from app.services.coach_engine import hydrate_coach_mandate
from app.services.credit_service import balance_for, spend
from app.services.llm_gateway import (
    FALLBACK_PROVIDER_NAME,
    ChatMessage,
    LLMGateway,
    LLMProvider,
    OpenAICompatibleProvider,
    OutputConstraint,
    VLLMProvider,
)
from app.services.room_runner import (
    ROOM_BACKUP_SWITCH_NOTICE,
    RoomRunner,
    is_llm_outage_verdict,
    is_outage_shaped_verdict,
)
from tests.unit.test_def425_shutdown_cancel_no_refund_gap import _billed_user

pytestmark = pytest.mark.allow_ledger_drift


# ── wire-level fakes (provider retry) ────────────────────────────────────────


class _Resp:
    def __init__(self, status: int, lines: list[str] | None = None, body: bytes = b""):
        self.status_code = status
        self._lines = lines or []
        self._body = body

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            if isinstance(line, Exception):
                raise line
            yield line

    async def aread(self) -> bytes:
        return self._body


class _SeqClient:
    """Answers each `stream()` call from a script: a `_Resp`, or an exception
    raised on entry (a connect error / timeout before any byte)."""

    def __init__(self, script: list[Any]):
        self._script = list(script)
        self.requests: list[dict] = []

    @asynccontextmanager
    async def stream(self, method: str, url: str, json: dict):
        self.requests.append(json)
        step = self._script.pop(0)
        if isinstance(step, Exception):
            raise step
        yield step

    async def aclose(self) -> None:
        pass


def _ok(text: str = "hello") -> _Resp:
    import json as _json

    return _Resp(
        200,
        [
            "data: " + _json.dumps({"choices": [{"delta": {"content": text}}]}),
            "data: [DONE]",
        ],
    )


def _provider(script, *, max_retries=3, kind="vllm", name="vllm") -> tuple[VLLMProvider, _SeqClient]:
    p = VLLMProvider(
        base_url="http://x", model_name="m", kind=kind, name=name,
        max_retries=max_retries, retry_backoff_s=0.0,
    )
    client = _SeqClient(script)
    p._client = client  # type: ignore[assignment]
    return p, client


async def _drain(provider, meta=None, **kw) -> str:
    out = []
    async for c in provider.stream_chat(
        system_prompt="x", messages=[ChatMessage(role="user", content="hi")],
        meta=meta, **kw,
    ):
        out.append(c)
    return "".join(out)


# ── 1. slot kind ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_vllm_kind_is_unchanged():
    p, client = _provider([_ok()], max_retries=0)
    assert p.supported_constraints == frozenset({"json_schema", "regex"})
    await _drain(p)
    assert client.requests[0]["chat_template_kwargs"] == {"enable_thinking": False}


@pytest.mark.asyncio
async def test_openai_kind_sends_no_vllm_only_field_and_drops_regex():
    p, client = _provider([_ok()], kind="openai")
    assert p.supported_constraints == frozenset({"json_schema"})
    await _drain(p)
    body = client.requests[0]
    assert "chat_template_kwargs" not in body
    assert "structured_outputs" not in body
    assert body["stream"] is True


@pytest.mark.asyncio
async def test_openai_kind_regex_grammar_is_recorded_unsupported_not_sent():
    p, client = _provider([_ok()], kind="openai")
    g = LLMGateway()
    g._providers["vllm"] = p
    meta: dict = {}
    async for _ in g.stream_chat(
        system_prompt="x", messages=[ChatMessage(role="user", content="hi")],
        meta=meta, constraint=OutputConstraint(name="money", regex=r"\d+"),
    ):
        pass
    assert meta["constraint"]["status"] == "unsupported"
    assert "structured_outputs" not in client.requests[0]


@pytest.mark.asyncio
async def test_openai_kind_json_schema_grammar_is_enforced_via_response_format():
    p, client = _provider([_ok()], kind="openai")
    g = LLMGateway()
    g._providers["vllm"] = p
    meta: dict = {}
    async for _ in g.stream_chat(
        system_prompt="x", messages=[ChatMessage(role="user", content="hi")],
        meta=meta,
        constraint=OutputConstraint(name="s", json_schema={"type": "object"}),
    ):
        pass
    assert meta["constraint"]["status"] == "enforced"
    assert client.requests[0]["response_format"]["type"] == "json_schema"


# ── 2. retry ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [503, 500, 429])
async def test_retries_http_failure_before_first_chunk(status):
    p, client = _provider([_Resp(status, body=b"busy"), _Resp(status), _ok("done")])
    assert await _drain(p) == "done"
    assert len(client.requests) == 3


@pytest.mark.asyncio
async def test_retries_connect_error_and_timeout_before_first_byte():
    p, client = _provider(
        [httpx.ConnectError("refused"), httpx.ReadTimeout("slow"), _ok("up")]
    )
    assert await _drain(p) == "up"
    assert len(client.requests) == 3


@pytest.mark.asyncio
async def test_retry_stops_at_three_then_the_sentinel_path_runs():
    p, client = _provider([_Resp(503)] * 4)
    meta: dict = {}
    text = await _drain(p, meta)
    assert len(client.requests) == 4  # 1 attempt + 3 retries
    assert "[AMI error: HTTP 503" in text
    assert meta["stream_error_status"] == 503


@pytest.mark.asyncio
async def test_retry_exhausted_connect_error_still_raises():
    p, client = _provider([httpx.ConnectError("refused")] * 4)
    with pytest.raises(httpx.ConnectError):
        await _drain(p)
    assert len(client.requests) == 4


@pytest.mark.asyncio
async def test_no_retry_once_a_chunk_has_been_yielded():
    mid_stream_failure = _Resp(
        200,
        [
            'data: {"choices": [{"delta": {"content": "partial"}}]}',
            httpx.ReadError("connection reset"),
        ],
    )
    p, client = _provider([mid_stream_failure, _ok("never")])
    got: list[str] = []
    with pytest.raises(httpx.ReadError):
        async for c in p.stream_chat(
            system_prompt="x", messages=[ChatMessage(role="user", content="hi")],
        ):
            got.append(c)
    assert got == ["partial"]
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_client_error_is_not_retried():
    p, client = _provider([_Resp(400, body=b"bad"), _ok()])
    meta: dict = {}
    text = await _drain(p, meta)
    assert len(client.requests) == 1
    assert "HTTP 400" in text and meta["stream_error_status"] == 400


@pytest.mark.asyncio
async def test_slot_without_retries_behaves_as_before():
    p, client = _provider([_Resp(503), _ok()], max_retries=0)
    text = await _drain(p)
    assert len(client.requests) == 1 and "HTTP 503" in text
    p2, client2 = _provider([httpx.ConnectError("x"), _ok()], max_retries=0)
    with pytest.raises(httpx.ConnectError):
        await _drain(p2)
    assert len(client2.requests) == 1


# ── gateway-level fakes ──────────────────────────────────────────────────────

PM_JSON = (
    '{"action": "APPROVE", "size_pct": 3.0, "entry": 150, "stop": 141, '
    '"target": 172, "horizon_days": 42, '
    '"narration": "Synthesis defended; the mandate clears at this size."}'
)


class _FakeProvider(LLMProvider):
    supported_constraints = frozenset()

    def __init__(self, name: str, mode: str = "ok"):
        self.name = name
        self.mode = mode
        self.calls = 0

    async def stream_chat(self, *, system_prompt, messages, model_tier="cheap",
                          max_tokens=1024, meta=None, constraint=None):
        self.calls += 1
        if self.mode == "http503":
            if meta is not None:
                meta["stream_error"] = "HTTP 503: down"
                meta["stream_error_status"] = 503
            yield "\n\n[AMI error: HTTP 503 from the upstream provider]"
            return
        if self.mode == "connect":
            raise httpx.ConnectError("refused")
        if self.mode == "hang":
            await asyncio.sleep(3600)
        if self.mode == "inband":
            if meta is not None:
                meta["stream_error"] = "grammar refused"
            yield "\n\n[AMI error: refused mid-stream]"
            return
        if self.mode == "chunk_then_boom":
            yield "partial"
            raise httpx.ReadError("boom")
        if "speak as the chief investment officer" in system_prompt.lower():
            yield PM_JSON
            return
        yield (
            f"[STANCE: for | CONVICTION: high | HEADLINE: view]\n"
            f"reply from {self.name}"
        )


def _gateway(primary: str | None, backup: str | None) -> tuple[LLMGateway, dict]:
    g = LLMGateway()
    fakes: dict[str, _FakeProvider] = {}
    if primary is not None:
        fakes["vllm"] = _FakeProvider("vllm", primary)
    if backup is not None:
        fakes[FALLBACK_PROVIDER_NAME] = _FakeProvider(FALLBACK_PROVIDER_NAME, backup)
    g._providers.update(fakes)
    return g, fakes


async def _call(g: LLMGateway, meta=None, **kw) -> str:
    out = []
    async for c in g.stream_chat(
        system_prompt="x", messages=[ChatMessage(role="user", content="hi")],
        audit_flow="one_on_one", meta=meta, **kw,
    ):
        out.append(c)
    return "".join(out)


@pytest.fixture
def logs(monkeypatch):
    events: list[tuple[str, dict]] = []
    real_warning = gw.logger.warning

    def _capture(event, **kw):
        events.append((event, kw))
        return real_warning(event, **kw)

    monkeypatch.setattr(gw.logger, "warning", _capture)
    return events


# ── 3. single-call failover (1-on-1 / Brief shape) ───────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["http503", "connect"])
async def test_primary_failure_fails_over_to_backup_and_is_logged(mode, logs):
    g, fakes = _gateway(mode, "ok")
    meta: dict = {}
    text = await _call(g, meta)
    assert text == "[STANCE: for | CONVICTION: high | HEADLINE: view]\nreply from vllm_fallback"
    assert "AMI error" not in text  # the failed attempt's sentinel is dropped
    assert fakes["vllm"].calls == 1 and fakes[FALLBACK_PROVIDER_NAME].calls == 1
    assert meta["failover"]["from"] == "vllm"
    assert meta["failover"]["to"] == FALLBACK_PROVIDER_NAME
    assert "stream_error" not in meta
    fo = [kw for ev, kw in logs if ev == "llm_failover"]
    assert len(fo) == 1
    assert fo[0]["surface"] == "one_on_one"
    assert fo[0]["from_provider"] == "vllm" and fo[0]["to"] == FALLBACK_PROVIDER_NAME
    assert fo[0]["reason"]


@pytest.mark.asyncio
async def test_failover_audits_each_attempt_under_its_own_provider():
    from sqlalchemy import select

    from app.db.models import LLMAuditRow
    from app.db.session import get_session

    g, _ = _gateway("http503", "ok")
    marker = f"cr272-audit-{id(g)}"
    async for _ in g.stream_chat(
        system_prompt=marker, messages=[ChatMessage(role="user", content="hi")],
        audit_flow="brief",
    ):
        pass
    with get_session() as s:
        rows = s.execute(
            select(LLMAuditRow).where(LLMAuditRow.system_prompt.contains(marker))
        ).scalars().all()
    assert sorted(r.provider for r in rows) == sorted(["vllm", FALLBACK_PROVIDER_NAME])
    failed = next(r for r in rows if r.provider == "vllm")
    assert failed.error


@pytest.mark.asyncio
async def test_no_backup_registered_keeps_todays_behaviour(logs):
    g, fakes = _gateway("http503", None)
    meta: dict = {}
    text = await _call(g, meta)
    assert "[AMI error: HTTP 503" in text
    assert meta["stream_error_status"] == 503 and "failover" not in meta
    assert not [e for e, _ in logs if e == "llm_failover"]

    g2, _ = _gateway("connect", None)
    with pytest.raises(httpx.ConnectError):
        await _call(g2)


@pytest.mark.asyncio
async def test_no_failover_after_a_chunk_was_yielded(logs):
    g, fakes = _gateway("chunk_then_boom", "ok")
    got: list[str] = []
    with pytest.raises(httpx.ReadError):
        async for c in g.stream_chat(
            system_prompt="x", messages=[ChatMessage(role="user", content="hi")],
        ):
            got.append(c)
    assert got == ["partial"]
    assert fakes[FALLBACK_PROVIDER_NAME].calls == 0


@pytest.mark.asyncio
async def test_inband_refusal_is_not_failed_over():
    g, fakes = _gateway("inband", "ok")
    meta: dict = {}
    text = await _call(g, meta)
    assert "refused mid-stream" in text
    assert fakes[FALLBACK_PROVIDER_NAME].calls == 0 and "failover" not in meta


@pytest.mark.asyncio
async def test_pinned_call_is_never_failed_over():
    g, fakes = _gateway("http503", "ok")
    text = await _call(g, provider_name="vllm")
    assert "[AMI error: HTTP 503" in text
    assert fakes[FALLBACK_PROVIDER_NAME].calls == 0


@pytest.mark.asyncio
async def test_backup_also_failing_surfaces_the_backups_failure():
    g, fakes = _gateway("http503", "http503")
    meta: dict = {}
    text = await _call(g, meta)
    assert "[AMI error: HTTP 503" in text
    assert meta["stream_error_status"] == 503
    assert meta["failover"]["to"] == FALLBACK_PROVIDER_NAME
    assert fakes["vllm"].calls == 1 and fakes[FALLBACK_PROVIDER_NAME].calls == 1


# ── registration + config ────────────────────────────────────────────────────


def test_backup_registered_from_settings_and_never_in_preference(monkeypatch):
    s = cfg.settings
    monkeypatch.setattr(s, "vllm_base_url", "http://lan:8000")
    monkeypatch.setattr(s, "vllm_fallback_base_url", "https://api.deepinfra.com")
    monkeypatch.setattr(s, "vllm_fallback_model", "some/model")
    monkeypatch.setattr(s, "vllm_fallback_api_key", "k")
    monkeypatch.setattr(s, "vllm_fallback_kind", "openai")
    g = LLMGateway()
    backup = g._providers[FALLBACK_PROVIDER_NAME]
    assert isinstance(backup, OpenAICompatibleProvider)
    assert backup.name == FALLBACK_PROVIDER_NAME
    assert backup.supported_constraints == frozenset({"json_schema"})
    assert backup._max_retries == s.llm_transient_retries
    assert FALLBACK_PROVIDER_NAME not in g._PREFERENCE
    assert g._active_provider_name() == "vllm"
    assert g.has_backup_provider() is True
    assert g.status()["backup_provider"] == FALLBACK_PROVIDER_NAME
    # a vllm-kind primary is retried only because a backup exists
    assert g._providers["vllm"]._max_retries == s.llm_transient_retries


def test_vllm_primary_without_backup_gets_no_retry_and_no_status_key(monkeypatch):
    s = cfg.settings
    monkeypatch.setattr(s, "vllm_base_url", "http://lan:8000")
    monkeypatch.setattr(s, "vllm_fallback_base_url", "")
    monkeypatch.setattr(s, "vllm_kind", "vllm")
    g = LLMGateway()
    assert FALLBACK_PROVIDER_NAME not in g._providers
    assert g._providers["vllm"]._max_retries == 0
    assert "backup_provider" not in g.status()
    assert g.has_backup_provider() is False


def test_hosted_primary_is_retried_without_a_backup(monkeypatch):
    s = cfg.settings
    monkeypatch.setattr(s, "vllm_base_url", "https://api.deepinfra.com")
    monkeypatch.setattr(s, "vllm_fallback_base_url", "")
    monkeypatch.setattr(s, "vllm_kind", "openai")
    g = LLMGateway()
    prim = g._providers["vllm"]
    assert prim.kind == "openai" and prim._max_retries == s.llm_transient_retries


def test_fallback_url_without_model_refuses_boot():
    with pytest.raises(ValidationError):
        Settings(vllm_fallback_base_url="https://x", vllm_fallback_model="")


def test_fallback_settings_are_forwarded_in_compose():
    from pathlib import Path

    compose = (Path(__file__).resolve().parents[3] / "docker-compose.yml").read_text()
    for key in (
        "VLLM_KIND", "VLLM_FALLBACK_BASE_URL", "VLLM_FALLBACK_MODEL",
        "VLLM_FALLBACK_API_KEY", "VLLM_FALLBACK_KIND",
        "LLM_TRANSIENT_RETRIES", "LLM_RETRY_BACKOFF_S",
    ):
        assert f"      {key}: " in compose, key


# ── 4. Room: restart the whole Room on the backup ────────────────────────────

CREDIT_COST = 12


def _run_room(g: LLMGateway, *, user_id=None, agent_timeout_s=None):
    user_id = user_id or _billed_user()
    before = balance_for(user_id)[0]
    spend(user_id, CREDIT_COST, reason="room:AAPL:test-charge")
    charged = balance_for(user_id)[0]
    assert charged == before - CREDIT_COST
    runner = RoomRunner(llm=g)

    async def go():
        return [ev async for ev in runner.run(
            user_id=user_id, ticker="AAPL",
            mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
            char_delay_min=0.0, char_delay_max=0.0, credit_cost=CREDIT_COST,
            **({"agent_timeout_s": agent_timeout_s} if agent_timeout_s else {}),
        )]

    events = asyncio.run(go())
    run = runner.get_run(events[0].run_id)
    return events, run, user_id, before, charged


@pytest.mark.parametrize("mode", ["http503", "connect"])
def test_room_primary_failure_restarts_whole_room_on_backup(mode, logs):
    g, fakes = _gateway(mode, "ok")
    events, run, user_id, before, charged = _run_room(g)

    switches = [e for e in events if e.kind == "provider_switch"]
    assert len(switches) == 1
    assert switches[0].text == ROOM_BACKUP_SWITCH_NOTICE
    assert "backup model" in ROOM_BACKUP_SWITCH_NOTICE

    # restarted from phase 0: ANALYSTS appears twice, then the full ladder
    phases = [e.phase for e in events if e.kind == "phase"]
    assert phases[0] == "ANALYSTS" and phases[1] == "ANALYSTS"
    assert phases[1:] == [
        "ANALYSTS", "RESEARCHERS", "SYNTHESIS", "EXECUTION", "RISK", "VERDICT"
    ]
    # nothing from the voided attempt streamed after the failed analyst phase
    switch_at = events.index(switches[0])
    assert not [e for e in events[:switch_at] if e.kind in ("agent_token", "verdict")]

    # one Room never mixes two models: the whole transcript is the backup's
    for m in run.transcript:
        if m.agent_id.value != "portfolio_manager":
            assert "reply from vllm_fallback" in m.content
            assert "reply from vllm" not in m.content.replace("vllm_fallback", "")
    # the primary was never asked again after the restart
    assert fakes["vllm"].calls <= 4  # only the ANALYSTS fan-out of the failed attempt

    verdicts = [e for e in events if e.kind == "verdict"]
    assert len(verdicts) == 1
    assert verdicts[0].verdict.action == VerdictAction.APPROVE.value
    assert run.verdict.llm_backup_used is True
    assert run.verdict.llm_backup_model == cfg.settings.vllm_fallback_model or (
        run.verdict.llm_backup_model is None
    )
    assert run.status == "completed"

    # charged once: run() never spends, so the balance is exactly the one charge
    assert balance_for(user_id)[0] == charged
    assert not run.refund_recorded

    fo = [kw for ev, kw in logs if ev == "llm_failover"]
    assert len(fo) == 1 and fo[0]["surface"] == "room"
    assert fo[0]["from_provider"] == "vllm" and fo[0]["to"] == FALLBACK_PROVIDER_NAME


def test_room_primary_that_hangs_before_the_first_chunk_also_restarts_on_backup():
    g, fakes = _gateway("hang", "ok")
    events, run, user_id, before, charged = _run_room(g, agent_timeout_s=0.3)
    assert len([e for e in events if e.kind == "provider_switch"]) == 1
    assert run.verdict.llm_backup_used is True
    assert run.verdict.action == VerdictAction.APPROVE.value
    assert balance_for(user_id)[0] == charged


def test_room_backup_also_failing_ends_in_outage_state_with_refund():
    g, fakes = _gateway("http503", "http503")
    events, run, user_id, before, charged = _run_room(g)

    assert len([e for e in events if e.kind == "provider_switch"]) == 1  # restarts once
    verdicts = [e for e in events if e.kind == "verdict"]
    assert len(verdicts) == 1
    v = verdicts[0].verdict
    assert is_outage_shaped_verdict(v.model_dump())
    assert v.action != VerdictAction.APPROVE.value  # never a default/approving verdict
    assert run.refund_recorded is True
    assert balance_for(user_id)[0] == before  # refunded through the existing path
    assert run.verdict.llm_backup_used is True


def test_room_with_no_backup_keeps_the_scripted_fallback_behaviour():
    g, fakes = _gateway("http503", None)
    events, run, user_id, before, charged = _run_room(g)

    assert not [e for e in events if e.kind == "provider_switch"]
    phases = [e.phase for e in events if e.kind == "phase"]
    assert phases == ["ANALYSTS", "RESEARCHERS", "SYNTHESIS", "EXECUTION", "RISK", "VERDICT"]
    v = run.verdict
    assert v.llm_backup_used is False
    # today's behaviour: every desk fell back to its scripted turn, and the
    # all-down Room is an outage-shaped verdict that the existing path refunds
    assert (v.scripted_turns or 0) > 0
    assert is_outage_shaped_verdict(v.model_dump())
    assert balance_for(user_id)[0] == before


def test_room_with_healthy_primary_and_a_backup_never_switches():
    g, fakes = _gateway("ok", "ok")
    events, run, user_id, before, charged = _run_room(g)
    assert not [e for e in events if e.kind == "provider_switch"]
    assert fakes[FALLBACK_PROVIDER_NAME].calls == 0
    assert run.verdict.llm_backup_used is False
    assert balance_for(user_id)[0] == charged


def test_failover_state_does_not_leak_past_the_run():
    g, _ = _gateway("http503", "ok")
    runner = RoomRunner(llm=g)

    async def go():
        async for _ in runner.run(
            user_id=_billed_user(), ticker="AAPL",
            mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
            char_delay_min=0.0, char_delay_max=0.0, credit_cost=CREDIT_COST,
        ):
            pass
        return gw._ROOM_FAILOVER.get()

    assert asyncio.run(go()) is None
