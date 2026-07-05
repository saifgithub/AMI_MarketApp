# Data Model

Postgres schema, managed via Alembic. **This doc mirrors the tables
actually shipped in `backend/app/db/models.py` and the Alembic migration
chain — not the aspirational MVP shape.** Tables that were specced for
later phases (Beta/MVP) are listed under "Not yet delivered" at the
bottom.

## Storage realities (Alpha)

- **One Postgres instance** on melehost (`ami_postgres` Docker service). No Supabase yet — the swap-over plan lives in [`hosting.md`](hosting.md).
- **No RLS yet.** Postgres row-level security policies will land when Supabase plugs in; today we run behind a single trusted backend. The `models.py` header documents this explicitly.
- **JSONB portable shim.** ORM uses `JsonB()` from `app/db/base.py` — maps to native `JSONB` on Postgres and falls back to `JSON` on SQLite (so unit tests run on a tempfile DB).
- **Money columns** are `NUMERIC(12, n)` on Postgres, `Float` on SQLite. `n=2` for cash balances, `n=4` for share quantities + entry prices.
- **UUID columns** are native `UUID` on Postgres, `CHAR(36)` on SQLite via the `Uuid()` shim.
- **Migrations**: Alembic, files in `backend/alembic/versions/`. Each migration is reversible where practical. See [Migrations](#migrations) section.

## Tables overview

Eighteen tables in Alpha. Sizes are 10K-MAU projections.

| Table | Purpose | Size (10K MAU) |
|---|---|---|
| `users` | Identity + plan + trial + suspension state | ~10K rows |
| `mandates` | Versioned mandate snapshots (JSONB blob, not normalized) | ~20K rows |
| `agent_activations` | Which agents each user has unlocked + how | ~120K rows |
| `user_overlays` | Brief Your Agent overlays, per (user, agent), versioned | ~50K rows |
| `overlay_edit_counts` | Per (user, agent) lifetime accepted-edit count (for tier caps) | ~120K rows |
| `room_runs` | Convene the Room sessions + verdict | ~50K rows / mo |
| `journal_entries` | Decision Journal (Rooms + 1-on-1 + sim + mandate-edit + agent-coach) with soft-delete | ~600K rows / mo |
| `lessons_progress` | Per (user, lesson) state — started_at, completed_at, quiz scores | ~500K rows |
| `sim_portfolios` | One per user (unique constraint) | ~10K rows |
| `sim_holdings` | Open positions, per (portfolio, ticker) | ~100K rows |
| `sim_trades` | Full sim trade ledger — entry, stop, target, status, closed_price, realised P&L | ~100K rows / mo |
| `sim_watchlists` | User-curated watchlist tickers + notes | ~30K rows |
| `bug_reports` | In-app bug reports (shake gesture) + optional photo attachment + assigned-branch coordination | ~5K rows |
| `auth_challenges` | One-time codes for magic-link + Apple OIDC exchange (hashed) | ~50K rows / mo |
| `llm_audit` | Every LLM gateway call — full prompt + response + tier + provider + latency | ~5M rows / mo |
| `http_audit` | Every inbound HTTP request — bodies truncated, auth headers scrubbed at middleware | ~10M rows / mo |
| `one_on_one_messages` | Durable per-turn record of every 1-on-1 chat (Concierge + 12 agents) | ~500K rows / mo |
| `subscription_events` | Audit trail for plan / credit / trial / suspension changes (admin + app + revenuecat) | ~30K rows / mo |

## Core schema

### `users`

Identity + entitlements. Trial dates only populated via the admin grant
endpoint today (the auto-populate on claim is deferred — see BL3).
Single device per user via `device_user_id`; multi-device is BL2.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE,
    phone TEXT UNIQUE,
    apple_id TEXT,
    google_id TEXT,
    hms_unionid TEXT,
    display_name TEXT,            -- set on first OIDC auth (Apple full_name);
                                  -- minimum-data policy, never overwritten

    plan TEXT NOT NULL DEFAULT 'floor_pass',
    -- 'floor_pass' | 'trader' | 'floor_manager' | 'trial_trader'
    credit_balance INTEGER NOT NULL DEFAULT 0,
    locale TEXT NOT NULL DEFAULT 'en',
    timezone TEXT NOT NULL DEFAULT 'UTC',

    is_anonymous BOOLEAN NOT NULL DEFAULT TRUE,
    anonymous_session_started_at TIMESTAMPTZ,
    claimed_at TIMESTAMPTZ,
    device_user_id UUID,          -- stable per-device id from shared_preferences

    trial_started_at TIMESTAMPTZ,
    trial_expires_at TIMESTAMPTZ,
    suspended_at TIMESTAMPTZ,     -- admin-only flag; NULL = active

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_device_user_id ON users(device_user_id);
```

**Not yet shipped on `users`:** `reputation`, `free_one_on_ones_used_this_period`,
`free_rooms_used_this_period`, `period_resets_at`, `deleted_at`. These are
specced in earlier drafts; entitlement metering currently runs off
`subscription_events` aggregation, and deletion is hard-delete until GDPR/PDPL
flow ships at MVP.

### `mandates`

**Denormalized JSONB snapshot, not normalized columns.** The full Pydantic
`Mandate` (see `app/schemas/mandate.py` + [`mandate_schema.md`](../03_onboarding/mandate_schema.md))
is written as a single blob per version. Each PATCH writes a new row so
we can reconstruct any historic mandate exactly.

```sql
CREATE TABLE mandates (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    version INTEGER NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    snapshot JSONB NOT NULL,       -- full Pydantic Mandate.model_dump()
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, version)
);

