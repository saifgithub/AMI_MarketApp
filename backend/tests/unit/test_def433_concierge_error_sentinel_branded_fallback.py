"""DEF433 — the Concierge chat could show the raw upstream-error sentinel.

Found by the DEF424 minors worker (2026-09-25): `agent_runner.py::_stream_
concierge` catches only a RAISED exception (the transport-down shape, fixed
under RETRO-SECURITY MAJOR-2 round 3). The in-band `[AMI error: HTTP 503 from
the upstream provider (vllm). Check backend logs.]` sentinel
(`llm_gateway.py`'s non-200 / in-band-SSE-error branches) never raises — it
sets `meta["stream_error"]` and yields its own sentinel text as an ordinary
chunk, which used to land straight in `buf` and out to the user. The trailing
`if not "".join(buf).strip():` empty-buffer fallback never fired because
`buf` wasn't empty once the sentinel text was appended to it. Brief and non-
Concierge 1-on-1 got this exact fix under DEF424 post-COMPLETE MINOR-1; the
Concierge was deliberately left alone there because it has its own scripted
fallback (`concierge_scripted_reply`) rather than `canned_agent_fallback`,
making the correct fix a small design choice instead of a one-line mirror.

This closes that gap: `_stream_concierge` now detects `meta["stream_error"]`
transitioning from unset to set on a yielded chunk (structural — the same
key `one_on_one.py` already reads for the refund decision, never string-
matching the sentinel's own prose) and swaps that chunk for the Concierge's
own scripted/branded reply while `buf` is still empty. A sentinel arriving
mid-stream (after real content already streamed) is a different case from
DEF424's own MINOR-2: DEF424's mid-stream failure is a RAISED exception (no
provider text ever reaches a chunk), so "leave the buffer as-is" was safe
there. Here the sentinel IS the chunk on the wire — `[AMI error: the
upstream provider (vllm) refused this request mid-stream. Check backend
logs.]` — so leaving it as-is would still leak provider name + operator
text after real content. Instead that one chunk is swapped for the same
short branded cut-off line ("— AMI lost the connection mid-reply; this turn
wasn't charged.") the raised-exception branch already uses for its own
mid-stream case — never concatenated after real content, just substituted
for the sentinel chunk itself.

Concierge turns ARE charged and refunded exactly like every other 1-on-1
turn — `one_on_one_cost()` is a flat per-turn price with no agent-specific
carve-out; "Concierge is always free" in one_on_one.py:119 refers only to
DEF179's lesson-unlock GATE, not the credit charge. So the same
`stream_meta.get("stream_error")` refund check in `one_on_one.py` already
covers the Concierge; this defect was a copy/UX leak, never a billing gap
(confirmed by the `test_..._success_still_bills_normally` control, and by
the ledger assertions on every failure-path test below).

These tests drive the REAL `LLMGateway` + a REAL `VLLMProvider` (the live-
preference provider), transport faked via `httpx.MockTransport` /
`httpx.AsyncBaseTransport` — the same pattern
`test_def424_llm_down_branded_fallback.py` and
`test_def113_one_on_one_credit_gate.py`'s round-3 Concierge tests use.
"""

from __future__ import annotations

import httpx as _httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.one_on_one import router as one_on_one_router
from app.db import get_session
from app.db.models import SubscriptionEventRow, User
from app.services.auth_service import AuthService
from app.services.credit_service import balance_for
from app.services.rate_limit import (
    agent_stream_concurrency_limit,
    one_on_one_message_rate_limit,
)


@pytest.fixture(autouse=True)
def _reset_limiters():
    one_on_one_message_rate_limit.reset()
    agent_stream_concurrency_limit.reset()
    yield
    one_on_one_message_rate_limit.reset()
    agent_stream_concurrency_limit.reset()


def _new_user() -> tuple[str, dict]:
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        s.get(User, user.id).plan = "trader"
    return user.id, {"Authorization": f"Bearer {token}"}


def _ledger(user_id) -> list[SubscriptionEventRow]:
    with get_session() as s:
        return list(s.execute(
            select(SubscriptionEventRow).where(
                SubscriptionEventRow.user_id == user_id
            )
        ).scalars())


def _http_503_handler(request):
    return _httpx.Response(503, text="upstream unavailable")


def _ok_handler(request):
    body = (
        b'data: {"choices":[{"delta":{"content":"hello from the Concierge"}}]}\n\n'
        b'data: [DONE]\n\n'
    )
    return _httpx.Response(
        200, content=body, headers={"content-type": "text/event-stream"},
    )


