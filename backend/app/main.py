"""FastAPI entry point for the AMI Trade backend."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.api.admin import router as admin_router
from app.api.alpaca import router as alpaca_router
from app.api.ai_coach import router as ai_coach_router
from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.feedback import router as feedback_router
from app.api.brief import router as brief_router
from app.api.coach import router as coach_router  # deprecated /v1/coach/* shim
from app.api.daily_challenge import router as daily_challenge_router
from app.api.glossary import router as glossary_router
from app.api.journal import router as journal_router
from app.api.league import router as league_router
from app.api.lessons import router as lessons_router
from app.api.llm import router as llm_router
from app.api.mandate import router as mandate_router
from app.api.onboarding import router as onboarding_router
from app.api.one_on_one import router as one_on_one_router
from app.api.room import router as room_router
from app.api.sim import router as sim_router
from app.api.watchlist import router as watchlist_router
from app.api.webhooks import router as webhooks_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.observability import init_sentry
from app.core.logging import logger
from app.middleware.http_audit import HTTPAuditMiddleware
from app.services.audit import trim_audit_tables
from app.services.room_runner import get_room_runner

configure_logging()
# Sentry must initialise BEFORE the FastAPI app is constructed so the
# auto-enabling integrations can wrap Starlette / FastAPI. No-op when
# SENTRY_DSN is unset (dev).
init_sentry()

# Boot-time secret check — adversarial audit (2026-05-18) finding A1.
# Any env reachable from the public tunnel MUST set its own SECRET_KEY;
# the source-visible default would make HMAC signatures trivially forgeable.
if settings.env != "local" and settings.secret_key == "dev-secret-change-in-prod":
    raise RuntimeError(
        f"Refusing to start: env={settings.env} requires SECRET_KEY to be set "
        "to a non-default value (env file or environment variable). "
        "Generate one with: openssl rand -hex 32"
    )

_TRIM_INTERVAL_SECONDS = 24 * 60 * 60  # 24 h
_LEAGUE_ROLL_INTERVAL_SECONDS = 60 * 60  # hourly — weekly_roll() is idempotent
_SHARIA_REFRESH_INTERVAL_SECONDS = 24 * 60 * 60  # daily — SPUS publishes daily


async def _nightly_audit_trim() -> None:
    """Background task: trim audit tables every 24 h."""
    while True:
        await asyncio.sleep(_TRIM_INTERVAL_SECONDS)
        try:
            counts = trim_audit_tables()
            logger.info("audit_trim_complete", **counts)
        except Exception:
            logger.exception("audit_trim_failed")


async def _league_roll_tick() -> None:
    """Background task: hourly league roll (CR004). weekly_roll() no-ops
    within an already-assembled ISO week, so restarts can't miss the
    Monday 00:00 UTC boundary — the next tick catches up."""
    from app.db import get_session
    from app.services.league_service import get_league_service

    while True:
        try:
            with get_session() as s:
                get_league_service().weekly_roll(s)
        except Exception:
            logger.exception("league_roll_failed")
        await asyncio.sleep(_LEAGUE_ROLL_INTERVAL_SECONDS)


async def _sharia_universe_refresh() -> None:
    """Background task: fetch the sourced Sharia universe once a day and store a
    snapshot row (CR075). Idempotent like `_league_roll_tick` — a tick that finds
    a fresh stored row does nothing, so a restart can't miss a boundary. The
    network fetch happens HERE (the only socket this feature opens), off the
    request path and off the event loop (`to_thread`, since it does two ~15s httpx
    round-trips); the read path resolves from the stored row and never blocks."""
    from app.services.sharia_universe import run_sharia_refresh_tick

    while True:
        try:
            await asyncio.to_thread(run_sharia_refresh_tick)
        except Exception:
            logger.exception("sharia_universe_refresh_failed")
        await asyncio.sleep(_SHARIA_REFRESH_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # AT:R34 (eeeb866f): respawn any room runs the previous boot left
    # in status=running. The sweep itself ran in get_room_runner()'s
    # __init__ (claiming rows + bumping retry_count); this drains the
    # claimed list and spawns the retry background tasks now that we
    # have a live event loop.
    try:
        await get_room_runner().resume_pending_retries()
    except Exception:
        logger.exception("room_resume_pending_retries_failed")

    tasks = [
        asyncio.create_task(_nightly_audit_trim()),
        asyncio.create_task(_league_roll_tick()),
        asyncio.create_task(_sharia_universe_refresh()),
    ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
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
app.include_router(admin_router)
app.include_router(alpaca_router)
app.include_router(ai_coach_router)
app.include_router(auth_router)
app.include_router(billing_router)
app.include_router(onboarding_router)
app.include_router(one_on_one_router)
app.include_router(brief_router)
app.include_router(coach_router)  # legacy /v1/coach/* — deprecated AT:R27
app.include_router(daily_challenge_router)
app.include_router(glossary_router)
app.include_router(journal_router)
app.include_router(league_router)
app.include_router(lessons_router)
app.include_router(llm_router)
app.include_router(mandate_router)
app.include_router(room_router)
app.include_router(sim_router)
app.include_router(feedback_router)
app.include_router(watchlist_router)
app.include_router(webhooks_router)


@app.get("/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0", "env": settings.env}


# Admin back-office stop-gap UI (AT:R27). The page itself is public; every
# API call it makes is gated by the ADMIN_SECRET bearer. Will be replaced
# by a compiled Flutter web bundle in Beta — same URL, same API.
_ADMIN_HTML_PATH = Path(__file__).parent / "static" / "admin.html"


@app.get("/admin", include_in_schema=False, response_class=HTMLResponse)
async def admin_ui() -> HTMLResponse:
    return HTMLResponse(_ADMIN_HTML_PATH.read_text(encoding="utf-8"))
