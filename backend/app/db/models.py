"""ORM models — the on-disk shape of every persisted store.

Mirrors `docs/08_tech/data_model.md` with deliberate simplifications for the
solo-dev MVP:
  - RLS policies are NOT created here. Until Supabase is wired up we run
    behind a single trusted backend; RLS lands when real Supabase plugs in.
  - JSONB → portable JSON via `JsonB` (works on Postgres + SQLite).
  - PG UUID → portable Uuid (CHAR(36) on SQLite).
  - Decimal columns use Float on SQLite; in Postgres they get NUMERIC via
    SQLAlchemy's Numeric type. Money fields use Numeric(12, 4).

The User table follows Supabase's `auth.users` shape closely enough that the
swap-over is mechanical: drop our `users` table, create a FK from app tables
to `auth.users.id`, point auth-related code at the Supabase admin API.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonB, Uuid


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    email: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    apple_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    google_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    hms_unionid: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    plan: Mapped[str] = mapped_column(String, default="floor_pass", nullable=False)
    credit_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locale: Mapped[str] = mapped_column(String, default="en", nullable=False)
    timezone: Mapped[str] = mapped_column(String, default="UTC", nullable=False)

    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    anonymous_session_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    claimed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # Device-stable identifier (UUID from shared_preferences). When the user
    # claims with Apple/email we keep their original id but mark claimed_at.
    device_user_id: Mapped[Optional[UUID]] = mapped_column(Uuid(), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        server_default=func.now(), nullable=False,
    )


class MandateRow(Base):
    __tablename__ = "mandates"
    __table_args__ = (UniqueConstraint("user_id", "version", name="uq_mandate_user_version"),)

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Full Pydantic Mandate snapshot — versioned, so a new edit writes a new
    # row rather than mutating an existing one. Lets us reconstruct any
    # historic mandate exactly.
    snapshot: Mapped[dict] = mapped_column(JsonB(), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False,
    )


class UserOverlayRow(Base):
    __tablename__ = "user_overlays"
    __table_args__ = (
        UniqueConstraint("user_id", "agent_id", "version", name="uq_overlay_user_agent_version"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    content: Mapped[str] = mapped_column(String, nullable=False)
    plain_english: Mapped[str] = mapped_column(String, nullable=False)
    based_on_session: Mapped[Optional[UUID]] = mapped_column(Uuid(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class OverlayEditCounter(Base):
    """Per-(user, agent) lifetime accepted-edit count. Independent of the
    versions table because retention may drop old versions while the count
    still gates Floor-Pass tier writes."""

    __tablename__ = "overlay_edit_counts"
    __table_args__ = (
        UniqueConstraint("user_id", "agent_id", name="uq_overlay_count_user_agent"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(String, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class JournalEntryRow(Base):
    __tablename__ = "journal_entries"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    entry_type: Mapped[str] = mapped_column(String, index=True, nullable=False)
    reference_id: Mapped[Optional[UUID]] = mapped_column(Uuid(), nullable=True)

    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ticker: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    agents_involved: Mapped[list] = mapped_column(JsonB(), default=list, nullable=False)
    mandate_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    tags: Mapped[list] = mapped_column(JsonB(), default=list, nullable=False)
    user_note: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    payload: Mapped[dict] = mapped_column(JsonB(), default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False,
    )


class LessonProgressRow(Base):
    __tablename__ = "lessons_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_lessons_user_lesson"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    lesson_id: Mapped[str] = mapped_column(String, nullable=False)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    quiz_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quiz_passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_quiz_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class AgentActivationRow(Base):
    __tablename__ = "agent_activations"
    __table_args__ = (
        UniqueConstraint("user_id", "agent_id", name="uq_activation_user_agent"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(String, nullable=False)
    activation_method: Mapped[str] = mapped_column(String, nullable=False)
    triggering_lesson_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class SimPortfolioRow(Base):
    __tablename__ = "sim_portfolios"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, default="Main", nullable=False)
    starting_capital: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    current_cash: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )

    holdings: Mapped[list["SimHoldingRow"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan",
    )


class SimHoldingRow(Base):
    __tablename__ = "sim_holdings"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "ticker", name="uq_holding_portfolio_ticker"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        Uuid(), ForeignKey("sim_portfolios.id", ondelete="CASCADE"), nullable=False,
    )
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    avg_cost: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )

    portfolio: Mapped[SimPortfolioRow] = relationship(back_populates="holdings")


class SimTradeRow(Base):
    __tablename__ = "sim_trades"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    portfolio_id: Mapped[UUID] = mapped_column(
        Uuid(), ForeignKey("sim_portfolios.id", ondelete="CASCADE"), nullable=False,
    )
    ticker: Mapped[str] = mapped_column(String, index=True, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    stop: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    target: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    horizon_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    status: Mapped[str] = mapped_column(String, default="open", nullable=False)
    verdict_ref: Mapped[Optional[UUID]] = mapped_column(Uuid(), nullable=True)
    realised_pnl: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)


class RoomRunRow(Base):
    __tablename__ = "room_runs"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    ticker: Mapped[str] = mapped_column(String, index=True, nullable=False)

    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    mandate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    model_tier: Mapped[str] = mapped_column(String, nullable=False)
    rounds: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    transcript: Mapped[list] = mapped_column(JsonB(), default=list, nullable=False)
    verdict: Mapped[Optional[dict]] = mapped_column(JsonB(), nullable=True)

    credit_cost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String, default="running", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class SimWatchlistRow(Base):
    """A18 — user-curated watchlist. Free-form ticker strings (anything Yahoo
    can quote), with optional notes. Unique per (user, ticker).
    """

    __tablename__ = "sim_watchlists"
    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class BugReportRow(Base):
    """In-app bug reports — shake / long-press trigger on the iPhone.

    user_id is nullable: anonymous sessions may file reports before the
    anon bootstrap completes.
    """

    __tablename__ = "bug_reports"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[Optional[UUID]] = mapped_column(Uuid(), index=True, nullable=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    steps: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    route: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    app_version: Mapped[str] = mapped_column(String, nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class AuthChallengeRow(Base):
    """One-time codes for magic-link + Apple Sign-In exchange.

    Stored hashed; consumed once on verify. Lives in our DB so the auth
    scaffold works end-to-end without requiring Supabase to be provisioned.
    When real Supabase plugs in, this table goes away.
    """

    __tablename__ = "auth_challenges"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # 'magic_link' | 'apple'
    target: Mapped[str] = mapped_column(String, index=True, nullable=False)  # email or apple sub
    code_hash: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[Optional[UUID]] = mapped_column(Uuid(), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class WaitlistRow(Base):
    """Marketing site waitlist — email captures before public launch.

    Upsert on email so duplicate submissions are idempotent; source records
    which surface the signup came from (e.g. 'marketing_site').
    """

    __tablename__ = "waitlist"
    __table_args__ = (UniqueConstraint("email", name="uq_waitlist_email"),)

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String, index=True, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
