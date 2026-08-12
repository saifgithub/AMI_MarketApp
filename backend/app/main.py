"""FastAPI entry point for the AMI Trade backend."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.api.admin import router as admin_router
from app.api.alpaca import router as alpaca_router
from app.api.backtest_admin import router as backtest_admin_router
from app.api.ai_coach import router as ai_coach_router
from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.feedback import router as feedback_router
from app.api.brief import router as brief_router
from app.api.coach import router as coach_router  # deprecated /v1/coach/* shim
from app.api.daily_challenge import router as daily_challenge_router
from app.api.games import router as games_router  # CR109 slice 2 — dark-launched
from app.api.glossary import router as glossary_router
from app.api.journal import router as journal_router
from app.api.league import router as league_router
from app.api.lessons import router as lessons_router
from app.api.llm import router as llm_router
from app.api.mandate import router as mandate_router
from app.api.onboarding import router as onboarding_router
from app.api.one_on_one import router as one_on_one_router
from app.api.portfolio import router as portfolio_router  # CR026 sector allocation
from app.api.price_alerts import router as price_alerts_router
from app.api.room import router as room_router
from app.api.sim import router as sim_router
from app.api.tickers import router as tickers_router
from app.api.watchlist import router as watchlist_router
from app.api.webhooks import router as webhooks_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.observability import init_sentry
from app.core.logging import logger
from app.db import get_session
from app.middleware.http_audit import HTTPAuditMiddleware
from app.middleware.version_gate import VersionGateMiddleware
from app.schemas.client_release_floor import ReleaseFloorResponse
from app.services.audit import trim_audit_tables
from app.services.client_release_floor import build_release_floor_response
from app.services.room_runner import get_room_runner

configure_logging()
# Sentry must initialise BEFORE the FastAPI app is constructed so the
# auto-enabling integrations can wrap Starlette / FastAPI. No-op when
# SENTRY_DSN is unset (dev).
init_sentry()

def check_secret_key_boot(env: str, secret_key: str) -> None:
    """Boot-time secret check — adversarial audit (2026-05-18) finding A1.

    Any env reachable from the public tunnel MUST set its own SECRET_KEY;
    the source-visible default would make HMAC signatures trivially
    forgeable. Raises RuntimeError (refusing to start) rather than
    warning — CR040 degrade-loudly.

    DEF185 (security review H2 + M15): the ORIGINAL check only refused
    the literal default string — an EMPTY SECRET_KEY (`SECRET_KEY=""`,
    e.g. a missing/typo'd env file line) sailed straight through, and an
    empty key makes every bearer token forgeable via HMAC(b"", user_id)
    while also silently disabling Alpaca ciphertext decryption (DEF182 —
    not touched here). Extended to refuse any non-local key shorter than
    32 bytes (an `openssl rand -hex 32` key is 64 hex chars; 32 is a
    generous floor that still catches "someone pasted three characters").
    Pulled into its own function (rather than inline module-level code)
    so it's unit-testable without reloading the whole app module.
    """
    if env != "local" and (
        secret_key == "dev-secret-change-in-prod" or len(secret_key) < 32
    ):
        raise RuntimeError(
            f"Refusing to start: env={env} requires SECRET_KEY to be set "
            "to a non-default value at least 32 characters long (env file "
            "or environment variable). Generate one with: openssl rand -hex 32"
        )


check_secret_key_boot(settings.env, settings.secret_key)

_TRIM_INTERVAL_SECONDS = 24 * 60 * 60  # 24 h
_LEAGUE_ROLL_INTERVAL_SECONDS = 60 * 60  # hourly — weekly_roll() is idempotent
_SHARIA_REFRESH_INTERVAL_SECONDS = 24 * 60 * 60  # daily — SPUS publishes daily
_CLASSIFICATION_REFRESH_INTERVAL_SECONDS = 24 * 60 * 60  # daily — sectors drift slowly
_TICKER_REFERENCE_REFRESH_INTERVAL_SECONDS = 24 * 60 * 60  # daily — CR128
_PRICE_ALERT_EVAL_INTERVAL_SECONDS = 5 * 60  # CR027
_PORTFOLIO_NAV_SNAPSHOT_INTERVAL_SECONDS = 24 * 60 * 60  # daily — CR109 slice 1
_GAME_NAV_SNAPSHOT_INTERVAL_SECONDS = 24 * 60 * 60  # daily — CR109 slice 2
_GAME_QUEUE_FILL_INTERVAL_SECONDS = 5 * 60  # CR109 slice 2 — matches CR027's cadence
_GAME_SCORING_PASS_INTERVAL_SECONDS = 30 * 60  # CR109 slice 3 — idempotent, like the league roll
# CR109 slice 3c — desks fill a field during its 30-minute `locked` window, so
# this must divide that window several times over: a single missed tick would
# cost a whole field its opponents.
_GAME_DESK_FILL_INTERVAL_SECONDS = 5 * 60


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


async def _classification_universe_refresh() -> None:
    """Background task: classify the ~503 S&P parent constituents by yfinance
    sector/industry once a day and store a snapshot row (DEF061). Idempotent like
    `_sharia_universe_refresh` — a tick that finds a fresh stored row does nothing,
    so a restart can't miss a boundary. The ~500 yfinance calls happen HERE (the
    only socket this feature opens), off the request path and off the event loop
    (`to_thread`); the read path resolves from the stored row and never blocks."""
    from app.services.classification_universe import run_classification_refresh_tick

    while True:
        try:
            await asyncio.to_thread(run_classification_refresh_tick)
        except Exception:
            logger.exception("classification_universe_refresh_failed")
        await asyncio.sleep(_CLASSIFICATION_REFRESH_INTERVAL_SECONDS)


async def _portfolio_snapshot_tick() -> None:
    """Background task: one `portfolio_value_snapshots` row per sim portfolio per
    trading day (CR136 M03). Idempotent like `_sharia_universe_refresh` — a tick
    that finds today's row stored does nothing, so a restart cannot miss a
    boundary, and the trading day comes from the benchmark's own candle grid
    rather than from the calendar. The quote fan-out and the DB writes both run
    off the event loop (`to_thread`)."""
    from app.services.portfolio_snapshot import run_portfolio_snapshot_tick

    while True:
        try:
            stats = await asyncio.to_thread(run_portfolio_snapshot_tick)
            logger.info("portfolio_snapshot_tick_complete", **stats)
        except Exception:
            logger.exception("portfolio_snapshot_tick_failed")
        await asyncio.sleep(settings.portfolio_snapshot_interval_seconds)


async def _portfolio_nav_snapshot_tick() -> None:
    """Background task: one `portfolio_nav_daily` row per user per US market
    day (CR109 slice 1 — the equity-curve spine). Idempotent like
    `_sharia_universe_refresh` — a tick that finds today's row already
    stored does nothing, so a restart cannot miss a boundary. The quote
    fan-out and the DB writes both run off the event loop (`to_thread`)."""
    from app.services.portfolio_nav_daily import run_portfolio_nav_snapshot_tick

    while True:
        try:
            stats = await asyncio.to_thread(run_portfolio_nav_snapshot_tick)
            logger.info("portfolio_nav_snapshot_tick_complete", **stats)
        except Exception:
            logger.exception("portfolio_nav_snapshot_tick_failed")
        await asyncio.sleep(_PORTFOLIO_NAV_SNAPSHOT_INTERVAL_SECONDS)


async def _game_nav_snapshot_tick() -> None:
    """Background task: one `portfolio_nav_daily` row per GAME run per US
    market day (CR109 slice 2 — the sibling of `_portfolio_nav_snapshot_tick`
    for `kind="game"` portfolios). Idempotent for the same reason as that
    tick: a tick that finds today's row already stored for a run does
    nothing, so a restart cannot miss a boundary."""
    from app.services.portfolio_nav_daily import run_game_nav_snapshot_tick

    while True:
        try:
            stats = await asyncio.to_thread(run_game_nav_snapshot_tick)
            logger.info("game_nav_snapshot_tick_complete", **stats)
        except Exception:
            logger.exception("game_nav_snapshot_tick_failed")
        await asyncio.sleep(_GAME_NAV_SNAPSHOT_INTERVAL_SECONDS)


async def _game_queue_fill_tick() -> None:
    """Background task: drain `game_queued_orders` every 5 min (CR109
    slice 2's market-hours rule — an out-of-hours order queues to the next
    open). A no-op outside market hours; when the market IS open, fetches
    a FRESH price for each still-queued order at drain time — never the
    price that was on screen when the order was placed (see
    `games_service.process_queued_orders`'s docstring).

    Then, in the SAME tick and immediately after the drain, the CR109
    Amendment I forced buy-in sweep. Not an independent task, for the reason
    Amendment H gives about duel pairing: a queued sell can OPEN a short in
    this very drain, and two tasks would race that ordering every five
    minutes with a silent failure mode — a position that should have been
    bought in simply is not, and nothing says so."""
    from app.services.games_service import process_queued_orders, sweep_forced_buyins

    while True:
        try:
            stats = await asyncio.to_thread(process_queued_orders)
            logger.info("game_queue_fill_tick_complete", **stats)
        except Exception:
            logger.exception("game_queue_fill_tick_failed")
        try:
            buyin_stats = await asyncio.to_thread(sweep_forced_buyins)
            logger.info("game_short_buyin_sweep_complete", **buyin_stats)
        except Exception:
            logger.exception("game_short_buyin_sweep_failed")
        await asyncio.sleep(_GAME_QUEUE_FILL_INTERVAL_SECONDS)


async def _game_scoring_pass_tick() -> None:
    """Background task: the SETTLING -> CLOSED scoring pass (CR109 slice 3),
    every 30 min. Idempotent like `_league_roll_tick` — `game_entries.
    scored_at` is the guard, so a tick that finds nothing left to score for
    an already-closed field does nothing, and a container restart mid-pass
    cannot double-post a career-points event (see `games_scoring_pass.py`'s
    own docstring for the two-phase read/write split this relies on)."""
    from app.services.games_scoring_pass import run_scoring_pass

    while True:
        try:
            stats = await asyncio.to_thread(run_scoring_pass)
            logger.info("game_scoring_pass_tick_complete", **stats)
        except Exception:
            logger.exception("game_scoring_pass_tick_failed")
        await asyncio.sleep(_GAME_SCORING_PASS_INTERVAL_SECONDS)


async def _game_desk_fill_tick() -> None:
    """Background task: enter the house strategy desks into any `locked` field
    that is short of the target size (CR109 slice 3c, design §11.2).

    Runs in the field's `locked` window — after entries close, so the taper is
    computed against the FINAL human count, and before the market opens, so
    every desk order queues and fills at the same open a human's weekend order
    does. Idempotent: the guard is "which desks are already entered in this
    field", so a restart mid-fill resumes rather than double-entering."""
    from app.services.games_desks import run_desk_fill_tick
    from app.services.games_duels import run_duel_pairing_tick

    while True:
        try:
            stats = await asyncio.to_thread(run_desk_fill_tick)
            logger.info("game_desk_fill_tick_complete", **stats)
            # Duels pair in the SAME tick, immediately after, and never in a
            # tick of their own: a first-run player must have an Index Desk
            # in the field to be paired against, and the desk only arrives in
            # the line above. Two independent tasks would race that ordering
            # every lock window, and the failure would be silent — a beginner
            # simply gets no duel, which looks like "no opponent was
            # available" rather than like a bug (CR109 slice 3b, §11.1).
            duels = await asyncio.to_thread(run_duel_pairing_tick)
            logger.info("game_duel_pairing_tick_complete", **duels)
        except Exception:
            logger.exception("game_desk_fill_tick_failed")
        await asyncio.sleep(_GAME_DESK_FILL_INTERVAL_SECONDS)


async def _ticker_reference_refresh() -> None:
    """Background task: fetch NASDAQ Trader's listed-securities files once a day
    and upsert the ticker reference table (CR128). Idempotent like
    `_sharia_universe_refresh` — a tick that finds a fresh refresh already stored
    does nothing, so a restart can't miss a boundary. The network fetch happens
    HERE (the only socket this feature opens), off the request path and off the
    event loop (`to_thread`); the read path (existence check + closest-match
    suggestion) resolves from the stored table and never blocks on the network."""
    from app.services.ticker_reference import run_ticker_reference_refresh_tick

    while True:
        try:
            await asyncio.to_thread(run_ticker_reference_refresh_tick)
        except Exception:
            logger.exception("ticker_reference_refresh_failed")
        await asyncio.sleep(_TICKER_REFERENCE_REFRESH_INTERVAL_SECONDS)


async def _price_alert_evaluation_tick() -> None:
    """Background task: evaluate active price alerts every 5 min (CR027).
    Work-first-then-sleep like `_sharia_universe_refresh` — a container
    restart shouldn't leave a breached alert unchecked for a full interval."""
    from app.services.price_alert_evaluator import evaluate_price_alerts

    while True:
        try:
            stats = await evaluate_price_alerts()
            logger.info("price_alert_evaluation_complete", **stats)
        except Exception:
            logger.exception("price_alert_evaluation_failed")
        await asyncio.sleep(_PRICE_ALERT_EVAL_INTERVAL_SECONDS)


async def _daily_reminder_tick() -> None:
    """Background task: daily-challenge reminder sweep (CR095). Work-first-
    then-sleep like `_price_alert_evaluation_tick` — a restart shouldn't push
    a user's reminder back by a full interval. Idempotency is DB-derived and
    ultimately enforced by `uq_notifications_dedupe`, not by this task being
    the only thing running (see `daily_reminder`'s own docstring for all
    three legs) — so unlike the league/sharia/etc ticks above this one is
    safe to run on a MUCH shorter interval, and safe against a second copy of
    itself: overlapping sweeps, a `--scale`d container, or a promotion window
    where the outgoing container's in-flight sweep hasn't finished. The
    interval only bounds how late a reminder can land after the user's chosen
    hour. The DB read is a single `daily_reminder_hour IS NOT NULL` scan,
    cheap at alpha scale."""
    from app.services.daily_reminder import send_due_reminders

    while True:
        try:
            stats = await asyncio.to_thread(send_due_reminders)
            logger.info("daily_reminder_tick_complete", **stats)
        except Exception:
            logger.exception("daily_reminder_tick_failed")
        await asyncio.sleep(settings.daily_reminder_tick_interval_seconds)


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

    # CR077 Phase 0 second guard — log the measured vLLM prefix-cache hit
    # rate once at boot so a silent regression to 0% (the state this whole
    # CR started in) shows up in the logs instead of nobody finding out.
    try:
        from app.services.llm_gateway import get_llm_gateway

        await get_llm_gateway().check_prefix_cache_at_startup()
    except Exception:
        logger.exception("prefix_cache_startup_check_failed")

    # CR158 — compute each agent's prompt version now, off the request path. The
    # lazy fallback would pay ~200 ms of assembly inside `stream_chat`, which runs
    # on the event loop; DEF136 is the measurement of what blocking the loop costs
    # every other Room stream on the worker.
    try:
        from app.services.prompt_version import warm_cache

        await warm_cache()
    except Exception:
        logger.exception("prompt_version_warm_failed")

    tasks = [
        asyncio.create_task(_nightly_audit_trim()),
        asyncio.create_task(_league_roll_tick()),
        asyncio.create_task(_sharia_universe_refresh()),
        asyncio.create_task(_classification_universe_refresh()),
        asyncio.create_task(_ticker_reference_refresh()),
        asyncio.create_task(_price_alert_evaluation_tick()),
        asyncio.create_task(_portfolio_snapshot_tick()),
        asyncio.create_task(_daily_reminder_tick()),
        asyncio.create_task(_portfolio_nav_snapshot_tick()),
        asyncio.create_task(_game_nav_snapshot_tick()),
        asyncio.create_task(_game_queue_fill_tick()),
        asyncio.create_task(_game_scoring_pass_tick()),
        asyncio.create_task(_game_desk_fill_tick()),
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

# CR121 — server-side 426 enforcement, belt-and-braces on top of the
# client's own gate check. Added between Audit and CORS so a below-floor
# request never reaches a route handler or the audit log, while CORS still
# wraps the 426 response with the usual headers.
app.add_middleware(VersionGateMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routers
app.include_router(admin_router)
app.include_router(backtest_admin_router)  # CR164 — admin-only as-of Room runs
app.include_router(alpaca_router)
app.include_router(ai_coach_router)
app.include_router(auth_router)
app.include_router(billing_router)
app.include_router(onboarding_router)
app.include_router(one_on_one_router)
app.include_router(brief_router)
app.include_router(coach_router)  # legacy /v1/coach/* — deprecated AT:R27
app.include_router(daily_challenge_router)
app.include_router(games_router)  # CR109 slice 2 — dark-launched, include_in_schema=False
app.include_router(glossary_router)
app.include_router(journal_router)
app.include_router(league_router)
app.include_router(lessons_router)
app.include_router(llm_router)
app.include_router(mandate_router)
app.include_router(portfolio_router)
app.include_router(price_alerts_router)
app.include_router(room_router)
app.include_router(sim_router)
app.include_router(tickers_router)
app.include_router(feedback_router)
app.include_router(watchlist_router)
app.include_router(webhooks_router)


@app.get("/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0", "env": settings.env}


@app.get("/v1/client/release-floor", response_model=ReleaseFloorResponse)
async def client_release_floor(
    # CR121 audit MINOR: `ge=0` for defence in depth. Round 1 claimed every
    # degenerate `build` resolves to `ok`, never `block` — true for the header
    # path (`parse_build_number` never raises, never returns negative) but this
    # is a bare Pydantic query param that doesn't go through it, so
    # `?build=not-a-number` 422s (a third outcome the claim didn't name) and,
    # against a hand-written `min_build=0` row, `?build=-5` resolves to
    # `block`. Neither is reachable by a real client — `DeviceContext`'s build
    # is `int?` in Dart and the admin write path is `Field(gt=0)` — so this
    # bricks nobody today. It is still one character of guarantee over an
    # argument about who can reach what.
    build: int | None = Query(default=None, ge=0),
    locale: str | None = None,
    platform: str | None = None,
) -> ReleaseFloorResponse:
    """CR121 — client version gate. UNAUTHENTICATED, sibling of `/v1/health`:
    it must answer *before* a session exists, because a blocked client may
    be too old to authenticate at all. `action` (block/nag/ok) is decided
    server-side so raising or retracting the floor takes effect with no
    client release. `build` is the caller's own numeric build (pubspec.yaml
    `version: <semver>+<build>`, one integer, no per-platform pair);
    `locale` selects the per-raise message (en/ar/ms, EN fallback);
    `platform` (ios/android) selects the store deep link — the two bundle
    IDs differ, so nothing here derives one platform's URL from the other.
    """
    with get_session() as session:
        return build_release_floor_response(
            session, build=build, locale=locale, platform=platform,
        )


# Admin back-office stop-gap UI (AT:R27). The page itself is public; every
# API call it makes is gated by the ADMIN_SECRET bearer. Will be replaced
# by a compiled Flutter web bundle in Beta — same URL, same API.
_ADMIN_HTML_PATH = Path(__file__).parent / "static" / "admin.html"


@app.get("/admin", include_in_schema=False, response_class=HTMLResponse)
async def admin_ui() -> HTMLResponse:
    return HTMLResponse(_ADMIN_HTML_PATH.read_text(encoding="utf-8"))
