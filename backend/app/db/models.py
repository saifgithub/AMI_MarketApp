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

from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
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
    # CR039 (AT:R60): the allowance window behind `credit_balance`. Credits
    # reset monthly and don't accumulate (credits.md), so the balance is only
    # meaningful alongside the period it was granted for. `credits_plan_at_grant`
    # holds the *effective* plan at grant time — re-granting when it drifts is
    # what makes trial expiry bite immediately instead of at month rollover.
    # Both nullable: existing rows re-grant on first touch, no backfill.
    credits_period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    credits_plan_at_grant: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # CR047 "The Winzip": when a Floor-Pass user's Room credits are exhausted
    # under GTM_FUNNEL=winzip we reset +1 Room immediately but block the next
    # convene until this timestamp. NULL = no cooldown pending. Only the winzip
    # funnel writes it; every other path ignores it. See credit_service.spend.
    room_cooldown_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    locale: Mapped[str] = mapped_column(String, default="en", nullable=False)
    timezone: Mapped[str] = mapped_column(String, default="UTC", nullable=False)
    # CR095 — the local hour (0-23) the daily-challenge reminder should fire
    # at, evaluated against `timezone` above (no second timezone column —
    # reuse the one that already exists). NULL = reminders off. Nullable
    # with no server_default and no backfill: every existing row opts out
    # until the user picks a time, which is the correct reading (never
    # silently opt a pre-CR095 user into a new push/email).
    daily_reminder_hour: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

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

    # CR125 — revocation counter for scaffold Bearer tokens. Embedded in every
    # token issued (`scaffold:<hex>:<exp>:<ver>:<sig>`); `get_current_user`
    # 401s when a token's version doesn't match this. `DELETE /v1/auth/session`
    # bumps it, which invalidates every outstanding token for the user in one
    # write — the real-revocation half of CR125 (previously a no-op sign-out).
    token_version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False,
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

    # CR109 slice 3c — house strategy desks (design §11.2). A desk is a real
    # user row with a real portfolio and a real NAV series: it enters fields,
    # trades through the same game path, and pays the same fee, so its return
    # is produced by the market rather than sampled to look plausible. The
    # flag exists so a desk can be (a) disclosed on every entrant-rendering
    # surface — §11.2's disclosure decision is Saiful's and it is load-bearing:
    # a user copying an undisclosed desk believes they are copying a person —
    # and (b) subtracted from every real-user metric, so the house never
    # inflates a number Saiful makes decisions on.
    #
    # `desk_key` names WHICH strategy (`index`, `momentum`, …) and is unique,
    # which is also the idempotency key for `ensure_desk_users()`: a second
    # container starting up cannot mint a second Momentum Desk.
    is_desk: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False, index=True,
    )
    desk_key: Mapped[Optional[str]] = mapped_column(
        String, unique=True, nullable=True,
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


class ClientReleaseFloorRow(Base):
    """CR121 — append-only client version-gate log. One row per raise, NOT a
    mutable setting: "message will be added for each time we move the bar"
    means the answer to "what did we tell users when we killed build N?" is a
    row, not a memory.

    The ACTIVE floor is the row with the highest `min_build` among rows where
    `active` is true — never mutated in place; a bad raise is retracted by
    flipping `active` to false on the offending row, which lets the
    previous-highest active row govern again without losing history.

    `min_build` is a single integer (not a per-platform pair) — pubspec.yaml
    carries one `version: <semver>+<build>` shared by iOS and Android, and
    the gate compares plain `int >=` on the build number, never semver.
    """

    __tablename__ = "client_release_floors"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    min_build: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    # Soft nag threshold: min_build <= build < recommended_build shows a
    # dismissible nag instead of the hard block. Null = no nag band.
    recommended_build: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    headline: Mapped[str] = mapped_column(String, nullable=False)
    body_en: Mapped[str] = mapped_column(String, nullable=False)
    # Nullable — EN fallback when unset. The per-raise message is
    # operational copy authored at raise time, not shipped ARB content, so
    # it cannot go through the normal translation cycle before Saiful needs
    # to raise the bar.
    body_ar: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    body_ms: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(),
        nullable=False,
    )
    created_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Retraction flag — flip false to undo a bad raise without deleting the
    # row (the history stays queryable). Default true: a freshly-created
    # raise is live immediately.
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


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
    __table_args__ = (
        # CR136: the database-level backstop behind an application check-then-act.
        # Two concurrent POSTs to the Finding route both read "no prior Finding
        # today" and "budget available", then both generate and both write —
        # measured at 5 concurrent requests producing 5 Findings against a cap of
        # 2, with 5 LLM calls billed for one logical action. A double-tap or a
        # client retry on a slow response is enough to trigger it.
        #
        # NULL for every other entry type, and NULLs do not collide in a unique
        # index on either Postgres or SQLite, so this constrains CR136 rows only.
        #
        # PARTIAL on `deleted_at IS NULL` (CR136-M07 audit r1, BLOCKER B1). As a
        # plain constraint it also covered TOMBSTONES, so deleting today's
        # Finding and regenerating collided with the deleted row: no new row was
        # ever written, the route handed back the deleted id — a link into an
        # empty journal — and because `daily_used` counts ROWS, both spend
        # counters froze. Measured: five generations against a daily cap of two,
        # stopped only by the rate limiter, each one a billed LLM call. The
        # invariant we actually want is "at most one LIVE Finding per user per
        # entry type per day"; a tombstone is not live.
        #
        # `WHERE deleted_at IS NULL` is spelled identically on Postgres and
        # SQLite, so unlike the JSON-expression index this migration's docstring
        # rejected, this one is enforced in production AND under test.
        Index(
            "uq_journal_dedupe",
            "user_id", "entry_type", "dedupe_key",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    entry_type: Mapped[str] = mapped_column(String, index=True, nullable=False)
    # Indexed under CR136-M08 m2: both of CR136's journal reads filter on it,
    # so every Health-card open and every Finding write was a scan.
    reference_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(), index=True, nullable=True,
    )

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
    # CR136: `<portfolio_id>:<as_of>` for a Portfolio Health Finding, NULL for
    # every other entry type. See the unique constraint above.
    dedupe_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)


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
    """A portfolio — TRAINING (`kind="training"`, `run_id` NULL, the
    original one-per-user shape) or GAME (`kind="game"`, one row per game
    run — CR109 slice 2, implementation_plan.md §4.2).

    `user_id` used to be UNIQUE on its own, which is what made "the
    portfolio" a safe singular lookup everywhere. Widening it to
    `UniqueConstraint(user_id, kind, run_id)` means a user can now hold
    MANY rows (one training + one per live/past game run) — every call
    site that queried this table directly with `.scalar_one_or_none()` or
    assumed "one row = one user" had to be re-scoped to `kind="training"`
    alongside this change (`api/sim.py`'s reset route, `portfolio_snapshot.py`
    M03's tick, `day_trader_outcomes.py`'s `_starting_capital`,
    `merge_service.py`) or it now raises `MultipleResultsFound` the moment a
    user has both. `SimEngine._load_portfolio_row` / `ensure_portfolio` take
    a defaulted `kind="training"` so the ~18 existing callers through those
    two functions are unaffected.
    """

    __tablename__ = "sim_portfolios"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "kind", "run_id", name="uq_portfolio_user_kind_run",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String, default="training", nullable=False)
    run_id: Mapped[Optional[UUID]] = mapped_column(Uuid(), index=True, nullable=True)
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
    # CR109 slice 2 (G2) — a corporate split adjusts `quantity` / `avg_cost`
    # IN PLACE (quantity *= ratio, avg_cost /= ratio — cost basis unchanged,
    # so NAV stays continuous once the market price divides by the same
    # ratio) and flags the row here rather than writing a
    # `portfolio_nav_daily.capital_event`: a split leaves economic value
    # unchanged, so — unlike a reset or a top-up — it must NOT split the TWR
    # chain, and only `capital_event` does that. NULL on every row this CR
    # doesn't touch, including every TRAINING holding (§12 of the design:
    # "training absorbs it with a free reset" — split handling is a GAME-
    # portfolio-only concern; see `SimEngine.apply_split`).
    split_adjusted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
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


