"""FastAPI entry point for the AMI Trade backend."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.coach import router as coach_router
from app.api.journal import router as journal_router
from app.api.lessons import router as lessons_router
from app.api.onboarding import router as onboarding_router
from app.api.one_on_one import router as one_on_one_router
from app.api.room import router as room_router
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="AMI Trade API",
    version="0.1.0",
    description="Backend for AMI Trade — 12-agent trading-education app.",
    docs_url="/docs" if settings.env != "prod" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routers
app.include_router(onboarding_router)
app.include_router(one_on_one_router)
app.include_router(coach_router)
app.include_router(journal_router)
app.include_router(lessons_router)
app.include_router(room_router)


@app.get("/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0", "env": settings.env}