CREATE INDEX idx_mandates_user_id ON mandates(user_id);
```

The historical doc described `mandates` as a normalized table with one column
per mandate field (`display_name`, `locale`, `primary_goal`, `risk_components`, etc.).
That shape is the **Pydantic** model. The on-disk row is one JSONB blob —
the trade-off was fast iteration during onboarding development. Normalization
is a Beta candidate if reporting needs it.

### `agent_activations`

Tracks which of the 12 agents a user has unlocked. `triggering_lesson_id`
captures the Agent Academy lesson that activated it (when activation came
via the lessons path).

```sql
CREATE TABLE agent_activations (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    agent_id TEXT NOT NULL,
    activation_method TEXT NOT NULL,
    -- 'earn_path' | 'skip_path' | 'trial' | 'founder_grant'
    triggering_lesson_id TEXT,
    activated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, agent_id)
);

CREATE INDEX idx_agent_activations_user_id ON agent_activations(user_id);
```

**Not yet shipped:** `earn_path_completed_at`, `skip_path_valid_until`. The
single `activated_at` + `activation_method` covers Alpha needs; the
"skip path expires" mechanic is MVP scope.

### `user_overlays` + `overlay_edit_counts`

Brief Your Agent overlays. Versioned per (user, agent). The accepted-edit
counter lives in a separate table so it survives retention drops of old
versions (Floor-Pass tier write caps).

```sql
CREATE TABLE user_overlays (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    agent_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,             -- overlay markdown
    plain_english TEXT NOT NULL,       -- for the version history UI
    based_on_session UUID,             -- FK to the Brief session (in-memory; no table yet)
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, agent_id, version)
);

CREATE INDEX idx_user_overlays_user_id ON user_overlays(user_id);

CREATE TABLE overlay_edit_counts (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    agent_id TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    UNIQUE (user_id, agent_id)
);

CREATE INDEX idx_overlay_edit_counts_user_id ON overlay_edit_counts(user_id);
```

**Naming note:** the column is `is_active`, not `is_current` (earlier drafts).
`based_on_session` (not `based_on_brief_session`).

### `room_runs`

Convene the Room sessions. Transcript + verdict captured as JSONB so we
can replay any past run without re-invoking the LLM.

```sql
CREATE TABLE room_runs (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    ticker TEXT NOT NULL,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,

    mandate_version INTEGER NOT NULL,
    model_tier TEXT NOT NULL,
    rounds INTEGER NOT NULL DEFAULT 1,

    transcript JSONB NOT NULL DEFAULT '[]'::jsonb,
    verdict JSONB,                 -- {action, size_pct, entry, target, stop, reason, ...}

    credit_cost INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'running',
    -- 'running' | 'completed' | 'failed' | 'cancelled'
    error_message TEXT,
    duration_ms INTEGER
);

