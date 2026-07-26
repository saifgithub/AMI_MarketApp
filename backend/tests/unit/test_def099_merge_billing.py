"""DEF099 — account merge must carry RevenueCat / entitlement / credit state.

Anonymous-first is a LOCKED decision: a pre-claim anonymous user who pays must
keep what they paid for after they claim/link an existing account. Before this
fix `MergeService.execute()` re-keyed ~16 per-user tables orphan→adopter and
deleted the orphan, but dropped billing state — the purchase silently vanished.

These tests pin the three closed gaps:

  1. `subscription_events` + `revenuecat_events` are re-keyed orphan→adopter
     (the audit / dedup trail must not dangle after the orphan is deleted).
  2. `plan` / `credit_balance` / period fields are carried with the DELIBERATE
     conflict rule **higher-entitlement plan wins, credits sum** (asserted
     explicitly below).
  3. A post-merge `RENEWAL` webhook resolves to the adopter (merge-trail safety
     net), not a 404 — and the RC-side customer-alias transfer is invoked.

Regression guard: a claimed (non-anonymous) user's purchase is unaffected.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.webhooks import router as webhooks_router
from app.core.config import settings
from app.db import get_session
from app.db.models import (
    RevenueCatEventRow,
    SubscriptionEventRow,
    User,
)
from app.schemas.mandate import Plan
from app.services import credit_service, revenuecat_client
from app.services.auth_service import AuthService
from app.services.credit_service import ALLOWANCE, balance_for
from app.services.merge_service import MergeService

SECRET = "rc-test-secret-value"


# ── fixtures / helpers ────────────────────────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    a = FastAPI()
    a.include_router(webhooks_router)
    return TestClient(a)


@pytest.fixture
def secret(monkeypatch) -> str:
    monkeypatch.setattr(settings, "revenuecat_webhook_secret", SECRET)
    return SECRET


def _month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _make_orphan_and_adopter(
    *,
    orphan_plan: str,
    orphan_balance: int,
    adopter_plan: str = "floor_pass",
    adopter_balance: int = 0,
) -> tuple[User, User]:
    """orphan = pre-claim anon that purchased; adopter = the claimed account it
    is being folded into. Also seeds one subscription_events + one
    revenuecat_events row on the orphan so re-keying can be asserted."""
    auth = AuthService()
    orphan_au, _, _ = auth.ensure_anonymous(device_user_id=None)
    adopter_au, _, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        orphan = s.execute(select(User).where(User.id == orphan_au.id)).scalar_one()
        adopter = s.execute(select(User).where(User.id == adopter_au.id)).scalar_one()

        # Orphan mimics a completed RC purchase (what the webhook would have set).
        orphan.plan = orphan_plan
        orphan.credit_balance = orphan_balance
        orphan.credits_period_start = _month_start()
        orphan.credits_plan_at_grant = orphan_plan
        s.add(SubscriptionEventRow(
            id=uuid4(), user_id=orphan.id, event_type="plan_changed",
            from_value="floor_pass", to_value=orphan_plan, source="revenuecat",
            note="orphan-purchase",
        ))
        s.add(RevenueCatEventRow(
            id=uuid4(), event_id=f"evt-{uuid4()}", event_type="INITIAL_PURCHASE",
            app_user_id=str(orphan.id), product_id="trader_monthly",
        ))

        # Adopter is a real claimed account.
        adopter.email = "adopter@example.com"
        adopter.is_anonymous = False
        adopter.claimed_at = datetime.now(timezone.utc)
        adopter.plan = adopter_plan
        adopter.credit_balance = adopter_balance
        if adopter_plan != "floor_pass":
            adopter.credits_period_start = _month_start()
            adopter.credits_plan_at_grant = adopter_plan
        return orphan, adopter


def _read(user_id: UUID) -> User:
    with get_session() as s:
        return s.get(User, user_id)


# ── gap 1+2: entitlement + credit carry with the explicit conflict rule ───────


def test_trader_orphan_into_floor_pass_adopter_carries_plan_and_sums_credits():
    """The headline case: anon buys trader (150 credits), claims a floor_pass
    account holding 13. Rule = higher plan wins + credits sum → trader / 163."""
    orphan, adopter = _make_orphan_and_adopter(
        orphan_plan="trader", orphan_balance=ALLOWANCE[Plan.TRADER],  # 150
        adopter_plan="floor_pass", adopter_balance=ALLOWANCE[Plan.FLOOR_PASS],  # 13
    )
    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)

    a = _read(adopter.id)
    assert a.plan == "trader"                                   # higher entitlement wins
    assert a.credit_balance == ALLOWANCE[Plan.TRADER] + ALLOWANCE[Plan.FLOOR_PASS]  # 163, summed
    assert a.credits_plan_at_grant == "trader"                 # period re-stamped

    # The carry survives the next allowance read — it must NOT be wiped by a
    # spurious drift re-grant back down to a single plan's allowance.
    assert balance_for(adopter.id)[0] == 163

    # Explicit billing audit row records the rule + inputs.
    with get_session() as s:
        row = s.execute(
            select(SubscriptionEventRow).where(
                SubscriptionEventRow.event_type == "account_merge_billing"
            )
        ).scalar_one()
        assert row.user_id == adopter.id
        assert row.from_value == "floor_pass"
        assert row.to_value == "trader"
        assert "higher_plan+sum_credits" in (row.note or "")


def test_adopter_higher_plan_is_kept_never_downgraded():
    """Adopter already floor_manager, orphan only trader → adopter stays
    floor_manager (never downgrade the surviving account); credits still sum."""
    orphan, adopter = _make_orphan_and_adopter(
        orphan_plan="trader", orphan_balance=ALLOWANCE[Plan.TRADER],       # 150
        adopter_plan="floor_manager", adopter_balance=ALLOWANCE[Plan.FLOOR_MANAGER],  # 500
    )
    _, _, _ = MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)

    a = _read(adopter.id)
    assert a.plan == "floor_manager"
    assert a.credit_balance == ALLOWANCE[Plan.FLOOR_MANAGER] + ALLOWANCE[Plan.TRADER]  # 650
    assert a.credits_plan_at_grant == "floor_manager"


def test_subscription_and_revenuecat_events_rekeyed_to_adopter():
    """gap 1: the audit + dedup trail must follow the surviving account, not
    dangle after the orphan row is deleted."""
    orphan, adopter = _make_orphan_and_adopter(
        orphan_plan="trader", orphan_balance=ALLOWANCE[Plan.TRADER],
    )
    counts, _, _ = MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)

    assert counts["subscription_events"] >= 1
    assert counts["revenuecat_events"] == 1

    with get_session() as s:
        # Nothing left keyed to the (deleted) orphan.
        assert s.execute(
            select(SubscriptionEventRow).where(SubscriptionEventRow.user_id == orphan.id)
        ).scalars().all() == []
        assert s.execute(
            select(RevenueCatEventRow).where(RevenueCatEventRow.app_user_id == str(orphan.id))
        ).scalars().all() == []
        # The orphan's purchase row now belongs to the adopter.
        rc = s.execute(
            select(RevenueCatEventRow).where(RevenueCatEventRow.app_user_id == str(adopter.id))
        ).scalars().all()
        assert len(rc) == 1


# ── gap 3: post-merge webhook resolves to the adopter (not a 404) ─────────────


def _event(event_type: str, app_user_id, *, entitlement_ids=None) -> dict:
    ev: dict = {"id": str(uuid4()), "type": event_type, "app_user_id": str(app_user_id)}
    if entitlement_ids is not None:
        ev["entitlement_ids"] = entitlement_ids
    return {"api_version": "1.0", "event": ev}


def test_renewal_after_merge_resolves_to_adopter_not_404(client, secret, monkeypatch):
    """A RENEWAL that still carries the deleted orphan id lands on the adopter
    via the merge-trail safety net — the paid subscription is not stranded."""
    monkeypatch.setattr(settings, "revenuecat_secret_api_key", "")  # alias half offline
    orphan, adopter = _make_orphan_and_adopter(
        orphan_plan="trader", orphan_balance=ALLOWANCE[Plan.TRADER],
    )
    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)

    resp = client.post(
        "/v1/webhooks/revenuecat",
        json=_event("RENEWAL", orphan.id, entitlement_ids=["trader"]),
        headers={"Authorization": SECRET},
    )
    assert resp.status_code == 200  # NOT 404

    with get_session() as s:
        # The RENEWAL's authoritative transition row landed on the adopter.
        row = s.execute(
            select(SubscriptionEventRow).where(
                SubscriptionEventRow.user_id == adopter.id,
                SubscriptionEventRow.source == "revenuecat",
                SubscriptionEventRow.event_type == "plan_changed",
            ).order_by(SubscriptionEventRow.created_at.desc())
        ).scalars().first()
        assert row is not None
        assert row.to_value == "trader"


def test_renewal_for_genuinely_unknown_user_still_404(client, secret):
    """Regression: a random id with no merge trail must still fail LOUDLY."""
    resp = client.post(
        "/v1/webhooks/revenuecat",
        json=_event("RENEWAL", uuid4(), entitlement_ids=["trader"]),
        headers={"Authorization": SECRET},
    )
    assert resp.status_code == 404


def test_claimed_user_purchase_is_unaffected(client, secret):
    """Regression: a claimed (non-anonymous) user's purchase targets a stable
    id, hits no merge path, and grants normally."""
    auth = AuthService()
    u, _, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        row = s.get(User, u.id)
        row.is_anonymous = False
        row.email = "claimed@example.com"
        row.claimed_at = datetime.now(timezone.utc)

    resp = client.post(
        "/v1/webhooks/revenuecat",
        json=_event("INITIAL_PURCHASE", u.id, entitlement_ids=["trader"]),
        headers={"Authorization": SECRET},
    )
    assert resp.status_code == 200
    got = _read(u.id)
    assert got.plan == "trader"
    assert got.credit_balance == ALLOWANCE[Plan.TRADER]


# ── gap 3: RC-side customer-alias transfer call ───────────────────────────────


def test_merge_invokes_rc_alias_transfer(monkeypatch):
    """MergeService fires the RC alias transfer orphan→adopter after commit."""
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        revenuecat_client, "transfer_alias",
        lambda frm, to: calls.append((frm, to)) or revenuecat_client.AliasTransferResult("ok"),
    )
    orphan, adopter = _make_orphan_and_adopter(
        orphan_plan="trader", orphan_balance=ALLOWANCE[Plan.TRADER],
    )
    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)
    assert calls == [(str(orphan.id), str(adopter.id))]


def test_transfer_alias_unset_key_degrades_loudly_no_network(monkeypatch):
    """CR040: no RC secret → not_configured + no network call (never silent-ok)."""
    monkeypatch.setattr(settings, "revenuecat_secret_api_key", "")

    def _boom(*a, **k):  # network must never be touched when unconfigured
        raise AssertionError("httpx.post must not be called when RC key is unset")

    monkeypatch.setattr(revenuecat_client.httpx, "post", _boom)
    res = revenuecat_client.transfer_alias("orphan-id", "adopter-id")
    assert res.status == "not_configured"


def test_transfer_alias_posts_to_revenuecat(monkeypatch):
    """With a key set, the call hits RC's alias endpoint with the right body +
    bearer auth."""
    monkeypatch.setattr(settings, "revenuecat_secret_api_key", "sk_live_test")
    captured: dict = {}

    def _fake_post(url, *, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return SimpleNamespace(status_code=200, text="")

    monkeypatch.setattr(revenuecat_client.httpx, "post", _fake_post)
    res = revenuecat_client.transfer_alias("orphan-id", "adopter-id")

    assert res.status == "ok"
    assert captured["url"].endswith("/subscribers/orphan-id/alias")
    assert captured["json"] == {"new_app_user_id": "adopter-id"}
    assert captured["headers"]["Authorization"] == "Bearer sk_live_test"


def test_transfer_alias_rc_rejection_is_failed_not_raised(monkeypatch):
    monkeypatch.setattr(settings, "revenuecat_secret_api_key", "sk_live_test")
    monkeypatch.setattr(
        revenuecat_client.httpx, "post",
        lambda *a, **k: SimpleNamespace(status_code=404, text="not found"),
    )
    res = revenuecat_client.transfer_alias("orphan-id", "adopter-id")
    assert res.status == "failed"


# ── compose parity pin (DEF038/DEF063 bug class) ──────────────────────────────


def test_revenuecat_secret_api_key_forwarded_in_compose():
    from pathlib import Path

    compose = (Path(__file__).resolve().parents[3] / "docker-compose.yml").read_text()
    assert "REVENUECAT_SECRET_API_KEY:" in compose