class _PartialThenSentinelTransport(_httpx.AsyncBaseTransport):
    """Real content streams, THEN the provider emits the in-band error frame
    mid-body (a refusal partway through, not an up-front non-200). This is
    the in-stream-sentinel-after-real-content shape — distinct from a raised
    transport exception mid-reply (which DEF424's MINOR-2 already covers).
    """

    async def handle_async_request(self, request):
        async def _body():
            yield b'data: {"choices":[{"delta":{"content":"partial real "}}]}\n\n'
            yield b'data: {"choices":[{"delta":{"content":"content before "}}]}\n\n'
            yield b'data: {"error": {"message": "the model refused mid-stream"}}\n\n'

        return _httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=_AsyncIterStream(_body()),
        )


class _PartialThenDropTransport(_httpx.AsyncBaseTransport):
    """Real content streams, THEN the connection itself dies mid-body — a
    RAISED `httpx.ReadError` out of `aiter_lines()`, not an in-band sentinel
    frame. This is `_stream_concierge`'s own `except Exception` branch (its
    pre-existing RETRO-SECURITY MAJOR-2 handler, untouched by DEF433's
    `newly_errored` addition above it) exercised with a non-empty `buf` —
    the DEF424 MINOR-2 shape, but for the Concierge specifically, which has
    its own separate exception handler and was never covered by DEF424's own
    `test_..._partial_stream_then_drop_appends_cutoff_notice` tests (those
    only drove the non-Concierge 1-on-1 and Brief branches).
    """

    async def handle_async_request(self, request):
        async def _body():
            yield b'data: {"choices":[{"delta":{"content":"partial real "}}]}\n\n'
            yield b'data: {"choices":[{"delta":{"content":"content before "}}]}\n\n'
            raise _httpx.ReadError("connection dropped mid-stream", request=request)

        return _httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=_AsyncIterStream(_body()),
        )


class _AsyncIterStream(_httpx.AsyncByteStream):
    def __init__(self, gen):
        self._gen = gen

    async def __aiter__(self):
        async for chunk in self._gen:
            yield chunk

    async def aclose(self) -> None:
        pass


@pytest.fixture
def _real_vllm_gateway(monkeypatch):
    from app.core import config as config_mod
    from app.services import agent_runner as agent_runner_mod
    from app.services import llm_gateway as gw_mod

    monkeypatch.setattr(config_mod.settings, "vllm_base_url", "http://fake-vllm:8000")
    monkeypatch.setattr(config_mod.settings, "vllm_model", "test-model")
    monkeypatch.setattr(config_mod.settings, "vllm_api_key", "")

    gateway = gw_mod.LLMGateway()
    assert "vllm" in gateway._providers
    assert gateway._active_provider_name() == "vllm"

    def _wire(handler_or_transport):
        provider = gateway._providers["vllm"]
        transport = (
            handler_or_transport
            if isinstance(handler_or_transport, _httpx.AsyncBaseTransport)
            else _httpx.MockTransport(handler_or_transport)
        )
        provider._client = _httpx.AsyncClient(
            base_url="http://fake-vllm:8000",
            transport=transport,
        )
        return gateway

    monkeypatch.setattr(gw_mod, "_gateway", None)
    monkeypatch.setattr(gw_mod, "get_llm_gateway", lambda: gateway)

    monkeypatch.setattr(agent_runner_mod, "_runner", None)
    monkeypatch.setattr(
        agent_runner_mod, "get_agent_runner",
        lambda: agent_runner_mod.AgentRunner(gateway),
    )

    return _wire


@pytest.fixture
def client() -> TestClient:
    a = FastAPI()
    a.include_router(one_on_one_router)
    return TestClient(a, raise_server_exceptions=False)