CREATE INDEX idx_room_runs_user_id ON room_runs(user_id);
CREATE INDEX idx_room_runs_ticker ON room_runs(ticker);
```

### `journal_entries`

Unified entry table — Room runs, 1-on-1s, sim trades, mandate edits,
brief accepts. Polymorphic via `entry_type`. Soft-deleted entries
(`deleted_at IS NOT NULL`) stay in the table for restore; live list
queries filter them out.

```sql
CREATE TABLE journal_entries (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    entry_type TEXT NOT NULL,
    -- 'room_run' | 'one_on_one' | 'sim_trade' | 'mandate_edit' |
    -- 'agent_coach' | 'drift_alert' | 'lesson_complete' | 'agent_unlock'

    reference_id UUID,             -- FK-ish to room_runs.id / sim_trades.id / etc.

    title TEXT NOT NULL,
    summary TEXT,
    ticker TEXT,
    agents_involved JSONB NOT NULL DEFAULT '[]'::jsonb,
    mandate_version INTEGER NOT NULL DEFAULT 1,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    user_note TEXT,
    outcome TEXT,                  -- 'win' | 'loss' | 'pending' | NULL
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,   -- full snapshot for replay

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ                          -- soft delete
);

CREATE INDEX idx_journal_user_id ON journal_entries(user_id);
CREATE INDEX idx_journal_user_created ON journal_entries(user_id, created_at DESC);
CREATE INDEX idx_journal_ticker ON journal_entries(ticker);
CREATE INDEX idx_journal_type ON journal_entries(entry_type);
CREATE INDEX idx_journal_deleted_at ON journal_entries(deleted_at);
```

**Naming note:** `agents_involved` and `tags` are JSONB arrays (not native
Postgres `TEXT[]`) so the SQLite-portable `JsonB()` shim can carry them.
`payload` is the full before/after snapshot used for replay (mandate
edits) or transcript embedding (room runs without a separate `room_runs`
row reference).

### `lessons_progress`

Per (user, lesson) state. No separate `academy_progress` table — agent
Academy modules live in this same table tagged by `lesson_id`.

```sql
CREATE TABLE lessons_progress (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    lesson_id TEXT NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    quiz_attempts INTEGER NOT NULL DEFAULT 0,
    quiz_passed BOOLEAN NOT NULL DEFAULT FALSE,
    last_quiz_score FLOAT,
    UNIQUE (user_id, lesson_id)
);

