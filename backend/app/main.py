"""FastAPI entry point for the AMI Trade backend."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ai_coach import router as ai_coach_router
from app.api.auth import router as auth_router
from app.api.feedback import router as feedback_router
from app.api.coach import router as coach_router
from app.api.daily_challenge import router as daily_challenge_router
from app.api.glossary import router as glossary_router
from app.api.journal import router as journal_router
from app.api.lessons import router as lessons_router
from app.api.llm import router as llm_router
from app.api.mandate import router as mandate_router
from app.api.onboarding import router as onboarding_router
from app.api.one_on_one import router as one_on_one_router
from app.api.room import router as room_router
from app.api.sim import router as sim_router
from app.api.watchlist import router as watchlist_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.observability import init_sentry
from app.middleware.http_audit import HTTPAuditMiddleware
from app.services.audit import trim_audit_tables

configure_logging()
# Sentry must initialise BEFORE the FastAPI app is constructed so the
# auto-enabling integrations can wrap Starlette / FastAPI. No-op when
# SENTRY_DSN is unset (dev).
init_sentry()

_TRIM_INTERVAL_SECONDS = 24 * 60 * 60  # 24 h


async def _nightly_audit_trim() -> None:
    """Background task: trim audit tables every 24 h."""
    while True:
        await asyncio.sleep(_TRIM_INTERVAL_SECONDS)
        try:
            counts = trim_audit_tables()
            logger.info("audit_trim_complete", **counts)
        except Exception:
            logger.exception("audit_trim_failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_nightly_audit_trim())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="AMI Trade API",
    version="0.1.0",
    description="Backend for AMI Trade — 12-agent trading-education app.",
    docs_url="/docs" if settings.env != "prod" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(HTTPAuditMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routers
app.include_router(ai_coach_router)
app.include_router(auth_router)
app.include_router(onboarding_router)
app.include_router(one_on_one_router)
app.include_router(coach_router)
app.include_router(daily_challenge_router)
app.include_router(glossary_router)
app.include_router(journal_router)
app.include_router(lessons_router)
app.include_router(llm_router)
app.include_router(mandate_router)
app.include_router(room_router)
app.include_router(sim_router)
app.include_router(feedback_router)
app.include_router(watchlist_router)


@app.get("/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0", "env": settings.env}