class PortfolioValueSnapshotRow(Base):
    """One valuation row per sim portfolio per TRADING DAY — CR136's Tier-2 history.

    Append-only, one row per `(portfolio_id, as_of)`; the unique constraint is
    the database-level backstop behind the tick's own check-before-insert. Rows
    are keyed to `portfolio_id`, not `user_id`, so a series structurally cannot
    span a reset: `reset_portfolio` is destroy-and-recreate, and the new
    portfolio gets a new UUID.

    `predicted_vol_ann` is the Tier-1 EWMA σₚ **as a decimal fraction**
    (0.262 ≡ 26.2% annualised), stored beside the realised value so the model is
    permanently auditable (Rev 4 F16): the bias test divides a realised return
    by it and the units only cancel because both sides are fractions. Null when
    the engine refused (mock data), was insufficient, or was unavailable — never
    0.0, which would read as a confident prediction of no risk at all.

    **`drawdown_pct` is NOT the Tier-2 max drawdown.** It is the sim's existing
    vs-STARTING-CAPITAL number, persisted for continuity with what the app
    already shows. The Tier-2 tile renders the rolling peak-to-trough figure
    computed from `total_value` history and must never read this column: on the
    path $10k → $15k → $12k this column reads 0.0 while the Tier-2 number reads
    20.0. Two different quantities that were both once called "drawdown" is the
    Rev 2 defect this warning exists to prevent recurring.
    """

    __tablename__ = "portfolio_value_snapshots"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "as_of", name="uq_pvs_portfolio_asof"),
        Index("ix_pvs_portfolio_asof", "portfolio_id", "as_of"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    portfolio_id: Mapped[UUID] = mapped_column(
        Uuid(), ForeignKey("sim_portfolios.id", ondelete="CASCADE"), nullable=False,
    )
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    total_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    cash: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    invested_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    drawdown_pct: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    predicted_vol_ann: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    n_observations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    engine_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)


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


