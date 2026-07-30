"""DEF179 guard: `plan`/credit fields are not client-writable on the mandate.

Security review H1: `PATCH /v1/mandate/{user_id}` shallow-merged a raw
`dict[str, Any]` through the `Mandate` schema, so `{"plan":"floor_manager"}`
validated and persisted — DEF062's re-validation blocks wrong *types*, not
entitlement escalation. Two consumers then read the stored mandate's `plan`
directly instead of server-side `users.plan`:
  - the 1-on-1 agent-lock gate (`api/one_on_one.py`) — patching unlocked all
    12 agents free for a Floor Pass user.
  - Brief's edit-cap (`brief_engine.BriefEngine.accept`) — bypassed the Floor
    Pass 3-lifetime-edit cap.
A second vector needs no PATCH at all: `hydrate_brief_mandate` (called via
`resolve_mandate` when no mandate is stored yet) trusted the client's
`mandate_override` body's `plan` key directly.

Every assertion below is on the DOWNSTREAM CONSEQUENCE (still locked, cap
still enforced) rather than the stored field — testing the fix, not the code
that was just written for it.

Decision (pinned by `test_patch_silently_drops_entitlement_fields_returns_200`):
silent-drop, not reject. These fields are always re-stamped server-side on
read (`_with_plan_state`) regardless of what's stored, exactly like the five
other CR101-BE2 fields aren't — round-tripping a GET body back through PATCH
(a plausible legitimate client pattern, since GET echoes `plan`/`credit_balance`
on every Mandate) must not 400 just because it carries fields the client
never touched.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.auth import router as auth_router
from app.api.brief import router as brief_router
from app.api.mandate import router as mandate_router
from app.api.one_on_one import router as one_on_one_router
from app.db import get_session
from app.db.models import User as UserRow
from app.services.auth_service import AuthService
from app.services.brief_engine import get_brief_engine, hydrate_brief_mandate
from app.services.mandate_store import MandateStore, resolve_mandate
from app.services.overlay_store import get_overlay_store


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(mandate_router)
    app.include_router(one_on_one_router)
    app.include_router(brief_router)
    return TestClient(app, raise_server_exceptions=False)


def _new_user():
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


# ── Vector 1: PATCH /v1/mandate/{user_id} ───────────────────────────────────


def test_patch_silently_drops_entitlement_fields_returns_200(client: TestClient):
    user_id, headers = _new_user()
    resp = client.patch(
        f"/v1/mandate/{user_id}",
        json={"plan": "floor_manager", "credit_balance": 999999, "risk_score": 4},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # The non-entitlement field in the same PATCH still applies — confirms
    # the drop is field-scoped, not a whole-request rejection.
    assert body["risk_score"] == 4
    # plan/credit_balance are stamped from server truth on every read
    # regardless (CR039 `_with_plan_state`) — a Floor Pass user's real
    # allowance, never the attempted 999999.
    assert body["plan"] == "floor_pass"
    assert body["credit_balance"] != 999999


def test_patch_plan_does_not_persist_into_the_stored_mandate_row(client: TestClient):
    """Stronger than the read-path assertion above: the stored JSONB snapshot
    itself must not carry the attempted `plan` escalation, so a future
    consumer that reads the store directly (like the two DEF179 fixed
    below) is never exposed to it."""
    user_id, headers = _new_user()
    client.patch(
        f"/v1/mandate/{user_id}",
        json={"plan": "floor_manager"},
        headers=headers,
    )
    stored = MandateStore().get(user_id)
    assert stored is not None
    # The raw stored snapshot's default plan (`hydrate_brief_mandate`'s own
    # "trial_trader" default for a never-before-stored mandate) is orthogonal
    # to this assertion — the point is it is NOT "floor_manager".
    assert stored.plan != "floor_manager"


def test_patch_plan_leaves_agent_lock_engaged(client: TestClient):
    """Downstream consequence #1: after the PATCH, a locked (non-Concierge)
    agent must still 403 for a Floor Pass user — not merely "plan stored
    unchanged", but the actual gate a paywall bypass would defeat."""
    user_id, headers = _new_user()
    client.patch(f"/v1/mandate/{user_id}", json={"plan": "floor_manager"}, headers=headers)

    resp = client.post(
        "/v1/agents/one_on_one/start",
        json={"agent_id": "portfolio_manager", "locale": "en"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason"] == "agent_locked"


def test_patch_plan_leaves_brief_edit_cap_at_three(client: TestClient):
    """Downstream consequence #2: Brief's edit-cap must still bind at 3 for a
    Floor Pass user after a PATCH attempts `plan: floor_manager`."""
    user_id, headers = _new_user()
    client.patch(f"/v1/mandate/{user_id}", json={"plan": "floor_manager"}, headers=headers)

    get_overlay_store().clear()
    engine = get_brief_engine()
    mandate = resolve_mandate(user_id, None)
    # The enforcement point is `effective_plan_for_user` (real `users.plan`,
    # untouched by the PATCH), not this mandate's own `plan` field — assert
    # only that the PATCH didn't get its escalation into the stored snapshot.
    assert mandate.plan != "floor_manager"

    from app.schemas import AgentId
    from app.schemas.brief import BriefMode

    for i in range(3):
        session, _, _ = engine.open_session(
            user_id=user_id, agent_id=AgentId.BEAR_RESEARCHER, mode=BriefMode.FROM_SCRATCH,
            mandate=mandate,
        )
        import asyncio

        from app.schemas.one_on_one import ChatMsg

        proposal = asyncio.run(
            engine.propose(session=session, history=[ChatMsg(role="user", content=f"edit {i}")])
        )
        result = engine.accept(session=session, proposal_id=proposal.id)
        assert result.__class__.__name__ == "UserOverlay", result

    session, _, _ = engine.open_session(
        user_id=user_id, agent_id=AgentId.BEAR_RESEARCHER, mode=BriefMode.FROM_SCRATCH,
        mandate=mandate,
    )
    import asyncio

    from app.schemas.one_on_one import ChatMsg

    proposal = asyncio.run(
        engine.propose(session=session, history=[ChatMsg(role="user", content="edit 4")])
    )
    result = engine.accept(session=session, proposal_id=proposal.id)
    assert result.__class__.__name__ == "BriefRefusal"
    assert result.reason == "edit_limit_reached"


# ── Vector 2: mandate_override, no PATCH at all ─────────────────────────────


def test_resolve_mandate_ignores_client_plan_override_for_new_user():
    """`hydrate_brief_mandate` itself stays a trusted constructor (tests and
    `MandateStore.get_or_default` call it directly with legitimate `plan`
    values) — the untrusted boundary is `resolve_mandate`'s `override` param,
    which is where `req.mandate_override` actually lands."""
    mandate = resolve_mandate(uuid4(), {"plan": "floor_manager"})
    assert mandate.plan != "floor_manager"


def test_one_on_one_start_mandate_override_cannot_unlock_agent(client: TestClient):
    """A brand-new user with no stored mandate hits the `hydrate_brief_mandate`
    fallback in `resolve_mandate`. Passing `mandate_override: {"plan":
    "floor_manager"}` must not unlock a paid agent — `effective_plan_for_user`
    (server truth: this user is Floor Pass) gates it, not the override."""
    user_id, headers = _new_user()
    resp = client.post(
        "/v1/agents/one_on_one/start",
        json={
            "agent_id": "portfolio_manager",
            "locale": "en",
            "mandate_override": {"plan": "floor_manager"},
        },
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason"] == "agent_locked"


def test_one_on_one_start_concierge_still_free_regardless_of_plan(client: TestClient):
    """Concierge stays free even with a bogus override — confirms the fix
    didn't accidentally start gating the one agent that must never be gated."""
    user_id, headers = _new_user()
    resp = client.post(
        "/v1/agents/one_on_one/start",
        json={
            "agent_id": "concierge",
            "locale": "en",
            "mandate_override": {"plan": "floor_manager"},
        },
        headers=headers,
    )
    assert resp.status_code == 201


# ── Consumers now read `users.plan`, not `mandate.plan` ─────────────────────


def test_one_on_one_gate_reads_effective_plan_not_stored_mandate(client: TestClient):
    """A user genuinely upgraded via `users.plan` (not the mandate) unlocks
    correctly — proves the gate now reads the right source, not just that it
    ignores the wrong one."""
    user_id, headers = _new_user()
    with get_session() as s:
        row = s.execute(select(UserRow).where(UserRow.id == user_id)).scalar_one()
        row.plan = "floor_manager"

    resp = client.post(
        "/v1/agents/one_on_one/start",
        json={"agent_id": "portfolio_manager", "locale": "en"},
        headers=headers,
    )
    assert resp.status_code == 201


def test_brief_accept_reads_effective_plan_not_stored_mandate(client: TestClient):
    """Mirror of the above for Brief's edit-cap: a genuinely-upgraded user
    (via `users.plan`) gets unlimited edits even though the SESSION's own
    mandate snapshot (`session.mandate_used`, exactly what the old
    `_plan_from_mandate(mandate)` read) says `floor_pass` — the pre-fix code
    would have capped this user at 3 edits despite their real DB plan."""
    user_id, headers = _new_user()
    with get_session() as s:
        row = s.execute(select(UserRow).where(UserRow.id == user_id)).scalar_one()
        row.plan = "trader"

    get_overlay_store().clear()
    engine = get_brief_engine()
    mandate = hydrate_brief_mandate({"plan": "floor_pass"})
    assert mandate.plan == "floor_pass"

    from app.schemas import AgentId
    from app.schemas.brief import BriefMode

    for i in range(5):
        session, _, _ = engine.open_session(
            user_id=user_id, agent_id=AgentId.BEAR_RESEARCHER, mode=BriefMode.FROM_SCRATCH,
            mandate=mandate,
        )
        import asyncio

        from app.schemas.one_on_one import ChatMsg

        proposal = asyncio.run(
            engine.propose(session=session, history=[ChatMsg(role="user", content=f"edit {i}")])
        )
        result = engine.accept(session=session, proposal_id=proposal.id)
        assert result.__class__.__name__ == "UserOverlay", result
