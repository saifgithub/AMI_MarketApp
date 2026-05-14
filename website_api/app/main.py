"""AMI Website API — standalone FastAPI service.

Handles website-only concerns (waitlist, future contact forms).
Zero shared code with the main ami_trade app backend.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import init_schema
from app.routes.waitlist import router as waitlist_router

app = FastAPI(
    title="AMI Website API",
    version="0.1.0",
    docs_url="/docs" if settings.env != "prod" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)

init_schema()

app.include_router(waitlist_router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