class NotificationRow(Base):
    """CR027 -- one row per notification regardless of delivery channel or
    outcome. The durable source of truth; push (OneSignal) is best-effort on
    top of this, never the other way round. Written only by
    notification_service.notify().
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_user_read", "user_id", "read_at"),
        # CR095 audit MAJOR: `source_ref` is the caller's dedupe business key,
        # and until this constraint existed the ONLY thing preventing a
        # double-send under concurrent execution was "in practice only one
        # process ever calls this" — an operational fact of today's melehost
        # topology, not a control. `docker compose up --scale`, a uvicorn
        # `--workers` flag, or a promotion window where the outgoing
        # container's in-flight sweep overlaps the incoming one's all break
        # it, silently, by sending twice. SQL treats NULLs as distinct in a
        # unique constraint, so callers that pass no `source_ref` (the
        # majority) are deliberately unaffected — opting in is passing one.
        UniqueConstraint("user_id", "type", "source_ref", name="uq_notifications_dedupe"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    # Open-ended on purpose (price_alert | daily_challenge | game_event |
    # trial_end | room_verdict | ...) -- plain String, not an enum, so a
    # future consumer never needs a migration just to add a type.
    type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(String, nullable=False)
    deep_link: Mapped[dict] = mapped_column(JsonB(), default=dict, nullable=False)
    source_ref: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class PriceAlertRow(Base):
    """CR027 §4 -- a user's stop/target/manual price-threshold watch.
    ACTIVE -> FIRED (breach) or ACTIVE -> CANCELLED (user/system cancel);
    terminal states are read-only (audit trail -- closing the linked trade
    does not delete or mutate the alert).
    """

    __tablename__ = "price_alerts"
    __table_args__ = (
        Index("ix_price_alerts_user_status", "user_id", "status"),
        Index("ix_price_alerts_ticker_status", "ticker", "status"),
        Index("ix_price_alerts_fired_at", "fired_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    threshold_type: Mapped[str] = mapped_column(String, nullable=False)  # stop|target|manual_above|manual_below
    threshold_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)  # active|fired|cancelled
    # No FK constraint, matching SimTradeRow.verdict_ref's convention -- a
    # bare nullable reference so closing/deleting a trade never cascades
    # into this audit-trail row.
    trade_ref: Mapped[Optional[UUID]] = mapped_column(Uuid(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    fired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_commentary: Mapped[Optional[str]] = mapped_column(String(280), nullable=True)


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
    # CR043 — the reporter-facing half of the lifecycle.
    # resolved_at + resolution_note are written when Saiful flips the
    # status to 'resolved'; the note is shown to the reporter verbatim.
    # acknowledged_at is stamped once that user has actually been shown
    # the toast, so the message fires exactly once and survives reinstall
    # (a device-local "seen" flag would not).
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    resolution_note: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
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
    not by HTTP requests. Retention is unbounded until tester count grows.

    CR141: the four `*_tokens` columns are the terminal `usage` block the
    gateway previously discarded (DEF125's `meta` channel now carries it —
    see `llm_gateway.py`). All four are NULLable and no code path is allowed
    to write 0 in place of a value the provider never reported: a provider
    that is silent on cache fields (most of them, outside Anthropic/DeepSeek)
    means "unmeasured", and a 0 there would misrepresent that as "measured,
    zero hits" — the exact CR040 degrade-loudly distinction. `cache_write_tokens`
    is Anthropic-only (the only provider we register that charges a cache
    write fee); every other provider's rows leave it NULL, permanently.
    """

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
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cache_read_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cache_write_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # CR158 — which prompt generation produced this row. A short hash of the fully
    # assembled prompt for a fixed reference mandate (see
    # `app/services/prompt_version.py`), so it changes when any assembly layer
    # changes and not when a user's mandate does.
    #
    # NULLABLE and permanently so. Every row written before this column existed is
    # NULL, and NULL means "unversioned", never "version zero" — the same CR040
    # distinction the `*_tokens` columns above draw. It is also what a row gets when
    # assembly fails: an honest unknown beats a fabricated generation, since the
    # entire point of the column is that a measurement can trust which prompt it is
    # measuring.
    prompt_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)


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


