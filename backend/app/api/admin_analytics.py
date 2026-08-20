"""Admin analytics API — /v1/admin/analytics/* (CR200).

The live subset of the nightly CR051 report, for the console's ANALYTICS
tab. Persona segment counts are NOT here — the SPA calls the existing
CR181 endpoint (GET /v1/telemetry/segments) for those.

Endpoint map:
  GET /v1/admin/analytics/summary              User + DAU/WAU/MAU scalars
  GET /v1/admin/analytics/timeseries?days=30   Per-day signups / actives / rooms / credits
  GET /v1/admin/analytics/revenuecat?days=30   RevenueCat event counts + recent feed
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.admin import get_admin
from app.services import admin_analytics
from app.services.cf_access import AdminIdentity

router = APIRouter(
    prefix="/v1/admin/analytics",
    tags=["admin"],
    dependencies=[Depends(get_admin)],
)


@router.get("/summary")
def analytics_summary() -> dict[str, Any]:
    return admin_analytics.summary()


@router.get("/timeseries")
def analytics_timeseries(
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    return admin_analytics.timeseries(days=days)


@router.get("/revenuecat")
def analytics_revenuecat(
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    return admin_analytics.revenuecat(days=days)
