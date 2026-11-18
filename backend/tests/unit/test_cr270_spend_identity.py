"""CR270 (CR267 WP-12) — served-model identity, cost, daily spend ceiling,
one Room per user.

What these pin, in the order a regression would hurt:

1. The migration adds `model` + `cost_usd` to `llm_audit`, downgrades cleanly,
   and the chain still has exactly one head.
2. `llm_audit.model` is the most specific id available: the `/v1/models` root
   (vLLM) > the response-reported model > the configured id. A failed
   `/v1/models` fetch breaks nothing.
3. Cost is computed from `LLM_PRICES_JSON` x tokens; an unknown price or unknown
   tokens store NULL (never 0) and the missing-price warning fires once.
4. The ceiling: None never refuses; under it proceeds; over it refuses NEW
   Room / 1-on-1 / Brief requests with the AMI message and no charge; a running
   Room is untouched; an unpriced row with tokens fails CLOSED; the UTC day
   boundary resets the sum; the sum is cached for 60 s.
5. One Room in flight per user across tickers, refused before the charge; the
   same ticker still attaches; an interrupted or stale row never blocks.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, select

from app.api.brief import router as brief_router
from app.api.one_on_one import router as one_on_one_router
from app.api.room import get_room_runner
from app.api.room import router as room_router
from app.core.config import Settings, parse_llm_prices
from app.db import get_session
from app.db.models import LLMAuditRow, RoomRunRow, SubscriptionEventRow
from app.services import llm_gateway as gw
from app.services import llm_spend
from app.services.auth_service import AuthService
from app.services.coach_engine import hydrate_coach_mandate
from app.services.credit_service import balance_for
from app.services.llm_gateway import ChatMessage, LLMGateway, VLLMProvider
from app.services.rate_limit import (
    agent_stream_concurrency_limit,
    brief_message_rate_limit,
    one_on_one_message_rate_limit,
)
from app.services.room_runner import (
    ROOM_IN_SESSION_MESSAGE,
    RoomAlreadyInSession,
    RoomRunner,
)

pytestmark = pytest.mark.allow_ledger_drift

_BACKEND = Path(__file__).resolve().parents[2]
_MIGRATION = _BACKEND / "alembic" / "versions" / "cr270a0b0c0d1_llm_audit_model_cost.py"


@pytest.fixture(autouse=True)
def _fresh_state():
    llm_spend.reset_state()
    brief_message_rate_limit.reset()
    one_on_one_message_rate_limit.reset()
    yield
    llm_spend.reset_state()


# ── 1. migration ─────────────────────────────────────────────────────────────


def _load_migration():
    spec = importlib.util.spec_from_file_location("cr270_mig", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_migration_upgrades_and_downgrades_on_sqlite(tmp_path):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    import sqlalchemy as sa

    mod = _load_migration()
    engine = create_engine(f"sqlite:///{tmp_path / 'mig.db'}")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE llm_audit (id VARCHAR PRIMARY KEY, provider VARCHAR)"))
        ops = Operations(MigrationContext.configure(conn))
        with Operations.context(ops.migration_context):
            mod.upgrade()
        cols = {c["name"] for c in inspect(conn).get_columns("llm_audit")}
        assert {"model", "cost_usd"} <= cols
        with Operations.context(ops.migration_context):
            mod.downgrade()
        cols = {c["name"] for c in inspect(conn).get_columns("llm_audit")}
        assert "model" not in cols and "cost_usd" not in cols


def test_single_alembic_head_and_this_migration_is_in_its_chain():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1, heads
    chain = {r.revision for r in script.walk_revisions(base="base", head=heads[0])}
    assert "cr270a0b0c0d1" in chain


# ── 2. model identity ────────────────────────────────────────────────────────


def _sse(model: str | None, text: str = "hi", usage: dict | None = None) -> list[str]:
    first: dict[str, Any] = {"choices": [{"delta": {"content": text}}]}
    if model is not None:
        first["model"] = model
    lines = ["data: " + json.dumps(first)]
    if usage is not None:
        lines.append("data: " + json.dumps({"choices": [], "usage": usage}))
    lines.append("data: [DONE]")
    return lines


class _Resp:
    def __init__(self, status: int = 200, lines: list[str] | None = None, body: bytes = b""):
        self.status_code = status
        self._lines = lines or []
        self._body = body

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self) -> bytes:
        return self._body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        return json.loads(self._body)


class _Client:
    """`stream()` replays a script of responses; `get()` answers /v1/models."""

    def __init__(self, stream_lines: list[str], models: _Resp | Exception | None = None):
        self._lines = stream_lines
        self._models = models

    @asynccontextmanager
    async def stream(self, method: str, url: str, json: dict):
        yield _Resp(200, self._lines)

    async def get(self, path: str, timeout: float | None = None):
        assert path == "/v1/models"
        if isinstance(self._models, Exception):
            raise self._models
        assert self._models is not None
        return self._models

    async def aclose(self) -> None:
        pass


def _models_payload(entries: list[dict]) -> _Resp:
    return _Resp(200, body=json.dumps({"object": "list", "data": entries}).encode())


def _gateway_with(provider: VLLMProvider) -> LLMGateway:
    g = LLMGateway()
    g._providers = {"mock": g._providers["mock"], "vllm": provider}
    return g


def _vllm(lines: list[str], models=None, *, kind="vllm", alias="ami-llm") -> VLLMProvider:
    p = VLLMProvider(base_url="http://x", model_name=alias, kind=kind, max_retries=0)
    p._client = _Client(lines, models)  # type: ignore[assignment]
    return p


async def _call(g: LLMGateway, flow: str = "t") -> str:
    out = []
    async for c in g.stream_chat(
        system_prompt="s", messages=[ChatMessage(role="user", content="q")],
        audit_flow=flow,
    ):
        out.append(c)
    return "".join(out)


def _last_row() -> LLMAuditRow:
    with get_session() as s:
        row = s.execute(
            select(LLMAuditRow).order_by(LLMAuditRow.created_at.desc()).limit(1)
        ).scalar_one()
        s.expunge(row)
        return row


def test_model_is_the_response_reported_one_on_a_hosted_slot():
    p = _vllm(_sse("Qwen/Qwen3-235B-A22B"), kind="openai", alias="configured-alias")
    asyncio.run(_call(_gateway_with(p)))
    assert _last_row().model == "Qwen/Qwen3-235B-A22B"


def test_model_falls_back_to_the_configured_id_when_nothing_else_is_known():
    p = _vllm(_sse(None), alias="configured-alias")
    asyncio.run(_call(_gateway_with(p)))
    assert _last_row().model == "configured-alias"


def test_vllm_root_from_v1_models_beats_the_alias_the_response_echoes():
    models = _models_payload(
        [{"id": "ami-llm", "root": "/models/qwen38-flash-next-abliterated-nvfp4"}]
    )
    p = _vllm(_sse("ami-llm"), models)
    g = _gateway_with(p)

    async def go():
        await g.discover_served_models()
        return await _call(g)

    asyncio.run(go())
    assert _last_row().model == "/models/qwen38-flash-next-abliterated-nvfp4"
    assert g.served_model("vllm") == "/models/qwen38-flash-next-abliterated-nvfp4"


def test_a_models_entry_without_root_uses_its_id():
    p = _vllm(_sse(None), _models_payload([{"id": "Qwen/Qwen3-X"}]), kind="openai", alias="Qwen/Qwen3-X")
    g = _gateway_with(p)
    asyncio.run(g.discover_served_models())
    assert g.served_model("vllm") == "Qwen/Qwen3-X"


def test_failed_models_fetch_never_raises_and_keeps_the_configured_id():
    p = _vllm(_sse(None), RuntimeError("connection refused"), alias="ami-llm")
    g = _gateway_with(p)
    asyncio.run(g.discover_served_models())
    assert p.served_root is None and p.served_id is None
    assert g.served_model("vllm") == "ami-llm"
    asyncio.run(_call(g))
    assert _last_row().model == "ami-llm"


def test_a_non_200_models_fetch_is_swallowed_too():
    p = _vllm(_sse(None), _Resp(500), alias="ami-llm")
    asyncio.run(_gateway_with(p).discover_served_models())
    assert p.served_root is None


def test_served_model_helper_defaults_to_the_active_provider(monkeypatch):
    p = _vllm(_sse(None), alias="ami-llm")
    g = _gateway_with(p)
    monkeypatch.setattr(gw, "_gateway", g)
    assert gw.served_model() == "ami-llm"
    assert gw.served_model("mock") == "mock"
    assert gw.served_model("nope") is None


# ── 3. cost ──────────────────────────────────────────────────────────────────


def _prices(monkeypatch, table: dict) -> None:
    monkeypatch.setattr(llm_spend.settings, "llm_prices_json", json.dumps(table))


def test_cost_is_tokens_times_price_per_million(monkeypatch):
    _prices(monkeypatch, {"m": {"in": 0.5, "out": 2.0}})
    assert llm_spend.compute_cost_usd(["m"], 2_000_000, 500_000) == pytest.approx(2.0)


def test_cost_tries_the_more_specific_key_first_then_the_alias(monkeypatch):
    _prices(monkeypatch, {"alias": {"in": 1.0, "out": 1.0}, "root": {"in": 3.0, "out": 3.0}})
    assert llm_spend.compute_cost_usd(["root", "alias"], 1_000_000, 0) == pytest.approx(3.0)
    assert llm_spend.compute_cost_usd(["unlisted", "alias"], 1_000_000, 0) == pytest.approx(1.0)


def test_unknown_price_is_none_not_zero_and_logs_once_per_model(monkeypatch):
    _prices(monkeypatch, {})
    seen: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        llm_spend.logger, "warning", lambda event, **kw: seen.append((event, kw))
    )
    assert llm_spend.compute_cost_usd(["mystery"], 10, 10) is None
    assert llm_spend.compute_cost_usd(["mystery"], 99, 99) is None
    assert llm_spend.compute_cost_usd(["other"], 10, 10) is None
    missing = [kw["model"] for ev, kw in seen if ev == "llm_price_missing"]
    assert missing == ["mystery", "other"]


def test_unknown_tokens_are_none_and_do_not_log_a_price_problem(monkeypatch):
    _prices(monkeypatch, {"m": {"in": 1.0, "out": 1.0}})
    seen: list[str] = []
    monkeypatch.setattr(llm_spend.logger, "warning", lambda event, **kw: seen.append(event))
    assert llm_spend.compute_cost_usd(["m"], None, 5) is None
    assert llm_spend.compute_cost_usd(["m"], 5, None) is None
    assert seen == []


def test_a_gateway_call_stores_cost_and_a_priced_zero_is_zero(monkeypatch):
    _prices(monkeypatch, {"/models/x": {"in": 1.0, "out": 4.0}})
    models = _models_payload([{"id": "ami-llm", "root": "/models/x"}])
    p = _vllm(_sse("ami-llm", usage={"prompt_tokens": 1_000_000, "completion_tokens": 250_000}), models)
    g = _gateway_with(p)

    async def go():
        await g.discover_served_models()
        await _call(g)

    asyncio.run(go())
    row = _last_row()
    assert row.model == "/models/x"
    assert float(row.cost_usd) == pytest.approx(2.0)


def test_a_gateway_call_with_an_unpriced_model_stores_null_cost(monkeypatch):
    _prices(monkeypatch, {})
    p = _vllm(_sse(None, usage={"prompt_tokens": 100, "completion_tokens": 50}))
    asyncio.run(_call(_gateway_with(p)))
    row = _last_row()
    assert row.input_tokens == 100 and row.cost_usd is None


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        '{"m": {"in": 1}}',
        '{"m": {"in": 1, "out": -0.1}}',
        '{"m": {"in": "1", "out": 1}}',
        '{"m": {"in": true, "out": 1}}',
        '{"m": {"in": 1, "out": 1, "cache": 2}}',
        '{"m": 3}',
    ],
)
def test_malformed_or_negative_prices_fail_boot(raw):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_prices_json=raw)


def test_valid_prices_including_free_boot_and_blank_means_empty():
    s = Settings(_env_file=None, llm_prices_json='{"a": {"in": 0, "out": 0.25}}')
    assert parse_llm_prices(s.llm_prices_json) == {"a": (0.0, 0.25)}
    assert parse_llm_prices("") == {}
    assert Settings(_env_file=None).llm_prices_json == "{}"


def test_ceiling_setting_defaults_to_none_blank_is_none_and_must_be_positive():
    assert Settings(_env_file=None).llm_daily_spend_ceiling_usd is None
    assert Settings(_env_file=None, llm_daily_spend_ceiling_usd="").llm_daily_spend_ceiling_usd is None
    assert Settings(_env_file=None, llm_daily_spend_ceiling_usd="5").llm_daily_spend_ceiling_usd == 5.0
    for bad in ("0", "-1", "nan", "inf"):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, llm_daily_spend_ceiling_usd=bad)


# ── 4. the ceiling ───────────────────────────────────────────────────────────

NOON = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def clock(monkeypatch):
    state = {"now": NOON, "mono": 1000.0}
    monkeypatch.setattr(llm_spend, "_utcnow", lambda: state["now"])
    monkeypatch.setattr(llm_spend, "_monotonic", lambda: state["mono"])
    return state


def _ceiling(monkeypatch, value: float | None) -> None:
    monkeypatch.setattr(llm_spend.settings, "llm_daily_spend_ceiling_usd", value)


def _audit(
    cost: float | None, *, at: datetime = NOON, tokens: bool = True, provider="vllm",
    model: str | None = "served-model",
) -> None:
    with get_session() as s:
        s.add(LLMAuditRow(
            created_at=at, tier="cheap", provider=provider, system_prompt="s",
            messages=[], input_tokens=10 if tokens else None,
            output_tokens=10 if tokens else None, cost_usd=cost, model=model,
        ))


def test_a_pre_cr270_row_without_a_model_does_not_close_the_gate(monkeypatch, clock):
    """DEF488: rows written before the migration have tokens, no model and no
    cost. On deploy day they closed the gate for every request until 00:00 UTC."""
    _ceiling(monkeypatch, 5.0)
    _audit(None, tokens=True, model=None)
    _audit(0.5)
    llm_spend.check_budget("t")
    assert llm_spend.todays_spend().unknown_cost_rows == 0


def test_no_ceiling_never_refuses_and_never_reads_the_db(monkeypatch, clock):
    _ceiling(monkeypatch, None)
    monkeypatch.setattr(llm_spend, "_read_spend", lambda _d: pytest.fail("read the DB"))
    _audit(10_000.0)
    llm_spend.check_budget("t")


def test_under_the_ceiling_proceeds(monkeypatch, clock):
    _ceiling(monkeypatch, 5.0)
    _audit(2.0)
    _audit(1.5, provider="vllm_fallback")
    llm_spend.check_budget("t")
    assert llm_spend.todays_spend().spend_usd == pytest.approx(3.5)


def test_at_or_over_the_ceiling_refuses_counting_primary_and_backup(monkeypatch, clock):
    _ceiling(monkeypatch, 5.0)
    _audit(3.0)
    _audit(2.0, provider="vllm_fallback")
    with pytest.raises(llm_spend.LLMBudgetExhausted) as exc:
        llm_spend.check_budget("t")
    assert exc.value.reason == "ceiling_reached"
    assert str(exc.value) == (
        "AMI is temporarily unavailable — today's model budget is used up. "
        "Please try again after 00:00 UTC."
    )


def test_an_unpriced_row_with_tokens_fails_closed_even_far_under_the_ceiling(monkeypatch, clock):
    _ceiling(monkeypatch, 1000.0)
    _audit(0.01)
    _audit(None, tokens=True)
    with pytest.raises(llm_spend.LLMBudgetExhausted) as exc:
        llm_spend.check_budget("t")
    assert exc.value.reason == "unknown_cost"


def test_a_row_with_no_tokens_and_no_cost_does_not_close_the_gate(monkeypatch, clock):
    _ceiling(monkeypatch, 5.0)
    _audit(None, tokens=False)
    llm_spend.check_budget("t")


def test_unreadable_spend_fails_closed(monkeypatch, clock):
    _ceiling(monkeypatch, 5.0)

    def boom(_d):
        raise RuntimeError("db down")

    monkeypatch.setattr(llm_spend, "_read_spend", boom)
    with pytest.raises(llm_spend.LLMBudgetExhausted) as exc:
        llm_spend.check_budget("t")
    assert exc.value.reason == "spend_unreadable"


def test_utc_day_boundary_resets_the_sum_without_waiting_for_the_cache(monkeypatch, clock):
    _ceiling(monkeypatch, 5.0)
    _audit(6.0, at=NOON)
    with pytest.raises(llm_spend.LLMBudgetExhausted):
        llm_spend.check_budget("t")
    clock["now"] = datetime(2026, 11, 19, 0, 0, 1, tzinfo=timezone.utc)
    clock["mono"] += 5  # well inside the 60 s TTL: only the day changed
    llm_spend.check_budget("t")
    assert llm_spend.todays_spend().spend_usd == 0.0


def test_yesterdays_late_spend_does_not_count_today(monkeypatch, clock):
    _ceiling(monkeypatch, 5.0)
    _audit(99.0, at=datetime(2026, 11, 17, 23, 59, tzinfo=timezone.utc))
    _audit(None, at=datetime(2026, 11, 17, 23, 59, tzinfo=timezone.utc))
    llm_spend.check_budget("t")


def test_the_sum_is_cached_for_60_seconds(monkeypatch, clock):
    _ceiling(monkeypatch, 5.0)
    calls = []
    real = llm_spend._read_spend

    def counting(day_start):
        calls.append(day_start)
        return real(day_start)

    monkeypatch.setattr(llm_spend, "_read_spend", counting)
    llm_spend.check_budget("t")
    _audit(50.0)  # spend lands after the first read
    clock["mono"] += 59
    llm_spend.check_budget("t")  # still cached: not yet refused
    assert len(calls) == 1
    clock["mono"] += 2
    with pytest.raises(llm_spend.LLMBudgetExhausted):
        llm_spend.check_budget("t")
    assert len(calls) == 2
    assert calls[0] == datetime(2026, 11, 18, 0, 0, tzinfo=timezone.utc)


def test_breach_alert_fires_once_per_utc_day_to_log_and_sentry(monkeypatch, clock):
    _ceiling(monkeypatch, 5.0)
    _audit(9.0)
    errors: list[str] = []
    monkeypatch.setattr(llm_spend.logger, "error", lambda event, **kw: errors.append(event))
    captured: list[str] = []
    fake = SimpleNamespace(capture_message=lambda msg, level=None: captured.append(msg))
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake)
    for _ in range(3):
        with pytest.raises(llm_spend.LLMBudgetExhausted):
            llm_spend.check_budget("t")
    assert errors == ["llm_spend_ceiling_breached"]
    assert len(captured) == 1
    # next UTC day, breached again -> one more
    clock["now"] = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
    _audit(9.0, at=clock["now"])
    with pytest.raises(llm_spend.LLMBudgetExhausted):
        llm_spend.check_budget("t")
    assert errors == ["llm_spend_ceiling_breached"] * 2
    assert len(captured) == 2


def test_refusal_http_shape_is_a_503_with_the_ami_message_and_retry_after(clock):
    exc = llm_spend.budget_http_exception()
    assert exc.status_code == 503
    assert exc.detail["code"] == "llm_budget_exhausted"
    assert exc.detail["message"] == llm_spend.BUDGET_MESSAGE
    assert exc.detail["retry_after_seconds"] == 12 * 3600
    assert exc.headers["Retry-After"] == str(12 * 3600)
    assert exc.detail["resets_at"].startswith("2026-11-19T00:00:00")


# route-level: new 1-on-1 / Brief requests are refused, with no charge and no leaked slot


def _new_user() -> tuple[UUID, dict]:
    user, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


def _ledger(user_id) -> list[SubscriptionEventRow]:
    with get_session() as s:
        return list(s.execute(
            select(SubscriptionEventRow).where(SubscriptionEventRow.user_id == user_id)
        ).scalars())


def _breach(monkeypatch) -> None:
    _ceiling(monkeypatch, 5.0)
    now = datetime.now(timezone.utc)
    _audit(50.0, at=now)


def test_one_on_one_is_refused_503_when_over_the_ceiling_with_no_charge(monkeypatch):
    c = TestClient(_app(one_on_one_router), raise_server_exceptions=False)
    user_id, headers = _new_user()
    sid = c.post("/v1/agents/one_on_one/start", json={"agent_id": "concierge"}, headers=headers).json()["id"]
    before = balance_for(user_id)[0]
    ok = c.post("/v1/agents/one_on_one/message", json={"session_id": sid, "user_message": "hi"}, headers=headers)
    assert ok.status_code == 200, "no ceiling: unchanged behaviour"
    mid = balance_for(user_id)[0]

    _breach(monkeypatch)
    r = c.post("/v1/agents/one_on_one/message", json={"session_id": sid, "user_message": "hi"}, headers=headers)
    assert r.status_code == 503, r.text
    assert r.json()["detail"]["message"] == llm_spend.BUDGET_MESSAGE
    assert r.headers["retry-after"]
    assert balance_for(user_id)[0] == mid, "a refused request is not charged"
    assert mid <= before
    # no leaked concurrency slot: the user can still acquire the full allowance
    key = f"user:{user_id}"
    agent_stream_concurrency_limit.acquire(key)
    agent_stream_concurrency_limit.release(key)


def test_brief_message_and_propose_are_refused_503_when_over_the_ceiling(monkeypatch):
    c = TestClient(_app(brief_router), raise_server_exceptions=False)
    user_id, headers = _new_user()
    sid = c.post(
        "/v1/brief/start", json={"agent_id": "concierge", "user_id": str(user_id)}, headers=headers
    ).json()["session"]["id"]
    before = balance_for(user_id)[0]
    n_ledger = len(_ledger(user_id))

    _breach(monkeypatch)
    for path, body in (
        ("/v1/brief/message", {"session_id": sid, "user_message": "hi"}),
        ("/v1/brief/propose", {"session_id": sid, "history": []}),
    ):
        r = c.post(path, json=body, headers=headers)
        assert r.status_code == 503, (path, r.text)
        assert r.json()["detail"]["code"] == "llm_budget_exhausted"
    assert balance_for(user_id)[0] == before
    assert len(_ledger(user_id)) == n_ledger


def _app(router) -> FastAPI:
    a = FastAPI()
    a.include_router(router)
    return a


def _mandate():
    return hydrate_coach_mandate({"plan": "trader", "risk_score": 3})


def _trader() -> UUID:
    from app.db.models import User

    user, _, _ = AuthService().ensure_anonymous(device_user_id=None)
    with get_session() as s:
        s.get(User, user.id).plan = "trader"
    return user.id


def test_new_room_is_refused_over_the_ceiling_with_no_charge_via_the_route(monkeypatch):
    a = _app(room_router)
    runner = RoomRunner()
    a.dependency_overrides[get_room_runner] = lambda: runner
    c = TestClient(a, raise_server_exceptions=False)
    user, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    headers = {"Authorization": f"Bearer {token}"}
    before = balance_for(user.id)[0]
    _breach(monkeypatch)
    r = c.post("/v1/room/stream", json={"user_id": str(user.id), "ticker": "AAPL"}, headers=headers)
    assert r.status_code == 503, r.text
    assert r.json()["detail"]["message"] == llm_spend.BUDGET_MESSAGE
    assert balance_for(user.id)[0] == before
    assert not [e for e in _ledger(user.id) if e.event_type == "credits_spent"]


def test_a_running_room_is_not_interrupted_and_an_attach_is_not_refused(monkeypatch):
    user_id = _trader()
    run_id = _running_row(user_id, "AAPL")
    _breach(monkeypatch)
    # in-flight Room calls go through the gateway, which never consults the ceiling
    p = _vllm(_sse(None), alias="ami-llm")
    assert asyncio.run(_call(_gateway_with(p))) == "hi"

    async def go():
        return await RoomRunner().start_run(
            user_id=user_id, ticker="AAPL", mandate=_mandate(),
            char_delay_min=0.0, char_delay_max=0.0,
        )

    assert asyncio.run(go()) == run_id, "tier-1 attach is free and precedes the gate"


# ── 5. one Room in flight per user ───────────────────────────────────────────


def _running_row(
    user_id: UUID, ticker: str, *, started_ago: timedelta = timedelta(minutes=1),
    interrupted: bool = False, status: str = "running",
) -> UUID:
    now = datetime.now(timezone.utc)
    run_id = uuid4()
    with get_session() as s:
        s.add(RoomRunRow(
            id=run_id, user_id=user_id, ticker=ticker, triggered_at=now - started_ago,
            started_at=now - started_ago, mandate_version=1, model_tier="cheap",
            status=status, interrupted_at=now if interrupted else None,
        ))
    return run_id


def _start(runner: RoomRunner, user_id: UUID, ticker: str):
    return runner.start_run(
        user_id=user_id, ticker=ticker, mandate=_mandate(),
        char_delay_min=0.0, char_delay_max=0.0,
    )


def test_a_running_room_on_another_ticker_refuses_before_the_charge():
    user_id = _trader()
    active = _running_row(user_id, "MSFT")
    before = balance_for(user_id)[0]

    async def go():
        with pytest.raises(RoomAlreadyInSession) as e:
            await _start(RoomRunner(), user_id, "AAPL")
        return e.value

    err = asyncio.run(go())
    assert str(err) == ROOM_IN_SESSION_MESSAGE == "You already have a Room in session. It will finish first."
    assert err.active_run_id == active and err.active_ticker == "MSFT"
    assert balance_for(user_id)[0] == before
    assert not [e for e in _ledger(user_id) if e.event_type == "credits_spent"]


def test_the_same_ticker_still_attaches_and_is_free():
    user_id = _trader()
    active = _running_row(user_id, "MSFT")
    before = balance_for(user_id)[0]
    assert asyncio.run(_start(RoomRunner(), user_id, "MSFT")) == active
    assert balance_for(user_id)[0] == before


def test_another_users_running_room_does_not_block():
    other = _trader()
    _running_row(other, "MSFT")
    me = _trader()
    runner = RoomRunner()

    async def run_it():
        rid = await _start(runner, me, "AAPL")
        async for _ in runner.subscribe(rid):
            pass
        return rid

    assert asyncio.run(run_it())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"interrupted": True},
        {"started_ago": timedelta(minutes=45)},
        {"status": "completed"},
        {"status": "failed"},
    ],
    ids=["interrupted", "stale", "completed", "failed"],
)
def test_interrupted_stale_or_finished_rows_do_not_block(kwargs):
    user_id = _trader()
    # Built BEFORE the row exists: the constructor's startup sweep would
    # otherwise claim an interrupted/stale row and queue it for retry, which
    # makes it a genuinely running Room again (and that one should block).
    runner = RoomRunner()
    _running_row(user_id, "MSFT", **kwargs)

    async def go():
        rid = await _start(runner, user_id, "AAPL")
        async for _ in runner.subscribe(rid):
            pass
        return rid

    assert asyncio.run(go())


def test_an_in_memory_run_on_another_ticker_blocks_before_its_first_insert():
    user_id = _trader()
    runner = RoomRunner()
    runner._active_by_key[(user_id, "MSFT")] = uuid4()

    async def go():
        with pytest.raises(RoomAlreadyInSession):
            await _start(runner, user_id, "AAPL")

    asyncio.run(go())


def test_the_route_returns_409_with_the_message_and_the_active_run(monkeypatch):
    a = _app(room_router)
    runner = RoomRunner()
    a.dependency_overrides[get_room_runner] = lambda: runner
    c = TestClient(a, raise_server_exceptions=False)
    user, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    headers = {"Authorization": f"Bearer {token}"}
    active = _running_row(user.id, "MSFT")
    before = balance_for(user.id)[0]
    r = c.post("/v1/room/stream", json={"user_id": str(user.id), "ticker": "AAPL"}, headers=headers)
    assert r.status_code == 409, r.text
    d = r.json()["detail"]
    assert d == {
        "code": "room_in_session",
        "message": "You already have a Room in session. It will finish first.",
        "active_run_id": str(active),
        "active_ticker": "MSFT",
    }
    assert balance_for(user.id)[0] == before