class BadgeRow(Base):
    """Earned-once badges (CR091/CR092), co-located with the streak-milestone
    credit grant in reputation_service.py::_grant_milestone — same DEF049
    idempotency guarantee (the reputation_events guard row gates both).

    UNIQUE(user_id, badge_key) is defense-in-depth, mirroring the
    reputation_events dedup index (DEF039): the milestone guard row already
    makes a double-award structurally unreachable, but a DB constraint costs
    nothing and catches a future caller that doesn't go through it.
    """

    __tablename__ = "badges"
    __table_args__ = (
        UniqueConstraint("user_id", "badge_key", name="uq_badge_user_key"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)

    badge_key: Mapped[str] = mapped_column(String, nullable=False)
    ref_type: Mapped[str] = mapped_column(String, nullable=False)
    ref_id: Mapped[str] = mapped_column(String, nullable=False)
    # CR092: the 365-day Marathoner badge also renders as permanent profile
    # flair — a flag on the badge record rather than a parallel flair table.
    is_permanent_flair: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False,
    )

    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class StreakFreezeRow(Base):
    """Consumed streak freezes (CR094) — a Floor Manager perk, 2/year.

    A recorded, countable row per frozen local-date, never "tolerate a
    missing day in the streak scan" (Architect D4): that would be
    unbounded and unauditable. `period_key` is the calendar-year bucket
    (str(frozen_date.year), in the user's local timezone) the 2-per-year
    allowance resets on — the simplest defensible reading of "2/year"
    absent a subscription-anniversary date to key off (flagged for Saiful
    in the hand-off, not decided unilaterally).
    """

    __tablename__ = "streak_freezes"
    __table_args__ = (
        UniqueConstraint("user_id", "frozen_date", name="uq_streak_freeze_user_date"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)

    frozen_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_key: Mapped[str] = mapped_column(String, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class RevenueCatEventRow(Base):
    """Idempotency ledger for RevenueCat webhook deliveries (CR084).

    RevenueCat retries any non-2xx delivery, so the same purchase event can
    arrive many times; a replayed `INITIAL_PURCHASE` must never double-grant
    credits. `event_id` (RC's own event UUID) is UNIQUE, so the webhook can
    INSERT-first inside the grant transaction and let the DB constraint reject
    a duplicate — a DB-level guarantee, not a SELECT-then-INSERT race
    (DEF039). The dedup row and the grant commit atomically in one
    transaction, so a delivery that failed mid-processing leaves no dedup
    trace and RC's retry can succeed; only a delivery that fully succeeded is
    ever recognized as a duplicate.
    """

    __tablename__ = "revenuecat_events"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    # RC's event id — the dedup anchor. UNIQUE is the whole point of the table.
    event_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    # RC app_user_id == our users.id (str form; the event may reference a user
    # that no longer exists after a merge, so this is not a FK).
    app_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    product_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False,
    )


class SocialSentimentCacheRow(Base):
    """Durable Adanos sentiment cache (CR041).

    The cache used to live in a dict on the _AdanosSource instance, so it died
    with the process. That made the free tier's 250-calls/month budget
    unspendable-on-purpose: api-alpha was recreated 4× on 2026-07-17 alone
    (promotions, CR035 flag flips), and each restart re-burned the whole
    universe. A 150-ticker benchmark needs the cache to outlive the container,
    hence a table rather than memory or a volume (api-alpha mounts no /data).

    `found=False` rows are cached deliberately: an uncovered ticker previously
    cost one live call per convene forever, a quota leak independent of TTL.
    Staleness is decided by the reader against SOCIAL_CACHE_TTL_DAYS, not by a
    stored expiry — so changing the TTL re-dates every row without a backfill.
    """

    __tablename__ = "social_sentiment_cache"

    ticker: Mapped[str] = mapped_column(String, primary_key=True)
    found: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    payload: Mapped[Optional[dict]] = mapped_column(JsonB, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False,
    )


class ShariaUniverseSnapshotRow(Base):
    """One persisted snapshot of the sourced Sharia universe (CR075).

    Append-only: the daily `_sharia_universe_refresh()` background task writes one
    row per SUCCESSFUL fetch, and the read path resolves from the latest row for a
    standard by `fetched_at`. Persisting the universe takes the network fetch off
    the request path (a restart reads the row, never a socket — CR069's
    `default_halal_universe_async` no longer stalls the first halal trade after
    boot) and turns a source outage from DEF093's every-halal-trade block into an
    ageing-but-served list disclosing its held `as_of`.

    `fetched_at` (OUR UTC stamp) is the freshness signal the parent-index mirror
    never publishes: a frozen mirror is visible because `fetched_at` keeps
    advancing across snapshots while `as_of` does not. Append-only also answers
    "which companies did AMI treat as compliant on a given day" — one row per day
    is negligible storage (two lists of a few hundred tickers), so retention is
    unbounded for now, matching `llm_audit`.
    """

    __tablename__ = "sharia_universe_snapshots"
    __table_args__ = (
        Index(
            "ix_sharia_snapshot_standard_fetched",
            "standard",
            "fetched_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    # The screening standard this snapshot enforces (e.g. "AAOIFI"). Indexed with
    # fetched_at so "latest row for a standard" is a single ordered lookup.
    standard: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    parent_source_url: Mapped[str] = mapped_column(String, nullable=False)
    # The compliant file's OWN as-of date (nullable — the parent mirror publishes
    # none). Staleness is measured against this at read time.
    as_of: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # OUR UTC stamp of when this snapshot was fetched — the missing freshness
    # signal (a frozen source mirror keeps a fixed as_of while this advances).
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    # The compliant + parent ticker sets, stored as JSON lists (a few hundred each).
    compliant: Mapped[list] = mapped_column(JsonB(), default=list, nullable=False)
    parent: Mapped[list] = mapped_column(JsonB(), default=list, nullable=False)


class ClassificationUniverseSnapshotRow(Base):
    """One persisted snapshot of the sourced sector/industry classification (DEF061).

    Append-only, exactly like `ShariaUniverseSnapshotRow` (CR075): the daily
    `_classification_universe_refresh()` background task classifies the ~503 S&P
    parent constituents (reused from the latest Sharia snapshot's `parent` set) by
    their yfinance sector/industry and writes one row per SUCCESSFUL run. The read
    path resolves from the latest row — the ~500 yfinance calls stay OFF the request
    path (a restart reads the row, never a socket), and a classify outage serves the
    held sets instead of un-enforcing the `no_fossil_fuels` /
    `no_tobacco_alcohol_gambling` filters.

    `fetched_at` (OUR UTC stamp) is the freshness signal; `as_of` is set to its date
    at write time (yfinance carries no source date, so AMI's classify date is the
    honest freshness the reader gates on). `classified` is every ticker that returned
    a sector — a name absent from it resolves UNKNOWN (permitted + disclosed), never
    a false PERMITTED. History answers "which names did AMI treat as fossil/sin on
    day X"; one row/day is negligible storage, so retention is unbounded for now.
    """

    __tablename__ = "classification_universe_snapshots"
    __table_args__ = (
        Index(
            "ix_classification_snapshot_fetched",
            "fetched_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String, nullable=False)
    # AMI's classify date (nullable to mirror the Sharia row's source-date column;
    # in practice set to fetched_at.date()). Staleness is measured against this.
    as_of: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    # Every ticker that returned a sector (the classified membership), plus the three
    # derived exclusion buckets — stored as JSON lists (a few hundred / few dozen
    # each). `defense` (weapons/aerospace-defense) is the third bucket; the curated
    # `esg_lite` exclusion set is fossil ∪ sin ∪ defense, derived at resolve time so
    # only the buckets are persisted (DEF061 esg fork, founder-ruled 2026-07-25).
    classified: Mapped[list] = mapped_column(JsonB(), default=list, nullable=False)
    fossil: Mapped[list] = mapped_column(JsonB(), default=list, nullable=False)
    sin: Mapped[list] = mapped_column(JsonB(), default=list, nullable=False)
    defense: Mapped[list] = mapped_column(JsonB(), default=list, nullable=False)
    # CR026: the per-ticker raw GICS sector tag (ticker → sector string, e.g.
    # "Technology"), captured from the SAME `yf.Ticker(t).info["sector"]` read the
    # fossil/sin classifier already performs. Feeds the sector-concentration
    # enforcement in `safety_floor.check_mandate_compliance()` and the
    # `/v1/portfolio/sector-allocation` donut — resolved off the request path from
    # this stored map, never a live fetch (CR075/DEF089). Nullable so pre-CR026 rows
    # (and the migration's back-fill) read as an empty map; a ticker absent from it
    # resolves to "Other" (disclosed, never blocking — the DEF059 inversion guard).
    sectors: Mapped[dict] = mapped_column(JsonB(), default=dict, nullable=True)


class TickerReferenceRow(Base):
    """One row per known US-listed ticker (CR128).

    Unlike the Sharia/classification snapshot tables (one append-only row per
    refresh, list-membership use case), this is one row PER SYMBOL — existence
    checks and "did you mean X" suggestions need an O(1) point lookup by symbol,
    not a scan of a JSON blob. The daily `_ticker_reference_refresh()` background
    task upserts every symbol from NASDAQ Trader's listed-securities files
    (`nasdaqlisted.txt` + `otherlisted.txt` — NASDAQ + NYSE + AMEX + ARCA, no
    auth). A symbol missing from the latest refresh gets `is_active = False`
    (soft-delete — a delisting or a transient source hiccup should never make a
    previously-valid ticker silently vanish from history; existence checks just
    filter on `is_active`).
    """

    __tablename__ = "ticker_reference"

    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    exchange: Mapped[str] = mapped_column(String, nullable=False)
    is_etf: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class PriceHistoryDailyRow(Base):
    """One daily close per (ticker, trading day) — CR136's history store.

    A read-through table over the market-data provider, and the ONLY source of
    return series for the Portfolio Health engine. It exists for two reasons.
    First, the quote path's 60-second `CachingProvider` TTL is built for "what
    is AAPL worth right now", not for a 504-bar series: without a table, an
    N-holding evaluation is N Yahoo round-trips every time anyone opens the
    card. Second, trading days are derived from which bars exist — no trading
    calendar is imported anywhere — so the series has to be persisted the way
    it was served.

    `adj_close` is the analytic column (dividends/splits already applied) and is
    what every metric reads. `close` carries the same value today because the
    provider's `Candle.c` is already adjusted (`yfinance` defaults
    `auto_adjust=True`); the pair exists so a future provider serving raw closes
    can diverge honestly rather than silently redefining what the stored number
    means. `source` records the leaf provider that produced the row, so
    fabricated mock bars can never be read as real market data.
    """

    __tablename__ = "price_history_daily"
    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_price_history_ticker_date"),
        Index("ix_price_history_ticker_date", "ticker", "date"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    adj_close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    # CR164 — full OHLCV on the same adjusted basis as `adj_close` (the
    # provider serves auto_adjust=True bars, so o/h/l are adjusted too).
    # Nullable: pre-CR164 rows carry closes only. The as-of provider treats a
    # window containing any NULL-volume row as OHLCV-incomplete and serves
    # nothing rather than a half-real technicals input; target/stop-hit
    # scoring needs the daily high/low, backfilled by
    # `scripts/backfill_price_history.py`.
    open: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    high: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    low: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    volume: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class PortfolioNavDailyRow(Base):
    """One NAV snapshot per (user, run, US market day) — CR109 slice 1.

    Append-only, like `ShariaUniverseSnapshotRow`: a daily background tick
    writes one row per user per US market date and the read path resolves the
    whole stored series, never re-deriving history from `sim_trades`. It is
    the table the entire CR109 design rests on — the app's equity curve, and
    later the game's scored run, both read from here.

    `run_id` is NULL for the TRAINING portfolio, which is the only surface
    this slice writes. A real run UUID is a slice-2+ concern (a game run) —
    one table serves both without a schema change.

    FENCE — deliberately NOT foreign-keyed to `sim_portfolios`.
    `SimEngine.reset_portfolio()` hard-deletes the portfolio row and every
    `SimTradeRow`, and the replacement gets a brand-new UUID (destroy-and-
    recreate — the same shape `PortfolioValueSnapshotRow` already uses for
    CR136's Tier-2 history, and the reason THAT table is keyed to
    `portfolio_id` rather than `user_id`). A FK here would CASCADE the whole
    NAV history away on the player's first restart, which is the opposite of
    what a training or career record needs. Keyed on `user_id` + `run_id`
    instead — the same reset-immune shape `ReputationEventRow` already
    proves: a reset can empty the portfolio without erasing what it once did.

    `price_source` is `live` / `mock` / `stale`, carried from the mark that
    produced `nav` — CR040 degrade-loudly: a mock-priced day is WRITTEN and
    flagged, never silently absorbed into a curve that would then read as
    fact.

    `capital_event` (`open` / `restart` / `topup`, nullable) marks a row
    where NAV moved for a reason other than market performance.
    `trading_math/twr.py` splits the time-weighted-return chain at every such
    row, so a big loss followed by a reset reads as the loss it was rather
    than washing out against the fresh stake.
    """

    __tablename__ = "portfolio_nav_daily"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "run_id", "as_of_date", name="uq_nav_user_run_date",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    run_id: Mapped[Optional[UUID]] = mapped_column(Uuid(), index=True, nullable=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    cash: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    price_source: Mapped[str] = mapped_column(String, nullable=False)
    capital_event: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class GameFieldRow(Base):
    """A scheduled competitive window for the game — CR109 slice 2
    (implementation_plan.md §4.3 + §4.4.1 Amendment D). Columns and their
    meanings are specified verbatim there; not re-derived here.

    State machine: `announced -> entry_open -> locked -> live -> settling ->
    closed -> archived`, plus `abandoned` for a demand-gated field that
    never fills. **Slice 2 only ever writes `announced` / `entry_open` /
    `locked` / `live`** — settling/closing/archiving is slice 3, so this
    table's rows never advance past `live` yet. `scoring_basis` is resolved
    at CLOSE and frozen (slice 3); stays NULL through slice 2.

    No FK target from `sim_portfolios` or `portfolio_nav_daily` — only
    `game_entries` points here, and fields are never hard-deleted (§4.4),
    so that FK is safe.
    """

    __tablename__ = "game_fields"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    cadence: Mapped[str] = mapped_column(String, nullable=False, index=True)
    state: Mapped[str] = mapped_column(String, nullable=False, default="announced")
    entry_opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locks_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    min_entrants: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_wait_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scoring_basis: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    benchmark_ticker: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    entrant_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Amendment D (§4.4.1)
    kind: Mapped[str] = mapped_column(String, nullable=False, default="open")
    join_code: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    owner_user_id: Mapped[Optional[UUID]] = mapped_column(Uuid(), nullable=True)
    points_policy: Mapped[str] = mapped_column(String, nullable=False, default="full")
    theme: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class GameEntryRow(Base):
    """One user's entry into one `game_fields` row — CR109 slice 2
    (implementation_plan.md §4.4). Columns specified verbatim there.

    `run_id` joins to `portfolio_nav_daily` (NOT a FK — see that table's
    FENCE) and identifies the `SimPortfolioRow(kind="game")` this entry
    trades through. `UniqueConstraint(field_id, user_id)` is the DB-level
    backstop for "one entry per field per user"; combined with "at most one
    field is ever `entry_open` per cadence" (the weekly roll in
    `games_service.py`), that is also the one-live-run-per-cadence guard.
    """

    __tablename__ = "game_entries"
    __table_args__ = (
        UniqueConstraint("field_id", "user_id", name="uq_entry_field_user"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    field_id: Mapped[UUID] = mapped_column(
        Uuid(), ForeignKey("game_fields.id"), nullable=False, index=True,
    )
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    run_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False, default="entered")
    final_twr_pct: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    final_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    career_points_delta: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scored_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    intent: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    wildness_index: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    fees_paid: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # CR109 slice 3 — written once by the scoring pass (`games_scoring_pass.py`).
    # `void_reason` states loudly WHY a run is VOID (mock-priced day(s), named)
    # rather than leaving the client to infer it from the absence of a score
    # (CR040). `alpha_scored_pct` is what the ledger paid on (net of the one
    # entry fee — implementation_plan.md §6.6.2's achievable benchmark);
    # `alpha_display_pct` is the gross comparison the Close prints ("the index
    # pays no fees. You beat it anyway.") — stored SEPARATELY, never derived by
    # a client, because the whole point is that the two differ.
    void_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    alpha_scored_pct: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    alpha_display_pct: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    # The two private mirrors (design §10.4) — computed once in the scoring
    # pass, from data it already walks. FENCE: neither may ever appear in a
    # board or opponent-facing payload — see `games_record_service.py`'s
    # public/private serializer split and its enforcing test.
    counterfactual_hold_index_pct: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 4), nullable=True,
    )
    counterfactual_hold_first_picks_pct: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 4), nullable=True,
    )
    # The amount OF `career_points_delta` (below) that came from the finish
    # stipend specifically — 0 when this entry didn't claim it (zero trades,
    # forfeited, or another entry already claimed the cadence period).
    # `career_points_delta` itself is the TOTAL this entry netted (run_close/
    # void delta + stipend_points), so the Close can show one number without
    # a second query while the ledger (`career_events`) still holds the
    # granular, audit-grade breakdown.
    stipend_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class GameQueuedOrderRow(Base):
    """A game order placed outside US market hours — CR109 slice 2's
    queue-first path (design §5.1: "the primary flow, not the fallback").

    Not part of the plan's §4 schema — that section specifies `game_fields`
    / `game_entries` verbatim and is deliberately not re-derived here; this
    table fills a genuine gap the plan leaves open ("queued-order
    visibility" is listed under implementation_plan.md §10's still-open
    items, and the design's own G3/§5.1 assume queued orders exist without
    naming a table for them).

    Holds the order SPEC ONLY — never a captured price. The fill price is
    fetched fresh at drain time (`games_service.process_queued_orders`),
    which is what keeps a queued order from ever filling on a stale quote
    (implementation_plan.md §2 slice-2 acceptance).
    """

    __tablename__ = "game_queued_orders"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    order_type: Mapped[str] = mapped_column(String, nullable=False, default="market")
    limit_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    stop: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    target: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    horizon_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # queued / filled / cancelled
    state: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    filled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    filled_trade_id: Mapped[Optional[UUID]] = mapped_column(Uuid(), nullable=True)
    cancel_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class CareerEventRow(Base):
    """Append-only career-points ledger — CR109 slice 3
    (implementation_plan.md §4.5, Amendment D's clamp-at-write correction).

    Never a mutable running total anywhere: `SUM(delta)` for a user IS the
    displayed number, with NO clamp on read anywhere (`career_ledger.py`).
    `delta` is the amount actually APPLIED — clamped so the running sum can
    never go below zero on a debit, never clamped on a credit (there is no
    floor on the way up). `delta_uncapped` keeps the raw computed value for
    the audit trail (the Record's "given-back" total).

    `UniqueConstraint(entry_id, reason)` is the DEF039/DEF049 dedup shape —
    a re-run of the scoring pass cannot double-post the SAME entry's SAME
    reason. The partial unique index on `(user_id, period_key)` WHERE
    `reason = 'finish_stipend'` is the SEPARATE "once per cadence period,
    not once per entry" guard (design §6.5's fourth stipend condition) — it
    catches a second claim from a DIFFERENT entry in the same period, which
    the entry-scoped constraint above cannot see on its own.

    Amendment F (mandatory, CR109): `field_id`/`entry_id` are NOT NULL —
    a `career_events` row may never be written without both, because
    `field_id` is the only handle that makes cleaning dark-phase data
    possible later. `career_ledger.post_career_event` enforces this in code
    too (raises before ever building the row); this column constraint is
    the structural backstop that survives a caller forgetting to check.

    Both FKs are safe: neither `game_fields` nor `game_entries` rows are
    ever hard-deleted (implementation_plan.md §4.3/§4.4 — fields go
    `closed -> archived`, entries go `finished`/`forfeit`/`void`, never
    dropped).
    """

    __tablename__ = "career_events"
    __table_args__ = (
        UniqueConstraint("entry_id", "reason", name="uq_career_event_entry_reason"),
        Index(
            "uq_career_event_stipend_period",
            "user_id", "period_key",
            unique=True,
            postgresql_where=text("reason = 'finish_stipend'"),
            sqlite_where=text("reason = 'finish_stipend'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(), index=True, nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    delta_uncapped: Mapped[int] = mapped_column(Integer, nullable=False)
    # run_close / forfeit / forfeit_minimum / finish_stipend / duel
    # (implementation_plan.md §4.5) — slice 3 writes only the first and the
    # fourth; the rest are slice 3b/4 concerns and unreachable from this CR.
    reason: Mapped[str] = mapped_column(String, nullable=False)
    field_id: Mapped[UUID] = mapped_column(
        Uuid(), ForeignKey("game_fields.id"), nullable=False, index=True,
    )
    entry_id: Mapped[UUID] = mapped_column(
        Uuid(), ForeignKey("game_entries.id"), nullable=False, index=True,
    )
    # Only set on reason='finish_stipend' rows — see the partial index above.
    period_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class EdgarFactRow(Base):
    """One point-in-time XBRL fact from SEC EDGAR companyfacts (CR164).

    Production infrastructure, not a backtest-prefixed side table: this is the
    app's only filed-date-keyed fundamentals source, usable wherever a
    "knowable on date D" guarantee matters. `filed` is the leakage key — an
    as-of resolver may only read facts `filed <= as_of`; `period_end` says
    what period the value describes. Amendments (10-K/A) arrive as later
    `filed` rows for the same period and win by filed-ordering, never by
    overwrite — the table is append-only per accession.
    """

    __tablename__ = "edgar_facts"
    __table_args__ = (
        UniqueConstraint(
            "cik", "taxonomy", "tag", "unit", "period_end", "filed", "accession_no",
            name="uq_edgar_fact_identity",
        ),
        Index("ix_edgar_facts_ticker_tag_filed", "ticker", "tag", "filed"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    cik: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    taxonomy: Mapped[str] = mapped_column(String, nullable=False)  # us-gaap | dei
    tag: Mapped[str] = mapped_column(String, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)  # USD | shares | USD/shares
    value: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    fy: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fp: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # FY | Q1..Q4
    form: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    filed: Mapped[date] = mapped_column(Date, nullable=False)
    accession_no: Mapped[str] = mapped_column(String, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class NewsArchiveRow(Base):
    """Reserved store for point-in-time news (CR164) — EMPTY in v1.

    Created with the CR164 schema so a later historical-news arm (Alpha
    Vantage NEWS_SENTIMENT `time_from`/`time_to`, GDELT) ingests without a
    migration. `published_at` is the as-of cutoff key. No production code
    reads this table yet; the v1 backtest runs the News analyst ablated.
    """

    __tablename__ = "news_archive"
    __table_args__ = (
        UniqueConstraint(
            "ticker", "source", "url", "published_at", name="uq_news_archive_item",
        ),
        Index("ix_news_archive_ticker_pub", "ticker", "published_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    publisher: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    raw: Mapped[Optional[dict]] = mapped_column(JsonB(), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class BacktestRunIndexRow(Base):
    """Harness bookkeeping: one row per backtest Room run (CR164).

    Joins `room_runs.id` (no FK, per `portfolio_nav_daily` precedent — the
    index must survive a room_runs archive/prune). The unique constraint IS
    the sweep's idempotency mechanism: the runner's dedup tiers are bypassed
    under an as-of context (they exist to stop mobile-retry double-billing),
    so a driver retry of a completed (batch, ticker, as_of) pair fails here
    loudly and the driver skips. Scoring joins through this table, and
    real-user analytics exclude anything present in it.
    """

    __tablename__ = "backtest_run_index"
    __table_args__ = (
        UniqueConstraint("batch_id", "ticker", "as_of", name="uq_backtest_run"),
        Index("ix_backtest_run_batch", "batch_id"),
    )

    room_run_id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True)
    batch_id: Mapped[str] = mapped_column(String, nullable=False)
    arm: Mapped[str] = mapped_column(String, nullable=False)
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )


class BacktestUniverseMembershipRow(Base):
    """The survivorship audit (CR164): per (universe, ticker), when the name
    was actually tradeable in the backtest window and why it is excluded when
    it is. `tickers_150.txt` was screened 2026-07 from live names — using it
    at earlier as-of dates embeds survivorship unless membership is audited
    and the exclusion counts are published verbatim with every report.
    """

    __tablename__ = "backtest_universe_membership"
    __table_args__ = (
        UniqueConstraint("universe_id", "ticker", name="uq_backtest_universe"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    universe_id: Mapped[str] = mapped_column(String, nullable=False)
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    eligible_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    eligible_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # listed_after_asof | delisted_in_window | insufficient_candles | NULL (clean)
    exclusion_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    noted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
