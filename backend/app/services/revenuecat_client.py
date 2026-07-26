"""RevenueCat server-side REST client (DEF099) — customer-alias transfer.

When an anonymous user who has purchased then claims/links an existing account,
`MergeService` folds the orphan into the adopter and deletes the orphan `users`
row. But RevenueCat still knows the subscription under the orphan's UUID
(`app_user_id`), so its post-merge `RENEWAL` / `EXPIRATION` webhooks would arrive
for a now-deleted user. This module transfers the RC customer alias so future
webhooks carry the *adopter's* id.

Two independent safeguards close gap 3 of DEF099:

  1. **This RC-side call** re-points RC at the surviving account (best-effort,
     external I/O). It runs AFTER the DB merge commits, so a slow/failed RC call
     can never roll back the local entitlement carry.
  2. **A backend safety net** in the webhook (`app/api/webhooks.py::_load_user`)
     follows the merge audit trail orphan→adopter, so even a webhook that still
     arrives under the old id (RC alias not yet propagated, or an in-flight
     event) resolves to the adopter instead of a 404.

Degrade LOUDLY (CR040): an unconfigured secret key is logged as an error and
returns `not_configured` — it never silently reports success (which would leave
the operator believing RC was re-targeted when it was not) and never makes a
network call, so offline unit tests stay hermetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx

from app.core.config import settings
from app.core.logging import logger

_RC_API_BASE = "https://api.revenuecat.com/v1"
_TIMEOUT = httpx.Timeout(10.0)

AliasStatus = Literal["ok", "not_configured", "failed"]


@dataclass
class AliasTransferResult:
    status: AliasStatus
    detail: str | None = None


def transfer_alias(from_app_user_id: str, to_app_user_id: str) -> AliasTransferResult:
    """Re-alias an RC customer from the orphan id to the adopter id.

    Uses RC's server-side alias endpoint
    (`POST /v1/subscribers/{app_user_id}/alias`, Bearer = RC *secret* API key),
    which associates the two ids so the subscription follows the surviving
    account. Best-effort: never raises — the caller has already committed the
    authoritative local merge and relies on the webhook safety net if this
    fails.
    """
    secret = settings.revenuecat_secret_api_key
    if not secret:
        # CR040: a missing key must be a LOUD refusal, not a silent "ok". The
        # local merge still stands; the webhook safety net re-targets deliveries.
        logger.error(
            "revenuecat_alias_secret_unset",
            from_app_user_id=from_app_user_id,
            to_app_user_id=to_app_user_id,
        )
        return AliasTransferResult(
            status="not_configured",
            detail="REVENUECAT_SECRET_API_KEY unset — RC alias not transferred",
        )

    url = f"{_RC_API_BASE}/subscribers/{from_app_user_id}/alias"
    try:
        resp = httpx.post(
            url,
            json={"new_app_user_id": to_app_user_id},
            headers={
                "Authorization": f"Bearer {secret}",
                "Content-Type": "application/json",
            },
            timeout=_TIMEOUT,
        )
    except httpx.RequestError as exc:
        logger.error(
            "revenuecat_alias_transfer_error",
            from_app_user_id=from_app_user_id,
            to_app_user_id=to_app_user_id,
            error=str(exc),
        )
        return AliasTransferResult(status="failed", detail=str(exc))

    if resp.status_code >= 400:
        logger.error(
            "revenuecat_alias_transfer_rejected",
            from_app_user_id=from_app_user_id,
            to_app_user_id=to_app_user_id,
            status_code=resp.status_code,
            body=resp.text[:500],
        )
        return AliasTransferResult(status="failed", detail=f"rc {resp.status_code}")

    logger.info(
        "revenuecat_alias_transferred",
        from_app_user_id=from_app_user_id,
        to_app_user_id=to_app_user_id,
    )
    return AliasTransferResult(status="ok")
