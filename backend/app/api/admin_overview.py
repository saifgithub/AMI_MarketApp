"""Admin system overview — GET /v1/admin/overview (CR200).

One server-side aggregation of every "is the stack healthy" question the
console's HEALTH tab asks, so the SPA makes one call instead of fanning out
to /v1/ready, /v1/llm/status, /v1/llm/cache_rate, config-check and a bug
count. Every block degrades independently to {"error": …} — a dead Redis
must not blank the LLM card, and the endpoint itself never 500s over a
probe (CR040: the failure is IN the payload, loudly, not swallowed).
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.admin import _settings_coverage, get_admin
from app.core.config import settings
from app.db import get_session
from app.db.models import BugReportRow
from app.services.cf_access import AdminIdentity

router = APIRouter(prefix="/v1/admin", tags=["admin"])


def _block(fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return fn()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def _ready_block() -> dict[str, Any]:
    from app.services.readiness import readiness_report
    return readiness_report()


def _llm_block() -> dict[str, Any]:
    from app.services.llm_gateway import get_llm_gateway
    return dict(get_llm_gateway().status())


def _llm_cache_block() -> dict[str, Any]:
    from app.services.vllm_metrics import windowed_rate
    w = windowed_rate(limit=2)
    return {
        "status": w.status,
        "rate": w.rate,
        "queries_delta": w.queries_delta,
        "hits_delta": w.hits_delta,
    }


def _release_floor_block() -> dict[str, Any]:
    from app.services.client_release_floor import get_active_floor
    with get_session() as s:
        floor = get_active_floor(s)
    if floor is None:
        return {"configured": False}
    return {
        "configured": True,
        "min_build": floor.min_build,
        "recommended_build": floor.recommended_build,
    }


def _bugs_block() -> dict[str, Any]:
    with get_session() as s:
        counts = {
            st: n for st, n in s.execute(
                select(BugReportRow.status, func.count())
                .group_by(BugReportRow.status)
            )
        }
    return {"open": counts.get("open", 0), "counts": counts}


def _config_block() -> dict[str, Any]:
    coverage = _settings_coverage()
    return {
        "settings_total": len(coverage),
        "unset_count": sum(1 for c in coverage if not c.configured),
        "unset_annotated": [
            c.setting for c in coverage if c.annotated and not c.configured
        ],
    }


@router.get("/overview")
def admin_overview(_: AdminIdentity = Depends(get_admin)) -> dict[str, Any]:
    return {
        "ready": _block(_ready_block),
        "build": {
            "git_sha": settings.git_sha,
            "alpha_tag": settings.alpha_tag,
            "env": settings.env,
        },
        "llm": _block(_llm_block),
        "llm_cache": _block(_llm_cache_block),
        "release_floor": _block(_release_floor_block),
        "market_data": {"real": bool(settings.use_real_market_data)},
        "bugs": _block(_bugs_block),
        "config": _block(_config_block),
    }
