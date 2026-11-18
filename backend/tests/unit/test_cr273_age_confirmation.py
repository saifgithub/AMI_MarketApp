"""CR273 (CR267 WP-31, D-084) — the 18+ confirmation in onboarding.

The control is server-side: a client that never shows the confirmation screen
is still refused. What is stored is a timestamp (`age_confirmed_at`); no
birth-date or age field exists anywhere.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from uuid import UUID

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import router as auth_router
from app.api.onboarding import router as onboarding_router
from app.core.time import now_utc
from app.db import get_session
from app.db.models import Base, User
from app.schemas.onboarding import ConversationStep, OnboardingSession
from app.services.auth_service import AuthService
from app.services.session_store import get_session_store

_BACKEND = Path(__file__).resolve().parents[2]
_MIGRATION = _BACKEND / "alembic" / "versions" / "cr273a0b0c0d1_users_age_confirmed_at.py"


@pytest.fixture
def client() -> TestClient:
    a = FastAPI()
    a.include_router(auth_router)
    a.include_router(onboarding_router)
    return TestClient(a)


def _start(client: TestClient, **body) -> dict:
    r = client.post(
        "/v1/onboarding/start", json={"locale": "en", "timezone": "UTC", **body}
    )
    assert r.status_code == 201, r.text
    return r.json()


def _readback_session(**overrides) -> OnboardingSession:
    defaults = dict(
        current_step=ConversationStep.READBACK,
        answers={
            "primary_goal": "retirement",
            "horizon": "very_long",
            "path": "long_horizon",
            "max_drawdown_pct": 20,
            "compliance": {
                "halal": True,
                "esg_lite": False,
                "no_tobacco_alcohol_gambling": True,
                "no_fossil_fuels": False,
                "long_only": True,
                "liquid_only": True,
                "ticker_blocklist": [],
                "ticker_allowlist": None,
                "custom_constraints": [],
            },
        },
        risk_components_partial={
            "drawdown_response": 3,
            "regret_asymmetry": -1,
            "concentration_tolerance": 1,
        },
    )
    defaults.update(overrides)
    return OnboardingSession(**defaults)


# ── the gate ─────────────────────────────────────────────────────────────────


def test_a_session_is_not_age_confirmed_unless_the_client_says_so(client):
    body = _start(client)
    stored = asyncio.run(get_session_store().get(UUID(body["session_id"])))
    assert stored is not None
    assert stored.age_confirmed_at is None

    explicit_false = _start(client, age_confirmed=False)
    stored = asyncio.run(get_session_store().get(UUID(explicit_false["session_id"])))
    assert stored.age_confirmed_at is None


def test_answer_without_confirmation_is_refused_with_a_typed_403(client):
    body = _start(client)
    r = client.post(
        "/v1/onboarding/answer",
        json={
            "session_id": body["session_id"],
            "step": body["first_question"]["step"],
            "answer": "grow my savings",
        },
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["code"] == "age_confirmation_required"


def test_completion_without_confirmation_is_refused_and_does_not_complete(client):
    session = _readback_session()
    asyncio.run(get_session_store().create(session))

    r = client.post(
        "/v1/onboarding/readback/confirm",
        json={"session_id": str(session.id), "confirm": "confirm"},
    )

    assert r.status_code == 403, r.text
    assert r.json()["detail"]["code"] == "age_confirmation_required"
    stored = asyncio.run(get_session_store().get(session.id))
    assert stored.completed is False
    assert stored.current_step == ConversationStep.READBACK.value


def test_a_confirmed_session_walks_to_completion_and_stores_a_timestamp(client):
    before = now_utc()
    body = _start(client, age_confirmed=True)
    sid = body["session_id"]
    stored = asyncio.run(get_session_store().get(UUID(sid)))
    assert stored.age_confirmed_at is not None
    assert stored.age_confirmed_at >= before

    stored.current_step = ConversationStep.READBACK
    stored.answers = _readback_session().answers
    stored.risk_components_partial = _readback_session().risk_components_partial
    asyncio.run(get_session_store().save(stored))

    r = client.post(
        "/v1/onboarding/readback/confirm",
        json={"session_id": sid, "confirm": "confirm"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["completed"] is True


def test_confirmation_is_copied_onto_the_signed_in_users_row(client):
    u, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    session = _readback_session(age_confirmed_at=now_utc())
    asyncio.run(get_session_store().create(session))

    r = client.post(
        "/v1/onboarding/readback/confirm",
        json={"session_id": str(session.id), "confirm": "confirm"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text

    with get_session() as s:
        row = s.get(User, u.id)
        assert row.age_confirmed_at is not None


def test_a_user_with_no_confirmation_has_a_null_timestamp():
    u, _, _ = AuthService().ensure_anonymous(device_user_id=None)
    with get_session() as s:
        assert s.get(User, u.id).age_confirmed_at is None


def test_the_existing_stamp_is_never_overwritten():
    from app.services import age_confirmation

    u, _, _ = AuthService().ensure_anonymous(device_user_id=None)
    first = now_utc()
    age_confirmation.stamp_user(u.id, first)
    age_confirmation.stamp_user(u.id, now_utc())
    with get_session() as s:
        assert s.get(User, u.id).age_confirmed_at.replace(tzinfo=None) == first.replace(
            tzinfo=None
        )


# ── nothing but a timestamp is stored ────────────────────────────────────────


def test_no_birth_date_or_age_field_exists_anywhere():
    banned = ("birth", "dob", "date_of_birth", "age_years", "birthday")
    for table in Base.metadata.tables.values():
        for col in table.columns:
            name = col.name.lower()
            assert not any(b in name for b in banned), f"{table.name}.{col.name}"
    for model in (OnboardingSession,):
        for name in model.model_fields:
            assert not any(b in name.lower() for b in banned), name


# ── migration ────────────────────────────────────────────────────────────────


def _load_migration():
    spec = importlib.util.spec_from_file_location("cr273_mig", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_migration_upgrades_and_downgrades_on_sqlite(tmp_path):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    mod = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'mig.db'}")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE users (id VARCHAR PRIMARY KEY, email VARCHAR)"))
        ops = Operations(MigrationContext.configure(conn))
        with Operations.context(ops.migration_context):
            mod.upgrade()
        cols = {c["name"]: c for c in sa.inspect(conn).get_columns("users")}
        assert "age_confirmed_at" in cols
        assert cols["age_confirmed_at"]["nullable"] is True
        with Operations.context(ops.migration_context):
            mod.downgrade()
        assert "age_confirmed_at" not in {
            c["name"] for c in sa.inspect(conn).get_columns("users")
        }


def test_single_alembic_head_and_this_migration_is_in_its_chain():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1, heads
    chain = {r.revision for r in script.walk_revisions(base="base", head=heads[0])}
    assert "cr273a0b0c0d1" in chain