def _open_concierge(client: TestClient, headers: dict) -> str:
    r = client.post(
        "/v1/agents/one_on_one/start",
        json={"agent_id": "concierge"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _send(client: TestClient, headers: dict, session_id: str, msg: str = "hi there"):
    return client.post(
        "/v1/agents/one_on_one/message",
        json={"session_id": session_id, "user_message": msg},
        headers=headers,
    )


def test_http_503_sentinel_yields_branded_scripted_reply_no_leak(
    client, monkeypatch, _real_vllm_gateway,
):
    """The defect's own repro shape: a reachable host answering a real HTTP
    503 hits the gateway's existing non-200 branch, which sets
    `meta["stream_error"]` and yields `[AMI error: HTTP 503 from the
    upstream provider (vllm). Check backend logs.]` as ordinary stream text.
    Before this fix that sentinel sailed straight into `buf` and out to the
    wire. Now: the Concierge's own scripted fallback replaces it."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 3)

    _real_vllm_gateway(_http_503_handler)

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_concierge(client, headers)

    r = _send(client, headers, session_id)
    assert r.status_code == 200, r.text

    lower = r.text.lower()
    assert "upstream unavailable" not in lower, (
        "the raw httpx response body must never reach the client"
    )
    assert "vllm" not in lower
    assert "503" not in r.text
    assert "backend logs" not in lower
    assert "AMI error" not in r.text
    assert "AMI" in r.text, "the Concierge's own scripted reply is branded AMI copy"
    # DEF433 r1 MINOR-1 (u66): with no text yet, the reply must be the
    # Concierge's scripted answer, not the bare mid-reply cut-off line; the
    # checks above pass for either.
    assert "fallback mode" in lower, "an empty-buffer outage gets the scripted reply"
    assert "lost the connection" not in lower

    assert balance_for(user_id)[0] == before, (
        "an HTTP-503 Concierge turn must net to zero credits (spent then refunded)"
    )
    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 1


def test_partial_reply_then_inband_sentinel_keeps_partial_no_leak(
    client, monkeypatch, _real_vllm_gateway,
):
    """The provider streams real content, then emits the in-band error frame
    mid-body. `buf` is non-empty by the time the sentinel chunk arrives, so
    the branded-scripted-reply swap-in doesn't fire (concatenating a whole
    scripted reply after real partial content would read as nonsense — same
    call DEF424 made) — but the sentinel CHUNK ITSELF must not ride the wire
    unchanged: `[AMI error: the upstream provider (vllm) refused this
    request mid-stream. Check backend logs.]` is provider name + operator
    text, not something DEF433 leaves in an already-real reply. It is instead
    swapped for the same short branded cut-off line the raised-exception
    branch already uses. This test originally only checked that the partial
    text was present and the refund fired — passing even while the raw
    sentinel prose (confirmed via manual `r.text` inspection: 'vllm' /
    'AMI error' / 'backend logs' all present) sailed straight through
    unchecked. Tightened to actually assert the leak is gone, matching what
    the test's own name always claimed."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 3)

    _real_vllm_gateway(_PartialThenSentinelTransport())

    user_id, headers = _new_user()
    session_id = _open_concierge(client, headers)

    r = _send(client, headers, session_id)
    assert r.status_code == 200, r.text
    assert "partial real " in r.text
    assert "content before " in r.text

    lower = r.text.lower()
    assert "vllm" not in lower
    assert "refused this request" not in lower
    assert "backend logs" not in lower
    assert "wasn't charged" in r.text, (
        "the mid-stream sentinel chunk must be swapped for the branded "
        "cut-off notice, not passed through raw"
    )

    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 1, (
        "stream_error must still be set structurally so the refund fires, "
        "even though the sentinel chunk arrived mid-stream"
    )


def test_partial_reply_then_raised_exception_appends_cutoff_notice(
    client, monkeypatch, _real_vllm_gateway,
):
    """DEF424 MINOR-2's shape (a RAISED exception, e.g. `httpx.ReadError`,
    partway through a real stream body), but for `_stream_concierge`
    specifically — its own `except Exception` handler predates DEF424
    (RETRO-SECURITY MAJOR-2 round 3) and was never exercised with a
    non-empty `buf`. Before this test, nothing pinned that the Concierge's
    `else` branch (added by this same DEF433 patch, copied from the
    non-Concierge fix) actually appends the cut-off notice rather than
    silently truncating the reply or leaking the raw `ReadError` text."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 3)

    _real_vllm_gateway(_PartialThenDropTransport())

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_concierge(client, headers)

    r = _send(client, headers, session_id)
    assert r.status_code == 200, r.text

    assert "partial real " in r.text
    assert "content before " in r.text
    assert "wasn't charged" in r.text.replace("\\'", "'")
    assert "ReadError" not in r.text
    assert "connection dropped" not in r.text.lower()

    assert balance_for(user_id)[0] == before, (
        "a Concierge turn cut off mid-stream by a transport error must "
        "net to zero credits"
    )
    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 1


def test_success_still_bills_normally(client, monkeypatch, _real_vllm_gateway):
    """Control — the structural `stream_error` detection must not turn a
    real, successful Concierge reply into a false refund."""
    from app.core import config as config_mod
    monkeypatch.setattr(config_mod.settings, "one_on_one_credit_cost", 3)

    _real_vllm_gateway(_ok_handler)

    user_id, headers = _new_user()
    before = balance_for(user_id)[0]
    session_id = _open_concierge(client, headers)

    r = _send(client, headers, session_id)
    assert r.status_code == 200, r.text
    assert "hello from the Concierge" in r.text
    assert balance_for(user_id)[0] == before - 3
    kinds = [e.event_type for e in _ledger(user_id)]
    assert kinds.count("credits_spent") == 1
    assert kinds.count("credits_refunded") == 0
