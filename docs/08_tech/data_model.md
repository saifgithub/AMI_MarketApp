# Data Model

Postgres schema (via Supabase). Every table has Row-Level Security (RLS) enabled.

## Tables overview

| Table | Purpose | Size estimate (10K MAU) |
|---|---|---|
| `users` | Identity + plan + trial state | ~10K rows |
| `mandates` | User mandates, versioned | ~20K rows |
| `agent_activations` | Which agents each user has unlocked | ~120K rows |
| `user_overlays` | Coach Your Agent prompt customisations | ~50K rows |
| `room_runs` | Convene the Room sessions | ~50K rows / mo |
| `one_on_one_sessions` | 1-on-1 chat sessions | ~500K rows / mo |
| `journal_entries` | Decision Journal entries (Rooms + 1-on-1 + sim trades + mandate edits) | ~600K rows / mo |
| `sim_portfolios` | User sim portfolios | ~15K rows |
| `sim_holdings` | Positions held in sim portfolios | ~100K rows |
| `sim_trades` | Sim trade ledger | ~100K rows / mo |
| `credit_transactions` | Every credit movement | ~1M rows / mo |
| `llm_calls` | Per-LLM-call records (cost, model, latency) | ~5M rows / mo (consider partition) |
| `lessons_progress` | Per-user lesson completion state | ~500K rows |
| `academy_progress` | Per-user Agent Academy progress | ~120K rows |
| `daily_challenges` | Per-locale daily challenges (cached) | ~3 rows / day |
| `daily_challenge_attempts` | Per-user attempts | ~300K rows / mo |
| `streaks` | Per-user streak state | ~10K rows |
| `briefings` | Generated morning briefings | ~300K rows / mo |
| `drift_alerts` | Mandate drift alerts | ~50K rows / mo |
| `coach_sessions` | Coach Your Agent sessions | ~50K rows / mo |
| `offers_redemptions` | Promo offer usage | ~10K rows |
| `audit_log` | All sensitive actions | ~100K rows / mo |

## Core schema (key tables)

### `users`

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT auth.uid(),
    email TEXT UNIQUE,
    phone TEXT UNIQUE,
    hms_unionid TEXT UNIQUE,
    apple_id TEXT,
    google_id TEXT,
    
    plan TEXT NOT NULL DEFAULT 'floor_pass',
    -- 'floor_pass', 'trader', 'floor_manager', 'trial_trader'
    trial_started_at TIMESTAMPTZ,
    trial_expires_at TIMESTAMPTZ,
    
    credit_balance INTEGER NOT NULL DEFAULT 0,
    free_one_on_ones_used_this_period INTEGER DEFAULT 0,
    free_rooms_used_this_period INTEGER DEFAULT 0,
    period_resets_at TIMESTAMPTZ,
    
    reputation INTEGER NOT NULL DEFAULT 0,
    
    locale TEXT NOT NULL DEFAULT 'en',
    timezone TEXT NOT NULL DEFAULT 'UTC',
    
    is_anonymous BOOLEAN DEFAULT FALSE,
    anonymous_session_started_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_users_plan ON users(plan);
CREATE INDEX idx_users_trial_expires ON users(trial_expires_at) WHERE trial_expires_at IS NOT NULL;

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY users_self ON users USING (id = auth.uid());
```

### `mandates`

See [`docs/03_onboarding/mandate_schema.md`](../03_onboarding/mandate_schema.md) for the full definition.

```sql
CREATE TABLE mandates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    
    display_name TEXT NOT NULL,
    locale TEXT NOT NULL,
    timezone TEXT NOT NULL,
    primary_goal TEXT NOT NULL,
    horizon TEXT NOT NULL,
    target_outcome JSONB,
    path TEXT NOT NULL,
    risk_score SMALLINT NOT NULL CHECK (risk_score BETWEEN 1 AND 5),
    risk_components JSONB NOT NULL,
    risk_quotes JSONB DEFAULT '[]'::jsonb,
    max_drawdown_pct SMALLINT NOT NULL,
    compliance JSONB NOT NULL,
    learning_style TEXT NOT NULL,
    daily_briefing JSONB NOT NULL,
    
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (user_id, version)
);

CREATE UNIQUE INDEX idx_mandate_current_per_user ON mandates(user_id) WHERE is_current = TRUE;

ALTER TABLE mandates ENABLE ROW LEVEL SECURITY;
CREATE POLICY mandates_self ON mandates USING (user_id = auth.uid());
```

### `agent_activations`

```sql
CREATE TABLE agent_activations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id TEXT NOT NULL,
    
    activation_method TEXT NOT NULL,
    -- 'earn_path' | 'skip_path' | 'trial' | 'founder_grant'
    activated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    earn_path_completed_at TIMESTAMPTZ,
    skip_path_valid_until TIMESTAMPTZ,
    
    UNIQUE (user_id, agent_id)
);

