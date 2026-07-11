"""ORM models — the on-disk shape of every persisted store.

Mirrors `docs/initial_specs/08_tech/data_model.md` with deliberate simplifications for the
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
    Index,
    Integer,
    Numeric,
    String,
    TypeDecorator,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.secret_crypto import decrypt_secret, encrypt_secret
from app.db.base import Base, JsonB, Uuid


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EncryptedString(TypeDecorator):
    """String column encrypted at rest (DEF044).

    Encrypts on write, decrypts on read, transparently — so every existing
    call site reads/writes plaintext while Postgres stores ciphertext. Legacy
    cleartext rows pass through unchanged (see `secret_crypto`). Not usable in
    SQL filters (values are opaque ciphertext), which is fine here: these
    columns are only ever read whole or checked for None.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        return encrypt_secret(value)

    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        return decrypt_secret(value)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    email: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    apple_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    google_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    hms_unionid: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Display name. Set on first OIDC auth (Apple `full_name` from iOS
    # SDK, Google `name` claim) — minimum-data policy: sub + name + email
    # is all we persist from OIDC providers. Never overwritten.
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

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

    # Device + build context (BL1, AT:R33). Sent on every /v1/auth/anon call
    # via device_info_plus + package_info_plus. Single-device-per-user is the
    # locked alpha assumption — multi-device split is BL2.
    device_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    os_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_app_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Trial management (AT:R27 admin back-office)
    trial_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    trial_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Admin-only suspension flag. Non-null = suspended; clears on reinstate.
    suspended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Alpaca paper trading link (AT:R45/R47). Null = unlinked.
    # auth_mode: 'oauth' (access_token = Bearer token) or 'apikey'
    # (access_token = key ID, refresh_token = key secret).
    # DEF044: both are encrypted at rest via EncryptedString (transparent to
    # every read/write site); legacy cleartext rows migrate lazily on next write.
    alpaca_access_token: Mapped[Optional[str]] = mapped_column(EncryptedString, nullable=True)
    alpaca_refresh_token: Mapped[Optional[str]] = mapped_column(EncryptedString, nullable=True)
    alpaca_linked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    alpaca_auth_mode: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Reputation + league identity (CR004, D-060). handle is the anonymous
    # leaderboard name (adjective+noun, minted on first league contact);
    # one self-service regeneration allowed. reputation is the lifetime
    # point counter kept in lockstep with reputation_events.
    handle: Mapped[Optional[str]] = mapped_column(
        String, unique=True, index=True, nullable=True,
    )
    handle_regenerated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    reputation: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False,
    )
    show_display_name: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        server_default=func.now(), nullable=False,
    )


class UserDeviceRow(Base):
    """BL2 (AT:R33): one row per device install. Keyed by `device_install_id`
    (mobile-generated UUID persisted once on first launch, never overwritten).
    Re-keyed to point at the adopting user on claim-adoption.
    """

    __tablename__ = "user_devices"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    device_install_id: Mapped[UUID] = mapped_column(
        Uuid(), nullable=False, unique=True,
    )

    device_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    os_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    app_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(),
        nullable=False,
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
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True,
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
    # AT:R34 (eeeb866f): startup sweep auto-retries stuck runs once before
    # giving up. retry_count tracks how many times the row has been
    # re-spawned by _sweep_stuck_runs after a container restart.
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


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
    # Git branch name a bug-fix agent claimed for this report.
    # Coordinates parallel work: two /fix-bugs sessions can't both claim
    # the same `open` bug because the UPDATE that sets status='in_progress'
    # also writes the branch name in the same statement.
    assigned_branch: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Optional photo/file attached at submit time. attachment_path is a
    # relative filename under settings.bug_attachments_dir; attachment_mime
    # is the original Content-Type. Both nullable — the text-only report
    # path is the common case.
    attachment_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    attachment_mime: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
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
    # B-tier audit (AT:R37): wrong-code-attempt counter. Bumped on every
    # verify miss against the still-active challenge; once it hits
    # MAX_MAGIC_LINK_ATTEMPTS the row is force-consumed so the attacker has
    # to request a fresh code (which a real user can always do).
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class LLMAuditRow(Base):
    """Every LLM gateway call. Full prompt + full response captured for alpha
    triage. Volume is bounded by gateway calls (~10s per active session),
    not by HTTP requests. Retention is unbounded until tester count grows."""

    __tablename__ = "llm_audit"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True,
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(Uuid(), index=True, nullable=True)
    agent_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    flow: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tier: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    locale: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    system_prompt: Mapped[str] = mapped_column(String, nullable=False)
    messages: Mapped[list] = mapped_column(JsonB(), default=list, nullable=False)
    response_text: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class HTTPAuditRow(Base):
    """Every inbound HTTP request. Bodies captured (truncated). Auth headers
    scrubbed at the middleware level — never reach this row."""

    __tablename__ = "http_audit"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True,
    )
    method: Mapped[str] = mapped_column(String, nullable=False)
    path: Mapped[str] = mapped_column(String, index=True, nullable=False)
    query: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_id: Mapped[Optional[UUID]] = mapped_column(Uuid(), index=True, nullable=True)
    client_ip: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    request_body: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    response_body: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    response_truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_streaming: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)


