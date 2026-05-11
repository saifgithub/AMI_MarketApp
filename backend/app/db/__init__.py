"""SQLAlchemy persistence layer.

Single source of truth for everything stored long-term:
  - User identity + plan state               → users
  - Mandates (versioned)                     → mandates
  - Coach overlays (versioned)               → user_overlays
  - Lessons progress + agent activations     → lessons_progress, agent_activations
  - Sim portfolio / holdings / trades        → sim_portfolios, sim_holdings, sim_trades
  - Room runs                                → room_runs
  - Decision Journal entries                 → journal_entries

Sync SQLAlchemy 2.0. FastAPI runs sync session work in a threadpool — fine
for the load profile we expect through MVP. The async route is reserved for
LLM calls and streaming.

A single `DATABASE_URL` controls the backend:
  - postgresql+psycopg2://...   real Postgres (docker-compose, prod via
                                Supabase plugged in later)
  - sqlite:///./.local.db       solo-dev fallback when no Postgres is up
  - sqlite:///:memory:          tests (set per-fixture)
"""

from app.db.base import Base
from app.db.session import (
    get_engine,
    get_session,
    get_sessionmaker,
    init_schema,
    reset_for_tests,
)

__all__ = [
    "Base",
    "get_engine",
    "get_session",
    "get_sessionmaker",
    "init_schema",
    "reset_for_tests",
]