ALTER TABLE agent_activations ENABLE ROW LEVEL SECURITY;
CREATE POLICY agent_activations_self ON agent_activations USING (user_id = auth.uid());
```

### `user_overlays`

```sql
CREATE TABLE user_overlays (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    
    content TEXT NOT NULL,                -- the overlay markdown
    plain_english TEXT NOT NULL,          -- for the version history UI
    based_on_coach_session UUID,
    
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (user_id, agent_id, version)
);

CREATE UNIQUE INDEX idx_overlay_current ON user_overlays(user_id, agent_id) WHERE is_current = TRUE;

ALTER TABLE user_overlays ENABLE ROW LEVEL SECURITY;
CREATE POLICY user_overlays_self ON user_overlays USING (user_id = auth.uid());
```

### `room_runs`

```sql
CREATE TABLE room_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    ticker TEXT NOT NULL,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    
    mandate_version INTEGER NOT NULL,
    model_tier TEXT NOT NULL,
    rounds INTEGER NOT NULL DEFAULT 1,
    
    transcript JSONB NOT NULL DEFAULT '[]'::jsonb,
    verdict JSONB,
    -- {action: APPROVE|REJECT|MODIFY, size_pct, entry, target, stop, reason, ...}
    
    credit_cost INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    -- running | completed | failed | cancelled
    
    error_message TEXT,
    duration_ms INTEGER
);

CREATE INDEX idx_room_runs_user ON room_runs(user_id, triggered_at DESC);

ALTER TABLE room_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY room_runs_self ON room_runs USING (user_id = auth.uid());
```

### `journal_entries`

Unified table covering Room runs, 1-on-1s, sim trades, and mandate edits. Polymorphic via `entry_type`.

```sql
CREATE TABLE journal_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    entry_type TEXT NOT NULL,
    -- 'room_run' | 'one_on_one' | 'sim_trade' | 'mandate_edit' | 'agent_coach' | 'drift_alert'
    
    reference_id UUID,
    -- FK to room_runs.id / one_on_one_sessions.id / sim_trades.id / etc.
    
    title TEXT NOT NULL,
    summary TEXT,
    
    ticker TEXT,                          -- if relevant
    agents_involved TEXT[],               -- agent IDs
    
    mandate_version INTEGER NOT NULL,
    tags TEXT[] DEFAULT '{}',
    user_note TEXT,
    
    outcome TEXT,
    -- 'win' | 'loss' | 'pending' | null
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_journal_user ON journal_entries(user_id, created_at DESC);
CREATE INDEX idx_journal_user_ticker ON journal_entries(user_id, ticker);
CREATE INDEX idx_journal_user_type ON journal_entries(user_id, entry_type);

-- Floor Pass users have 30-day retention enforced by background job
CREATE INDEX idx_journal_cleanup ON journal_entries(created_at) WHERE created_at < (NOW() - INTERVAL '30 days');

ALTER TABLE journal_entries ENABLE ROW LEVEL SECURITY;
CREATE POLICY journal_self ON journal_entries USING (user_id = auth.uid());
```

### `sim_portfolios` + `sim_holdings` + `sim_trades`

```sql
CREATE TABLE sim_portfolios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    starting_capital DECIMAL(12,2) NOT NULL,
    current_cash DECIMAL(12,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE sim_holdings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES sim_portfolios(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    quantity DECIMAL(12,4) NOT NULL,
    avg_cost DECIMAL(12,4) NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (portfolio_id, ticker)
);

CREATE TABLE sim_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES sim_portfolios(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,    -- 'buy' | 'sell'
    quantity DECIMAL(12,4) NOT NULL,
    price DECIMAL(12,4) NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pm_decision JSONB,     -- the PM compliance check that approved this trade
    related_room_run_id UUID REFERENCES room_runs(id)
);

ALTER TABLE sim_portfolios ENABLE ROW LEVEL SECURITY;
CREATE POLICY sim_self ON sim_portfolios USING (user_id = auth.uid());
-- Similar policies for sim_holdings and sim_trades (via portfolio_id → user_id join)
```

### `credit_transactions`

```sql
CREATE TABLE credit_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    type TEXT NOT NULL,
    -- 'monthly_grant' | 'purchase' | 'spend' | 'refund' | 'founder_grant' | 'streak_bonus' | 'referral_reward'
    amount INTEGER NOT NULL,        -- positive for inflow, negative for spend
    balance_after INTEGER NOT NULL,
    
    operation_ref UUID,
    operation_type TEXT,            -- 'room_run' | 'one_on_one' | etc.
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_credits_user ON credit_transactions(user_id, created_at DESC);

ALTER TABLE credit_transactions ENABLE ROW LEVEL SECURITY;
CREATE POLICY credits_self ON credit_transactions USING (user_id = auth.uid());
```

### `llm_calls`

High-volume table. Partition by month.

```sql
CREATE TABLE llm_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    operation_type TEXT NOT NULL,
    operation_ref UUID,
    
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd DECIMAL(10,6) NOT NULL,
    latency_ms INTEGER NOT NULL,
    
    success BOOLEAN NOT NULL,
    error_message TEXT,
    
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL
) PARTITION BY RANGE (started_at);