CREATE INDEX idx_lessons_progress_user_id ON lessons_progress(user_id);
```

### `sim_portfolios` + `sim_holdings` + `sim_trades`

Single portfolio per user (UNIQUE on `sim_portfolios.user_id`).
Multi-portfolio is a Floor Manager feature deferred to MVP.

```sql
CREATE TABLE sim_portfolios (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL UNIQUE,        -- one portfolio per user in Alpha
    name TEXT NOT NULL DEFAULT 'Main',
    starting_capital NUMERIC(12,2) NOT NULL,
    current_cash NUMERIC(12,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE sim_holdings (
    id UUID PRIMARY KEY,
    portfolio_id UUID NOT NULL REFERENCES sim_portfolios(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    quantity NUMERIC(12,4) NOT NULL,
    avg_cost NUMERIC(12,4) NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (portfolio_id, ticker)
);

CREATE TABLE sim_trades (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,                          -- denormalized for fast list
    portfolio_id UUID NOT NULL REFERENCES sim_portfolios(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,                             -- 'buy' | 'sell'
    quantity NUMERIC(12,4) NOT NULL,
    entry_price NUMERIC(12,4) NOT NULL,
    stop NUMERIC(12,4),
    target NUMERIC(12,4),
    horizon_days INTEGER,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    closed_price NUMERIC(12,4),
    status TEXT NOT NULL DEFAULT 'open',            -- 'open' | 'closed' | 'stopped' | 'cancelled'
    verdict_ref UUID,                               -- FK-ish to the Room verdict that justified the trade
    realised_pnl NUMERIC(12,2) NOT NULL DEFAULT 0
);

CREATE INDEX idx_sim_trades_user_id ON sim_trades(user_id);
CREATE INDEX idx_sim_trades_ticker ON sim_trades(ticker);
```

**Naming note:** the trade column is `entry_price` (not `price`),
`verdict_ref` (not `related_room_run_id`), and the full open→stop→target→close
lifecycle lives in the same row rather than separate execution events.
`user_id` is denormalized onto `sim_trades` (in addition to `portfolio_id`)
so the list endpoint can filter without a join.

### `sim_watchlists`

```sql
CREATE TABLE sim_watchlists (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    ticker TEXT NOT NULL,
    notes TEXT,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, ticker)
);

CREATE INDEX idx_sim_watchlists_user_id ON sim_watchlists(user_id);
```

### `bug_reports`

In-app bug reports — shake-gesture / long-press trigger. `user_id` is
nullable so anonymous sessions can file reports before the anon
bootstrap completes. `assigned_branch` coordinates parallel `/fix-bugs`
sessions: the UPDATE that sets `status='in_progress'` also writes the
branch name in the same statement, so two sessions can't both claim
the same `open` bug.

```sql
CREATE TABLE bug_reports (
    id UUID PRIMARY KEY,
    user_id UUID,                            -- nullable for pre-anon-bootstrap reports
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    steps TEXT,
    route TEXT,
    app_version TEXT NOT NULL,
    platform TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',     -- 'open' | 'in_progress' | 'awaiting_merge' | 'closed'
    assigned_branch TEXT,                    -- claimed by a fix-bug session
    attachment_path TEXT,                    -- relative path under bug_attachments_dir
    attachment_mime VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_bug_reports_user_id ON bug_reports(user_id);
```

### `auth_challenges`

One-time codes for magic-link + Apple OIDC exchange. Stored hashed;
consumed once on verify. Goes away when Supabase Auth plugs in
(MVP migration).

```sql
CREATE TABLE auth_challenges (
    id UUID PRIMARY KEY,
    kind TEXT NOT NULL,                      -- 'magic_link' | 'apple'
    target TEXT NOT NULL,                    -- email or Apple sub
    code_hash TEXT NOT NULL,
    user_id UUID,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_auth_challenges_target ON auth_challenges(target);
```

### `llm_audit`

Every LLM gateway call. Full prompt + full response captured for Alpha
triage. Retention is unbounded until tester count grows.

```sql
CREATE TABLE llm_audit (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id UUID,
    agent_id TEXT,
    flow TEXT,                               -- 'room' | 'brief' | 'one_on_one' | 'onboarding' | 'translate' | ...
    tier TEXT NOT NULL,                      -- 'cheap' | 'mid' | 'premium'
    provider TEXT NOT NULL,                  -- 'vllm' | 'anthropic' | 'mock'
    locale TEXT,
    system_prompt TEXT NOT NULL,
    messages JSONB NOT NULL DEFAULT '[]'::jsonb,
    response_text TEXT,
    latency_ms INTEGER,
    error TEXT
);

CREATE INDEX idx_llm_audit_created_at ON llm_audit(created_at);
CREATE INDEX idx_llm_audit_user_id ON llm_audit(user_id);
```

This replaces the earlier `llm_calls` spec. No partitioning yet —
volume is bounded by gateway calls (~10/active session), not by HTTP
request count. Monthly partitions are an MVP candidate.

### `http_audit`

Every inbound HTTP request. Bodies captured truncated. Auth headers
scrubbed at the middleware layer — never reach this table.

```sql
CREATE TABLE http_audit (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    query TEXT,
    user_id UUID,
    client_ip TEXT,
    status_code INTEGER NOT NULL,
    request_body TEXT,
    response_body TEXT,
    response_truncated BOOLEAN NOT NULL DEFAULT FALSE,
    is_streaming BOOLEAN NOT NULL DEFAULT FALSE,
    latency_ms INTEGER NOT NULL
);

CREATE INDEX idx_http_audit_created_at ON http_audit(created_at);
CREATE INDEX idx_http_audit_path ON http_audit(path);
CREATE INDEX idx_http_audit_user_id ON http_audit(user_id);
```

### `one_on_one_messages`

Durable record of every 1-on-1 chat turn (Concierge + 12 agents). The
`agent_runner` streams via SSE and currently keeps no server-side
record; this table closes the gap so any conversation can be replayed.

```sql
CREATE TABLE one_on_one_messages (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL,
    user_id UUID NOT NULL,
    agent_id TEXT NOT NULL,
    role TEXT NOT NULL,                      -- 'user' | 'agent' | 'system'
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_one_on_one_messages_session_id ON one_on_one_messages(session_id);
CREATE INDEX idx_one_on_one_messages_user_id ON one_on_one_messages(user_id);
```

No dedicated `one_on_one_sessions` table — session state is held in
memory in the `agent_runner`; the durable record is just the messages.

### `subscription_events`

Complete audit trail for every plan / credit / trial / suspension
change. Every admin write and every app-side credit consumption
produces a row. RevenueCat webhook will write `revenuecat_purchase`
rows once that integration ships.

```sql
CREATE TABLE subscription_events (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    -- 'plan_change' | 'trial_grant' | 'trial_extend' | 'credit_grant' |
    -- 'credit_deduct' | 'credits_consumed' | 'suspend' | 'reinstate' |
    -- 'revenuecat_purchase' (MVP)
    from_value TEXT,
    to_value TEXT,
    source TEXT NOT NULL,                    -- 'admin_override' | 'app' | 'revenuecat'
    admin_id UUID,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_subscription_events_user_id ON subscription_events(user_id);
CREATE INDEX idx_subscription_events_created_at ON subscription_events(created_at);
```

This replaces the earlier `credit_transactions` spec — `subscription_events`
covers credit movement under `event_type='credit_grant' / 'credit_deduct' /
'credits_consumed'`, plus everything else admin can do to a user. The
`credits_consumed` event type is wired on the admin write path but the
app-side credit spend hook isn't emitting it yet (see project_plan.md
BL row on credit consumption events).

## Pydantic models

All schemas live in `backend/app/schemas/*.py`. The source files are the
canonical Pydantic definitions — this doc references them rather than
duplicating, because the Pydantic shape drifts faster than markdown
can keep up.

- `app/schemas/auth.py` — `AuthUser`, `AnonSessionRequest/Response`, magic-link + Apple verify
- `app/schemas/mandate.py` — full `Mandate` + nested `Compliance`, `RiskComponents`, `DailyBriefing`, `TargetOutcome`
- `app/schemas/brief.py` — `BriefSession`, `BriefProposal`, `BriefRefusal`, `UserOverlay`, history
- `app/schemas/onboarding.py` — `OnboardingSession`, question/answer types
- `app/schemas/room.py` — `RoomRun`, `AgentMessage`, `Verdict`
- `app/schemas/sim.py` — `PortfolioSnapshot`, `SimTrade`, holdings
- `app/schemas/journal.py` — `JournalEntry`, `JournalEntryCreate`, `EntryType`, `Outcome`
- `app/schemas/lessons.py` — `Lesson`, `LessonStatus`, `LessonCatalogue`, `ProgressSummary`, `QuizSubmitResponse`
- `app/schemas/watchlist.py`, `app/schemas/feedback.py`, `app/schemas/admin.py`, etc.

## Migrations

Alembic, files in `backend/alembic/versions/`. Chain so far (oldest first):

| Migration file | Adds |
|---|---|
| `e355c2468b2a_initial_schema.py` | All core tables: `users`, `mandates`, `user_overlays`, `overlay_edit_counts`, `agent_activations`, `journal_entries`, `lessons_progress`, `sim_portfolios`, `sim_holdings`, `sim_trades`, `room_runs`, `auth_challenges` |
| `a4c7e9d10001_rls_policies.py` | (Placeholder — RLS policies for the eventual Supabase swap; not yet enforced in Alpha.) |
| `b5e1f3c20002_sim_watchlists.py` | `sim_watchlists` table |
| `c7f2a1d30003_bug_reports.py` | `bug_reports` table |
| `d8a3e9f40004_audit_tables.py` | `llm_audit`, `http_audit`, `one_on_one_messages` |
| `f7d9b2e60005_journal_soft_delete.py` | `journal_entries.deleted_at` |
| `a9d1c7e80006_admin_backoffice.py` | `users.{trial_started_at, trial_expires_at, suspended_at}` + `subscription_events` |
| `a8e3c1b50006_bug_reports_assigned_branch.py` | `bug_reports.assigned_branch` |
| `b1c4e8d70007_bug_attachment.py` | `bug_reports.{attachment_path, attachment_mime}` |
| `b3f9d2a80007_users_display_name.py` | `users.display_name` |

Each migration is reversible where practical. New migrations run on
container start via the `alembic upgrade head` step in
`infra/docker/api/entrypoint.sh`.

## Backups

Alpha: Postgres on melehost — `pg_dump` to a host-side volume every
night, retained 7 days. No off-platform redundancy yet.

MVP target: Supabase Pro automatic daily backups + weekly `pg_dump`
to GCS.

## Performance considerations

| Concern | Strategy |
|---|---|
| **Journal by user × ticker** | `idx_journal_user_id` + `idx_journal_ticker`. Composite index a candidate if list-by-ticker becomes hot. |
| **agent_activations check on every Room run** | Read once per session, cached in app memory; invalidated on activation events. |
| **`llm_audit` + `http_audit` volume** | No partitioning yet. Will partition by month at MVP when tester count grows. |
| **Journal pruning for Floor Pass** | Specced (30-day retention) but **not yet wired**. Background job is MVP scope. |
| **Soft-delete cleanup** | `deleted_at IS NOT NULL` rows currently stay forever. Hard-purge after 30 days is a MVP backlog item. |
| **Real-time subscriptions** | Not delivered. SSE-only today; Supabase Realtime channels are MVP. |

## Not yet delivered

Tables that were specced in earlier drafts but never created in any
migration. Listed here so future sessions can see at a glance what's
real vs aspirational.

| Specced table | Status | Note |
|---|---|---|
| `one_on_one_sessions` | Replaced | Session state held in memory in `agent_runner`. `one_on_one_messages` is the durable record. |
| `academy_progress` | Replaced | Lives inside `lessons_progress` tagged by `lesson_id` (Agent Academy modules are lessons with an agent-id prefix). |
| `daily_challenges` | Deferred | Today the daily challenges are served from a static manifest, not a table. Database-backed catalogue is a backlog item for when content rotates per locale. |
| `daily_challenge_attempts` | Deferred | Attempts captured as `journal_entries` with `entry_type='daily_challenge'` today; dedicated table once tracking gets richer (streaks, leaderboards). |
| `streaks` | Deferred | Derived from `lessons_progress` aggregation today. Materialized streak table is a Beta candidate. |
| `briefings` | Deferred to MVP | Morning briefing generation hasn't shipped yet (specced for full-shakedown Stream 3 in `project_plan.md`). |
| `drift_alerts` | Deferred to MVP | Drift detection runs as a background job — output landing in `journal_entries` with `entry_type='drift_alert'` is the shipped path. Dedicated alerts table tracks suppression + ack at MVP. |
| `brief_sessions` | Replaced | Brief sessions are in-memory (lifetime of the conversation). The durable artefact is the `user_overlays` row written on accept + the `agent_coach` journal entry. |
| `offers_redemptions` | Deferred to MVP | Promo offers ship with billing namespace. |
| `audit_log` | Replaced | Split into three purpose-specific audit tables: `http_audit`, `llm_audit`, `subscription_events`. No single unified `audit_log`. |
| `credit_transactions` | Replaced | Subsumed by `subscription_events` (event_type='credit_*'). The Floor-Pass period-reset counters (`free_one_on_ones_used_this_period` etc.) on `users` are also not yet shipped. |
| `llm_calls` (partitioned) | Replaced | `llm_audit` covers the same data unpartitioned. Monthly partitioning is an MVP performance candidate. |

## Cross-references

- Mandate full schema: [`mandate_schema.md`](../03_onboarding/mandate_schema.md)
- API endpoints that consume this: [`api_design.md`](api_design.md)
- Auth + (future) RLS: [`auth.md`](auth.md)
- Backend hosting + Postgres deployment: [`hosting.md`](hosting.md)
- Project plan + backlog: [`../10_delivery/project_plan.md`](../10_delivery/project_plan.md)
