"""Billing identity endpoint (CR084).

GET /v1/billing/identity — the id the mobile RevenueCat SDK must log in with
(`Purchases.logIn(app_user_id)`), so RC's `app_user_id` on every webhook event
equals our `users.id`. Without this the webhook (app/api/webhooks.py) cannot map
a purchase back to a user.

Kept as its own auth-gated route rather than folded into the mandate payload so
the SDK has a single, purpose-named call to make at startup; `app_user_id` is
returned as an explicit field (== `user_id`) so the contract is unambiguous even
though today they are the same value.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.db.models import User


router = APIRouter(prefix="/v1/billing", tags=["billing"])


class BillingIdentity(BaseModel):
    user_id: UUID
    # The value to pass to Purchases.logIn(...). Currently identical to
    # user_id; a distinct field keeps the RC linkage explicit and stable if the
    # two ever diverge (e.g. a hashed alias).
    app_user_id: str


@router.get("/identity", response_model=BillingIdentity)
def billing_identity(current_user: User = Depends(get_current_user)) -> BillingIdentity:
    return BillingIdentity(
        user_id=current_user.id,
        app_user_id=str(current_user.id),
    )
