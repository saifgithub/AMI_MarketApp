"""Deprecated /v1/coach/* alias — use /v1/brief/* instead.

Coach Your Agent was renamed to Brief Your Agent in AT:R27. The Flutter
app on TestFlight `+17` was built against /v1/coach/*; this shim keeps
those routes alive through the deprecation window so old builds don't
break.

Every hit logs a `deprecated_coach_route_used` warning so we can confirm
no clients are still using the legacy path before removing the shim
(target: two TestFlight releases later).

Implementation: re-mount the BRIEF endpoints at /v1/coach with the same
handler functions. We re-create the router (rather than re-using the
brief_router instance) so the prefix is /v1/coach in the OpenAPI schema
and the deprecation log fires before the handler runs.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from uuid import UUID

from app.api.brief import (  # re-use the renamed handlers
    brief_accept,
    brief_history,
    brief_message,
    brief_propose,
    brief_reject,
    brief_rollback,
    brief_start,
)
from app.api.dependencies import get_current_user
from app.core.logging import logger
from app.db.models import User
from app.schemas import (
    AgentId,
    BriefHistoryResponse,
    BriefProposal,
    UserOverlay,
)
from app.schemas.brief import (
    BriefAcceptRequest,
    BriefMessageRequest,
    BriefProposeRequest,
    BriefRejectRequest,
    BriefRollbackRequest,
    BriefStartRequest,
    BriefStartResponse,
)
from app.services.brief_engine import BriefEngine, get_brief_engine
from app.services.overlay_store import OverlayStore, get_overlay_store


router = APIRouter(
    prefix="/v1/coach",
    tags=["coach (deprecated — use /v1/brief)"],
    dependencies=[Depends(get_current_user)],
)


async def _log_deprecation(request: Request) -> None:
    """Log every legacy /v1/coach/* hit so we can confirm cutover later."""
    logger.warning(
        "deprecated_coach_route_used",
        path=request.url.path,
        method=request.method,
    )


@router.post(
    "/start",
    response_model=BriefStartResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_log_deprecation)],
)
async def coach_start_legacy(
    req: BriefStartRequest,
    current_user: User = Depends(get_current_user),
    engine: BriefEngine = Depends(get_brief_engine),
) -> BriefStartResponse:
    return await brief_start(req, current_user, engine)


@router.post("/message", dependencies=[Depends(_log_deprecation)])
async def coach_message_legacy(
    req: BriefMessageRequest,
    current_user: User = Depends(get_current_user),
    engine: BriefEngine = Depends(get_brief_engine),
) -> StreamingResponse:
    return await brief_message(req, current_user, engine)


@router.post(
    "/propose",
    response_model=BriefProposal,
    dependencies=[Depends(_log_deprecation)],
)
async def coach_propose_legacy(
    req: BriefProposeRequest,
    current_user: User = Depends(get_current_user),
    engine: BriefEngine = Depends(get_brief_engine),
) -> BriefProposal:
    return await brief_propose(req, current_user, engine)


@router.post("/accept", dependencies=[Depends(_log_deprecation)])
async def coach_accept_legacy(
    req: BriefAcceptRequest,
    current_user: User = Depends(get_current_user),
    engine: BriefEngine = Depends(get_brief_engine),
) -> dict:
    return await brief_accept(req, current_user, engine)


@router.post("/reject", dependencies=[Depends(_log_deprecation)])
async def coach_reject_legacy(
    req: BriefRejectRequest,
    current_user: User = Depends(get_current_user),
    engine: BriefEngine = Depends(get_brief_engine),
) -> dict:
    return await brief_reject(req, current_user, engine)


@router.post(
    "/rollback",
    response_model=UserOverlay,
    dependencies=[Depends(_log_deprecation)],
)
async def coach_rollback_legacy(
    req: BriefRollbackRequest,
    current_user: User = Depends(get_current_user),
    store: OverlayStore = Depends(get_overlay_store),
) -> UserOverlay:
    return await brief_rollback(req, current_user, store)


@router.get(
    "/history/{user_id}/{agent_id}",
    response_model=BriefHistoryResponse,
    dependencies=[Depends(_log_deprecation)],
)
async def coach_history_legacy(
    user_id: UUID,
    agent_id: AgentId,
    plan: str = "trial_trader",
    current_user: User = Depends(get_current_user),
    store: OverlayStore = Depends(get_overlay_store),
) -> BriefHistoryResponse:
    return await brief_history(user_id, agent_id, plan, current_user, store)
