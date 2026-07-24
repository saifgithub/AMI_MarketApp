"""CR084 — RevenueCat webhook: server-authoritative entitlement/credit grants.

This is a money + entitlements path (D-5): a wrong grant is real dollars and a
real trust breach. These tests pin the behaviour that makes it safe:

  1. Fail CLOSED on signature — an unsigned / wrong-secret call is refused and
     grants nothing (proved RED first: no secret configured -> loud 503).
  2. Idempotent — RC retries on any non-2xx, so a replayed event id must grant
     exactly once, never twice.
  3. Each event -> grant mapping (sub tiers, credit packs, revoke) is correct
     and writes a `subscription_events` audit row (source="revenuecat").
  4. The trial double-grant guard holds (an active trial already granted this
     period's 150 credits; converting to paid trader must not hand a second).
  5. Unmappable purchases and unknown users fail LOUDLY (422 / 404), never a
     silent no-op grant (CR040).
  6. REVENUECAT_WEBHOOK_SECRET is forwarded in docker-compose (DEF038/DEF063).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.billing import router as billing_router
from app.api.webhooks import router as webhooks_router
from app.core.config import settings
from app.db import get_session
from app.db.models import RevenueCatEventRow, SubscriptionEventRow, User
from app.schemas.mandate import Plan
from app.services.auth_service import AuthService
from app.services.credit_service import ALLOWANCE, balance_for
from app.services.entitlements import effective_plan_for_user


SECRET = "rc-test-secret-value"


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(webhooks_router)
    a.include_router(billing_router)
    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def secret(monkeypatch) -> str:
    monkeypatch.setattr(settings, "revenuecat_webhook_secret", SECRET)
    return SECRET


def _new_user(plan: str = "floor_pass") -> tuple[UUID, str]:
    auth = AuthService()
    u, t, _ = auth.ensure_anonymous(device_user_id=None)
    if plan != "floor_pass":
        with get_session() as s:
            s.get(User, u.id).plan = plan
    return u.id, t


def _event(
    event_type: str,
    app_user_id,
    *,
    event_id: str | None = None,
    product_id: str | None = None,
    entitlement_ids: list[str] | None = None,
) -> dict:
    ev: dict = {
        "id": event_id or str(uuid4()),
        "type": event_type,
        "app_user_id": str(app_user_id),
    }
    if product_id is not None:
        ev["product_id"] = product_id
    if entitlement_ids is not None:
        ev["entitlement_ids"] = entitlement_ids
    return {"api_version": "1.0", "event": ev}


def _auth(secret_value: str = SECRET) -> dict:
    # RC sends the configured secret verbatim as the Authorization header value.
    return {"Authorization": secret_value}


def _read_user(user_id: UUID) -> tuple[str, int]:
    with get_session() as s:
        u = s.get(User, user_id)
        return u.plan, u.credit_balance


def _rc_rows(user_id: UUID) -> list[SubscriptionEventRow]:
    with get_session() as s:
        return list(s.execute(
            select(SubscriptionEventRow)
            .where(
                SubscriptionEventRow.user_id == user_id,
                SubscriptionEventRow.source == "revenuecat",
            )
            .order_by(SubscriptionEventRow.created_at)
        ).scalars())


def _dedup_count() -> int:
    with get_session() as s:
        return len(list(s.execute(select(RevenueCatEventRow)).scalars()))


def _set_balance_period(user_id: UUID, *, balance: int) -> None:
    """Force a balance without changing the (already-stamped) period/plan_at_grant."""
    with get_session() as s:
        s.get(User, user_id).credit_balance = balance


# ── 1. Signature: fail closed + degrade loudly ────────────────────────────────

def test_unset_secret_refuses_loudly_with_503(client, monkeypatch):
    """RED-first: with no secret configured the webhook must refuse LOUDLY
    (503), never silent-accept and never silent-reject-all (CR040)."""
    monkeypatch.setattr(settings, "revenuecat_webhook_secret", "")
    user_id, _ = _new_user()
    resp = client.post(
        "/v1/webhooks/revenuecat",
        json=_event("INITIAL_PURCHASE", user_id, entitlement_ids=["trader"]),
        headers=_auth("anything"),
    )
    assert resp.status_code == 503
    # Nothing granted, nothing recorded.
    assert _read_user(user_id) == ("floor_pass", 0)
    assert _dedup_count() == 0


def test_missing_authorization_is_401_and_grants_nothing(client, secret):
    user_id, _ = _new_user()
    resp = client.post(
        "/v1/webhooks/revenuecat",
        json=_event("INITIAL_PURCHASE", user_id, entitlement_ids=["trader"]),
    )
    assert resp.status_code == 401
    assert _read_user(user_id) == ("floor_pass", 0)
    assert _dedup_count() == 0


def test_wrong_secret_is_401_and_grants_nothing(client, secret):
    user_id, _ = _new_user()
    resp = client.post(
        "/v1/webhooks/revenuecat",
        json=_event("INITIAL_PURCHASE", user_id, entitlement_ids=["trader"]),
        headers=_auth("not-the-secret"),
    )
    assert resp.status_code == 401
    assert _read_user(user_id) == ("floor_pass", 0)
    assert _dedup_count() == 0


# ── 2. Idempotency — replay grants exactly once ───────────────────────────────

def test_replayed_initial_purchase_does_not_double_grant(client, secret):
    user_id, _ = _new_user()
    event_id = "evt-fixed-123"
    payload = _event(
        "INITIAL_PURCHASE", user_id, event_id=event_id, entitlement_ids=["trader"],
    )

    first = client.post("/v1/webhooks/revenuecat", json=payload, headers=_auth())
    assert first.status_code == 200
    assert first.json()["status"] == "ok"
    assert _read_user(user_id) == ("trader", ALLOWANCE[Plan.TRADER])

    second = client.post("/v1/webhooks/revenuecat", json=payload, headers=_auth())
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"

    # Still granted exactly once; one dedup row; one revenuecat audit row.
    assert _read_user(user_id) == ("trader", ALLOWANCE[Plan.TRADER])
    assert _dedup_count() == 1
    assert len(_rc_rows(user_id)) == 1


def test_replayed_credit_pack_adds_credits_once(client, secret):
    user_id, _ = _new_user()
    event_id = "pack-evt-1"
    payload = _event(
        "NON_RENEWING_PURCHASE", user_id, event_id=event_id, product_id="credits_standard",
    )
    baseline = ALLOWANCE[Plan.FLOOR_PASS] + 300  # 13 monthly grant + 300 pack

    client.post("/v1/webhooks/revenuecat", json=payload, headers=_auth())
    client.post("/v1/webhooks/revenuecat", json=payload, headers=_auth())

    plan, balance = _read_user(user_id)
    assert plan == "floor_pass"        # packs never change plan
    assert balance == baseline         # added once, not twice
    assert _dedup_count() == 1


# ── 3. Event -> grant mapping ─────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("entitlement", "expected_plan", "expected_credits"),
    [
        ("trader", "trader", ALLOWANCE[Plan.TRADER]),
        ("floor_manager", "floor_manager", ALLOWANCE[Plan.FLOOR_MANAGER]),
    ],
)
def test_subscription_sets_plan_and_grants_allowance(
    client, secret, entitlement, expected_plan, expected_credits,
):
    user_id, _ = _new_user()
    resp = client.post(
        "/v1/webhooks/revenuecat",
        json=_event("INITIAL_PURCHASE", user_id, entitlement_ids=[entitlement]),
        headers=_auth(),
    )
    assert resp.status_code == 200
    plan, balance = _read_user(user_id)
    assert plan == expected_plan
    assert balance == expected_credits

    rows = _rc_rows(user_id)
    assert len(rows) == 1
    assert rows[0].event_type == "plan_changed"
    assert rows[0].from_value == "floor_pass"
    assert rows[0].to_value == expected_plan
    assert rows[0].source == "revenuecat"


@pytest.mark.parametrize(
    ("product", "credits"),
    [("credits_starter", 60), ("credits_standard", 300), ("credits_power", 850)],
)
def test_credit_pack_adds_credits_no_plan_change(client, secret, product, credits):
    user_id, _ = _new_user()
    resp = client.post(
        "/v1/webhooks/revenuecat",
        json=_event("NON_RENEWING_PURCHASE", user_id, product_id=product),
        headers=_auth(),
    )
    assert resp.status_code == 200
    plan, balance = _read_user(user_id)
    assert plan == "floor_pass"
    assert balance == ALLOWANCE[Plan.FLOOR_PASS] + credits

    rows = _rc_rows(user_id)
    assert len(rows) == 1
    assert rows[0].event_type == "credits_added"
    assert rows[0].source == "revenuecat"


@pytest.mark.parametrize("revoke_type", ["CANCELLATION", "EXPIRATION", "BILLING_ISSUE"])
def test_revoke_drops_effective_plan_to_floor_pass(client, secret, revoke_type):
    user_id, _ = _new_user(plan="trader")
    _set_balance_period(user_id, balance=ALLOWANCE[Plan.TRADER])

    resp = client.post(
        "/v1/webhooks/revenuecat",
        json=_event(revoke_type, user_id, product_id="trader_monthly"),
        headers=_auth(),
    )
    assert resp.status_code == 200
    assert effective_plan_for_user(user_id) == Plan.FLOOR_PASS
    plan, balance = _read_user(user_id)
    assert plan == "floor_pass"
    assert balance == ALLOWANCE[Plan.FLOOR_PASS]  # downgrade cliff re-grant

    rows = _rc_rows(user_id)
    assert rows[-1].event_type == "plan_changed"
    assert rows[-1].to_value == "floor_pass"
    assert rows[-1].source == "revenuecat"


def test_revoke_falls_back_to_trial_when_trial_active(client, secret):
    """EXPIRATION with a still-active trial resolves to trial_trader via
    effective_plan, not floor_pass."""
    user_id, _ = _new_user(plan="trader")
    with get_session() as s:
        u = s.get(User, user_id)
        u.trial_expires_at = datetime.now(timezone.utc) + timedelta(days=3)
    balance_for(user_id)  # grant the current period under the effective plan

    resp = client.post(
        "/v1/webhooks/revenuecat",
        json=_event("EXPIRATION", user_id, product_id="trader_monthly"),
        headers=_auth(),
    )
    assert resp.status_code == 200
    assert effective_plan_for_user(user_id) == Plan.TRIAL_TRADER
    assert _rc_rows(user_id)[-1].to_value == "trial_trader"


# ── 4. Trial double-grant guard ───────────────────────────────────────────────

def test_active_trial_conversion_does_not_regrant_same_period(client, secret):
    """An active trial already granted this period's 150 credits; converting to
    paid trader (also 150) must NOT reset a spent-down balance."""
    user_id, _ = _new_user(plan="trial_trader")
    with get_session() as s:
        s.get(User, user_id).trial_expires_at = datetime.now(timezone.utc) + timedelta(days=5)
    balance_for(user_id)                 # grants 150 for this period (trial_trader)
    _set_balance_period(user_id, balance=100)  # simulate 50 credits already spent

    resp = client.post(
        "/v1/webhooks/revenuecat",
        json=_event("INITIAL_PURCHASE", user_id, entitlement_ids=["trader"]),
        headers=_auth(),
    )
    assert resp.status_code == 200
    plan, balance = _read_user(user_id)
    assert plan == "trader"
    assert balance == 100  # NOT re-granted to a fresh 150


def test_upgrade_trader_to_floor_manager_tops_up_allowance(client, secret):
    """A same-period PRODUCT_CHANGE to a higher tier grants the higher
    allowance (500 > 150)."""
    user_id, _ = _new_user()
    client.post(
        "/v1/webhooks/revenuecat",
        json=_event("INITIAL_PURCHASE", user_id, entitlement_ids=["trader"]),
        headers=_auth(),
    )
    assert _read_user(user_id) == ("trader", ALLOWANCE[Plan.TRADER])

    client.post(
        "/v1/webhooks/revenuecat",
        json=_event("PRODUCT_CHANGE", user_id, entitlement_ids=["floor_manager"]),
        headers=_auth(),
    )
    assert _read_user(user_id) == ("floor_manager", ALLOWANCE[Plan.FLOOR_MANAGER])


# ── 5. Loud failures on unmappable purchase / unknown user ────────────────────

def test_unknown_user_is_404_and_rolls_back_dedup(client, secret):
    ghost = uuid4()
    resp = client.post(
        "/v1/webhooks/revenuecat",
        json=_event("INITIAL_PURCHASE", ghost, entitlement_ids=["trader"]),
        headers=_auth(),
    )
    assert resp.status_code == 404
    # Dedup row rolled back so a retry after the user exists can still succeed.
    assert _dedup_count() == 0


def test_unknown_credit_pack_is_422(client, secret):
    user_id, _ = _new_user()
    resp = client.post(
        "/v1/webhooks/revenuecat",
        json=_event("NON_RENEWING_PURCHASE", user_id, product_id="credits_unlimited"),
        headers=_auth(),
    )
    assert resp.status_code == 422
    assert _read_user(user_id) == ("floor_pass", 0)
    assert _dedup_count() == 0


def test_unknown_entitlement_is_422(client, secret):
    user_id, _ = _new_user()
    resp = client.post(
        "/v1/webhooks/revenuecat",
        json=_event("INITIAL_PURCHASE", user_id, entitlement_ids=["platinum"]),
        headers=_auth(),
    )
    assert resp.status_code == 422
    assert _read_user(user_id) == ("floor_pass", 0)


def test_unactioned_event_type_is_ignored_noop(client, secret):
    user_id, _ = _new_user()
    resp = client.post(
        "/v1/webhooks/revenuecat",
        json=_event("TRANSFER", user_id),
        headers=_auth(),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
    assert _read_user(user_id) == ("floor_pass", 0)
    assert len(_rc_rows(user_id)) == 0
    assert _dedup_count() == 1  # recorded so RC stops retrying


# ── 6. Identity endpoint + compose parity ─────────────────────────────────────

def test_billing_identity_returns_user_id(client):
    user_id, token = _new_user()
    resp = client.get("/v1/billing/identity", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == str(user_id)
    assert body["app_user_id"] == str(user_id)


def test_billing_identity_requires_auth(client):
    resp = client.get("/v1/billing/identity")
    assert resp.status_code == 401


def test_revenuecat_secret_forwarded_in_compose():
    """DEF038/DEF063 regression, pinned by name: the webhook secret must reach
    the api-alpha container or the feature ships dark."""
    compose = (Path(__file__).resolve().parents[3] / "docker-compose.yml").read_text()
    assert "REVENUECAT_WEBHOOK_SECRET:" in compose