-- Create monthly partitions
CREATE TABLE llm_calls_2026_06 PARTITION OF llm_calls FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
-- ... etc.

-- No RLS — this is server-side only, never queried from mobile client
```

## Pydantic models (Python)

```python
# backend/app/schemas/

class User(BaseModel):
    id: UUID
    email: str | None
    phone: str | None
    plan: Plan
    trial_started_at: datetime | None
    trial_expires_at: datetime | None
    credit_balance: int
    reputation: int
    locale: str
    timezone: str
    is_anonymous: bool
    created_at: datetime

# Mandate — see docs/03_onboarding/mandate_schema.md

class AgentActivation(BaseModel):
    user_id: UUID
    agent_id: str
    activation_method: Literal["earn_path", "skip_path", "trial", "founder_grant"]
    activated_at: datetime
    earn_path_completed_at: datetime | None
    skip_path_valid_until: datetime | None
    
    @property
    def can_use_now(self) -> bool:
        if self.earn_path_completed_at:
            return True
        if self.skip_path_valid_until and self.skip_path_valid_until > datetime.utcnow():
            return True
        return False

class UserOverlay(BaseModel):
    id: UUID
    user_id: UUID
    agent_id: str
    version: int
    content: str
    plain_english: str
    based_on_coach_session: UUID | None
    is_current: bool
    created_at: datetime

class RoomRun(BaseModel):
    id: UUID
    user_id: UUID
    ticker: str
    triggered_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    mandate_version: int
    model_tier: Literal["cheap", "mid", "premium"]
    rounds: int
    transcript: list[AgentMessage]
    verdict: Verdict | None
    credit_cost: int
    status: Literal["running", "completed", "failed", "cancelled"]

class Verdict(BaseModel):
    action: Literal["APPROVE", "REJECT", "MODIFY"]
    size_pct: float | None
    entry: float | None
    target: float | None
    stop: float | None
    time_horizon_days: int | None
    reason: str
    violations: list[str] = []
    overridden_from_llm: bool = False

class JournalEntry(BaseModel):
    id: UUID
    user_id: UUID
    entry_type: Literal["room_run", "one_on_one", "sim_trade", "mandate_edit", "agent_coach", "drift_alert"]
    reference_id: UUID | None
    title: str
    summary: str | None
    ticker: str | None
    agents_involved: list[str]
    mandate_version: int
    tags: list[str]
    user_note: str | None
    outcome: Literal["win", "loss", "pending"] | None
    created_at: datetime
```

## Migrations

Migrations managed via Supabase SQL migrations (or sqlalchemy-alembic if we go SQLAlchemy):

```
backend/db/migrations/
├── 001_initial_schema.sql
├── 002_add_agent_activations.sql
├── 003_add_credit_transactions.sql
├── 004_add_llm_calls_partitioning.sql
├── ...
```

Each migration runs once on deploy. Reversible where practical.

## Backups

Supabase Pro: automatic daily backups, 7-day retention. We additionally `pg_dump` weekly to GCS for off-platform redundancy.

## Performance considerations

| Concern | Strategy |
|---|---|
| **High-cardinality lookups** (e.g., journal by user × ticker) | Indexes on (user_id, ticker, created_at) |
| **Hot path: agent_activations check on every Convene** | Cached in app memory, invalidated on activation events |
| **llm_calls write volume** | Partition by month + drop old partitions for cost |
| **Journal pruning for Floor Pass** | Daily background job deletes >30-day entries for non-paid users |
| **Real-time subscriptions** | Limited to specific row-keyed channels (e.g., per RoomRun), not broad table scans |

## Cross-references

- Mandate schema details: [`docs/03_onboarding/mandate_schema.md`](../03_onboarding/mandate_schema.md)
- API endpoints that consume this: [`api_design.md`](api_design.md)
- Auth + RLS: [`auth.md`](auth.md)