class OneOnOneMessageRow(Base):
    """Durable record of every 1-on-1 chat turn (Concierge + every agent).
    The agent_runner streams via SSE and currently keeps no server-side
    record. This table closes that gap so we can replay any conversation."""

    __tablename__ = "one_on_one_messages"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class SubscriptionEventRow(Base):
    """Complete audit trail for all plan / credit / trial / suspension changes.

    Every admin write and every app-side credit consumption produces a row.
    RevenueCat webhooks will write revenuecat_purchase rows in MVP M1.
    source values: admin_override | app | revenuecat
    """

    __tablename__ = "subscription_events"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)

    event_type: Mapped[str] = mapped_column(String, nullable=False)
    from_value: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    to_value: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    admin_id: Mapped[Optional[UUID]] = mapped_column(Uuid(), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False,
    )


class ReputationEventRow(Base):
    """Append-only reputation point grants (CR004, D-060).

    (user_id, event_type, ref_id) is the dedup anchor: award() refuses a
    second grant for the same ref. users.reputation is the denormalized
    running total; this table is the ledger behind it.

    DEF039: that dedup was app-code-only (a SELECT-then-INSERT race) — two
    concurrent award() calls for the same ref could both pass the check and
    double-insert. The partial unique index below is the defense-in-depth
    backstop; it's partial (WHERE ref_id IS NOT NULL) because ref_id is
    nullable and award() itself only dedups when a ref_id is given.
    """

    __tablename__ = "reputation_events"
    __table_args__ = (
        Index(
            "uq_reputation_event_dedup",
            "user_id", "event_type", "ref_id",
            unique=True,
            postgresql_where=text("ref_id IS NOT NULL"),
            sqlite_where=text("ref_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)

    event_type: Mapped[str] = mapped_column(String, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    ref_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False,
    )


class DailyChallengeAttemptRow(Base):
    """Server truth for daily-challenge answers (CR004).

    UNIQUE(user_id, challenge_id) closes the re-attempt exploit — the
    route returns the stored result with already_attempted=true on a
    duplicate instead of accepting a fresh answer.
    """

    __tablename__ = "daily_challenge_attempts"
    __table_args__ = (
        UniqueConstraint("user_id", "challenge_id", name="uq_challenge_attempt_user"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)

    challenge_id: Mapped[str] = mapped_column(String, nullable=False)
    selected_option: Mapped[int] = mapped_column(Integer, nullable=False)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class LeagueRow(Base):
    """One weekly cohort at one tier (CR004, D-060). week is ISO 'YYYY-Www'."""

    __tablename__ = "leagues"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    week: Mapped[str] = mapped_column(String(8), index=True, nullable=False)
    tier: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class LeagueMemberRow(Base):
    """A user's seat in one weekly league (CR004, D-060).

    week is denormalized from the league so UNIQUE(user_id, week) holds
    without a join. points accrues in-week via reputation_service.award();
    rank_final + outcome are stamped by the next weekly_roll().
    """

    __tablename__ = "league_members"
    __table_args__ = (
        UniqueConstraint("user_id", "week", name="uq_league_member_user_week"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    league_id: Mapped[UUID] = mapped_column(
        Uuid(), ForeignKey("leagues.id"), index=True, nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    week: Mapped[str] = mapped_column(String(8), nullable=False)

    points: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False,
    )
    rank_final: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
