"""RevenueCat webhook endpoint (CR084) — the server-authoritative grant path.

`POST /v1/webhooks/revenuecat` is how a real in-app purchase becomes an
entitlement. RevenueCat validates the store receipt and POSTs an event here;
the backend — never the client — is the authority on what a user owns
(structural, per CR038: an instruction to "trust only verified purchases" is
not a control; this signature check + the store-authoritative webhook is).

Hard rules this file enforces (money + entitlements = D-5):
  * Fail CLOSED. A bad/absent `Authorization` header -> 401, never a grant.
  * Degrade LOUDLY (CR040). An unset shared secret -> 503 + logged error; the
    webhook never silent-accepts (would grant on an unverified call) and never
    silent-rejects-all (would masquerade as an RC misconfiguration).
  * Idempotent. RC retries any non-2xx, so a replayed INITIAL_PURCHASE must not
    double-grant. Dedup is a DB UNIQUE constraint on RC's event id, inserted
    first inside the grant transaction (DEF039: not a SELECT-then-INSERT race).
  * Single ledger. Credit/plan changes go THROUGH credit_service's allowance
    mechanism; every transition writes ONE subscription_events row
    (source="revenuecat", note=<rc event id>).

RC `app_user_id` MUST equal our `users.id` (UUID) — the mobile SDK logs in with
the id served by GET /v1/billing/identity (app/api/billing.py).
"""

from __future__ import annotations

import hmac
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.logging import logger
from app.db import get_session
from app.db.models import RevenueCatEventRow, SubscriptionEventRow, User, _utcnow
from app.schemas.mandate import Plan
from app.services import credit_service


router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


# ── CR084 product catalog (docs/.../CR084_revenuecat_integration.md) ──────────
#
# Subscriptions are keyed off the RC *entitlement* (stable, few) — not the store
# product id. Credit packs are keyed off *product_id* (they are consumables, not
# entitlements). These are the canonical keys from the spec; if the store-side
# product ids differ they are mapped to these in the RC dashboard offering, or
# updated here.
_ENTITLEMENT_TO_PLAN: dict[str, Plan] = {
    "trader": Plan.TRADER,
    "floor_manager": Plan.FLOOR_MANAGER,
}

_CREDIT_PACKS: dict[str, int] = {
    "credits_starter": 60,
    "credits_standard": 300,
    "credits_power": 850,
}

_SUBSCRIPTION_TYPES = {"INITIAL_PURCHASE", "RENEWAL", "PRODUCT_CHANGE"}
_REVOKE_TYPES = {"CANCELLATION", "EXPIRATION", "BILLING_ISSUE"}
_CREDIT_PACK_TYPE = "NON_RENEWING_PURCHASE"


class WebhookAck(BaseModel):
    status: str
    detail: str | None = None


# ── Signature ─────────────────────────────────────────────────────────────────

def _verify_secret(authorization: str | None) -> None:
    """Fail closed + degrade loudly. RC sends the configured secret verbatim as
    the Authorization header value (RC's documented webhook auth model)."""
    secret = settings.revenuecat_webhook_secret
    if not secret:
        # CR040: an unconfigured secret must be a LOUD refusal — not a silent
        # accept (grant on an unverified call) and not a silent reject-all
        # (looks like RC broke). 503 + an error log surfaces the missing config.
        logger.error("revenuecat_webhook_secret_unset")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "revenuecat webhook not configured — set REVENUECAT_WEBHOOK_SECRET",
        )
    presented = (authorization or "").encode()
    if not hmac.compare_digest(presented, secret.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid webhook signature")


# ── Mapping helpers (raise LOUDLY on an unmappable purchase) ──────────────────

def _entitlement_plan(event: dict[str, Any]) -> Plan:
    candidates: list[str] = []
    ids = event.get("entitlement_ids")
    if isinstance(ids, list):
        candidates.extend(str(x) for x in ids)
    single = event.get("entitlement_id")
    if single:
        candidates.append(str(single))

    plans = [_ENTITLEMENT_TO_PLAN[c] for c in candidates if c in _ENTITLEMENT_TO_PLAN]
    if plans:
        # Highest tier wins when several entitlements are present.
        return max(plans, key=lambda p: credit_service.ALLOWANCE[p])

    # Fallback: infer from the product id (trader_* / floor_manager_*).
    product_id = str(event.get("product_id") or "")
    if product_id.startswith("floor_manager"):
        return Plan.FLOOR_MANAGER
    if product_id.startswith("trader"):
        return Plan.TRADER

    # A subscription purchase we cannot map = the user paid and would get
    # nothing. Refuse loudly (422) so RC surfaces a failed delivery and the
    # operator fixes the offering/entitlement config, rather than a silent
    # no-op grant (CR040).
    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        f"no known entitlement/product mapping (entitlements={candidates}, "
        f"product={product_id!r})",
    )


def _pack_credits(product_id: Any) -> int:
    key = str(product_id or "")
    if key in _CREDIT_PACKS:
        return _CREDIT_PACKS[key]
    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        f"unknown credit pack product {key!r}",
    )


def _load_user(session, app_user_id: Any) -> User:
    if not app_user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "event missing app_user_id")
    try:
        uid = UUID(str(app_user_id))
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"app_user_id is not a valid uuid: {app_user_id!r}",
        ) from exc
    user = session.get(User, uid)
    if user is None:
        # RC references a user we don't have — possibly deleted by an
        # anon->claimed merge (see the MergeService gap in the CR084 hand-off).
        # Loud 404 so the delivery shows as failed in the RC dashboard instead
        # of silently dropping a paid purchase.
        logger.error("revenuecat_webhook_unknown_user", app_user_id=str(app_user_id))
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"no user for app_user_id {app_user_id}"
        )
    return user


def _record_rc_event(
    session,
    *,
    user_id: UUID,
    event_type: str,
    from_value: str | None,
    to_value: str | None,
    note: str,
) -> None:
    """The single authoritative transition row for this RC event."""
    session.add(SubscriptionEventRow(
        id=uuid4(),
        user_id=user_id,
        event_type=event_type,
        from_value=from_value,
        to_value=to_value,
        source="revenuecat",
        note=note,
        created_at=_utcnow(),
    ))


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/revenuecat", response_model=WebhookAck)
def revenuecat_webhook(
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
) -> WebhookAck:
    _verify_secret(authorization)

    event = payload.get("event")
    if not isinstance(event, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "missing event object")
    rc_event_id = event.get("id")
    event_type = event.get("type")
    if not rc_event_id or not event_type:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "event missing id or type")
    rc_event_id = str(rc_event_id)
    event_type = str(event_type)

    app_user_id = event.get("app_user_id")
    product_id = event.get("product_id")

    is_actionable = (
        event_type in _SUBSCRIPTION_TYPES
        or event_type in _REVOKE_TYPES
        or event_type == _CREDIT_PACK_TYPE
    )

    # One transaction: dedup insert + grant + audit row commit (or roll back)
    # together, so a failed delivery leaves no dedup trace and RC's retry can
    # still succeed; only a fully-processed event is ever seen as a duplicate.
    with get_session() as s:
        s.add(RevenueCatEventRow(
            id=uuid4(),
            event_id=rc_event_id,
            event_type=event_type,
            app_user_id=str(app_user_id) if app_user_id else None,
            product_id=str(product_id) if product_id else None,
            received_at=_utcnow(),
        ))
        try:
            s.flush()  # forces the INSERT; UNIQUE(event_id) violation raises here
        except IntegrityError:
            s.rollback()
            logger.info(
                "revenuecat_webhook_duplicate",
                event_id=rc_event_id, event_type=event_type,
            )
            return WebhookAck(status="duplicate", detail="event already processed")

        if not is_actionable:
            # Benign RC event type we don't act on (TEST, TRANSFER,
            # UNCANCELLATION, SUBSCRIPTION_PAUSED, ...). Record dedup + 200 so
            # RC stops retrying; touch no money.
            logger.info(
                "revenuecat_webhook_ignored",
                event_id=rc_event_id, event_type=event_type,
            )
            return WebhookAck(status="ignored", detail=f"event type {event_type} not actioned")

        user = _load_user(s, app_user_id)

        if event_type in _SUBSCRIPTION_TYPES:
            target_plan = _entitlement_plan(event)
            grant = credit_service.set_plan_and_grant_allowance(s, user, target_plan)
            _record_rc_event(
                s,
                user_id=user.id,
                event_type="plan_changed",
                from_value=grant.old_plan,
                to_value=grant.new_plan,
                note=rc_event_id,
            )
            logger.info(
                "revenuecat_subscription_grant",
                event_id=rc_event_id, event_type=event_type,
                user_id=str(user.id), plan=target_plan.value,
                credits=grant.new_balance, regranted=grant.granted,
            )
            return WebhookAck(status="ok", detail=f"plan={target_plan.value}")

        if event_type == _CREDIT_PACK_TYPE:
            credits = _pack_credits(product_id)
            old_balance, new_balance = credit_service.add_credit_pack(s, user, credits)
            _record_rc_event(
                s,
                user_id=user.id,
                event_type="credits_added",
                from_value=str(old_balance),
                to_value=str(new_balance),
                note=rc_event_id,
            )
            logger.info(
                "revenuecat_credit_pack_grant",
                event_id=rc_event_id, user_id=str(user.id),
                product=str(product_id), credits=credits, balance=new_balance,
            )
            return WebhookAck(status="ok", detail=f"credits+{credits}")

        # Revoke (CANCELLATION / EXPIRATION / BILLING_ISSUE)
        old_plan, eff = credit_service.revoke_to_base(s, user)
        _record_rc_event(
            s,
            user_id=user.id,
            event_type="plan_changed",
            from_value=old_plan,
            to_value=eff.value,
            note=rc_event_id,
        )
        logger.info(
            "revenuecat_revoke",
            event_id=rc_event_id, event_type=event_type,
            user_id=str(user.id), from_plan=old_plan, effective_plan=eff.value,
        )
        return WebhookAck(status="ok", detail=f"revoked -> {eff.value}")
