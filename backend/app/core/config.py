"""Runtime config — all secrets via env vars, all environments via Pydantic Settings."""

import json
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# list[str] env vars accept bare CSV ("a,b"), a single bare value, an empty
# string (→ []), or JSON. NoDecode stops pydantic-settings from insisting on
# JSON at the source layer — without it a plain `GOOGLE_AUDIENCES=<client_id>`
# crashes boot (DEF038 — how Alpha ran with empty audiences unnoticed).
CsvList = Annotated[list[str], NoDecode]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator(
        "apple_audiences", "google_audiences", "league_eligible_plans",
        "portfolio_health_plans", "cors_origins", mode="before",
    )
    @classmethod
    def _csv_or_json_list(cls, v):
        if isinstance(v, str):
            text = v.strip()
            if not text:
                return []
            if text.startswith("["):
                return json.loads(text)
            return [part.strip() for part in text.split(",") if part.strip()]
        return v

    env: Literal["local", "dev", "staging", "prod"] = "local"
    # Env policy (post-adversarial-audit):
    #   local    — single-developer machine. Legacy unsigned tokens accepted,
    #              magic-link debug code returned in response, Apple endpoint
    #              accepts unverified JWTs (for offline testing).
    #   dev      — same as staging in security posture. Used by CI.
    #   staging  — melehost (public Cloudflare Tunnel). All bypasses off.
    #   prod     — Cloud Run. All bypasses off + strictest checks.

    # Database / Supabase
    supabase_url: str = "http://localhost:54321"
    supabase_anon_key: str = ""
    supabase_service_key: str = ""
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ami_trade"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Deploy identity (CR175 F2). Nothing recorded which commit was running, so
    # after any incident there was no query that answered "is what is running
    # what I shipped?" — every diagnosis to date began by assuming it was.
    #
    # These are BUILD ARGS baked into the image (see backend/Dockerfile), not
    # runtime env. That distinction is the point: a runtime value could be
    # changed by a restart, so a container could claim a commit it was not
    # built from. `test_config_compose_parity.py` excuses them for exactly that
    # reason rather than because they were forgotten.
    #
    # `unset` rather than `""` so an unstamped container is visibly unstamped in
    # every readout instead of rendering as a blank field.
    git_sha: str = "unset"
    alpha_tag: str = "unset"

    # LLM providers
    openrouter_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_ai_api_key: str = ""
    deepseek_api_key: str = ""
    # Qwen Flash via Alibaba's DashScope OpenAI-compatible endpoint (CR017 §3,
    # built CR141). Same "presence of key turns the feature on" convention as
    # deepseek_api_key/google_ai_api_key above — an empty value means the
    # provider is simply not registered, not an error.
    dashscope_api_key: str = ""

    # On-prem vLLM (OpenAI-compatible). When `vllm_base_url` is set the
    # gateway routes every call to it instead of Anthropic/mock.
    # Example: VLLM_BASE_URL=http://192.168.20.74:8000
    #          VLLM_MODEL=ami-llm
    vllm_base_url: str = ""
    vllm_model: str = "ami-llm"
    vllm_api_key: str = ""  # optional bearer auth — leave empty for unauth LAN servers

    # Kimi (Moonshot AI) — direct API, OpenAI-compatible. Wired 2026-07-30 for
    # Saiful to test as a candidate B7 provider (see CR006/CR126); CR017
    # already generalized the vLLM provider class specifically so a new
    # OpenAI-compatible provider is this small. Direct, not via OpenRouter —
    # CR006 flagged the ToS/data-training exposure that entails; a knowing
    # choice, not an oversight.
    #
    # CORRECTED same-day (CR130): the key Saiful holds is a **Kimi Coding
    # Plan** subscription key (console: kimi.com/code), not a general
    # Moonshot Open Platform key — two separate products with separate key
    # scopes. `api.moonshot.ai` (Open Platform, pay-per-token, model ids
    # like `kimi-k3`/`kimi-k2.7-code`/`kimi-k2.6`) 401s this key outright;
    # `api.kimi.com/coding` (Coding Plan, subscription, DIFFERENT model id
    # namespace) is what actually authenticates — verified live via a bare
    # curl bypassing this codebase entirely. If a general Open Platform key
    # is ever added instead, both this base_url and kimi_model need to
    # switch back.
    # base_url deliberately excludes the trailing /v1 — llm_gateway.py's
    # OpenAICompatibleProvider appends /v1/chat/completions itself, same
    # convention as vllm_base_url above.
    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.kimi.com/coding"
    # kimi-for-coding is available to every Coding Plan membership tier
    # (verified live, 200 OK). Higher tiers unlock kimi-for-coding-highspeed,
    # k3, and k3-256k (Moderato+/Allegretto+ only, per platform docs) — try
    # those via KIMI_MODEL if Saiful's tier supports them. Note this model-id
    # namespace is Coding-Plan-specific and distinct from Open Platform's
    # kimi-k3/kimi-k2.7-code/kimi-k2.6 despite the similar names.
    kimi_model: str = "kimi-for-coding"

    # CR130 calibration finding: Kimi's Coding Plan models are genuine
    # reasoning models whose chain-of-thought shares the SAME `max_tokens`
    # budget as the final answer. The Room's per-agent budgets in
    # `room_prompts.py` (600-900) are tuned for vLLM's non-reasoning model and
    # get fully consumed by invisible reasoning before any visible content is
    # emitted — 4/5 calibration tickers hit the DEF059 fail-safe this way.
    # Isolated via direct curl: max_tokens=900 -> empty content
    # (finish_reason=length, 100% reasoning); max_tokens=4000 -> clean verdict
    # (~1,200 reasoning tokens + real content, finish_reason=stop).
    # This is a FLOOR, not a per-role tune: `OpenAICompatibleProvider` raises
    # whatever max_tokens room_runner.py requests up to at least this value
    # for this provider only — vLLM/Anthropic's tuned budgets are untouched.
    # Generous on purpose (Saiful: "remove the token limit completely...I
    # just need to let KIMI give us 1 full room") rather than the measured
    # 4000 minimum — this is a calibration knob, not a cost-tuned production
    # value yet.
    kimi_max_tokens_floor: int = 8000

    # Manual provider-selection override for testing (e.g. exercising Kimi
    # without touching LLMGateway._PREFERENCE or unregistering vLLM). Empty
    # = normal preference order. An unregistered/typo'd name falls through
    # to normal preference rather than erroring — a test env var should
    # never be able to 500 a live flow.
    llm_force_provider: str = ""

    # Email / SMS / push
    resend_api_key: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    onesignal_app_id: str = ""
    onesignal_rest_key: str = ""

    # TTS
    azure_speech_key: str = ""
    azure_speech_region: str = "eastus"
    elevenlabs_api_key: str = ""

    # Observability
    sentry_dsn: str = ""
    posthog_api_key: str = ""

    # Market data
    # When true, SimEngine quotes real Yahoo prices with mock-walk fallback.
    # When false (default), the legacy deterministic random walk runs.
    use_real_market_data: bool = False

    # CR136 M06. Whether the Portfolio Health Finding may be narrated by the
    # LLM at all. False = the deterministic rendering ships, which is a
    # complete, correct report on its own — the LLM only ever rewrites prose
    # the engine already produced, and every failure path falls back to it.
    # AT:R66 — back ON now that CR136-M06 audit BLOCKER B1 is closed
    # STRUCTURALLY: the model no longer emits digits at all, it emits
    # `{{slot}}` references that `build_slot_map` resolves, so a figure cannot
    # land on a metric it does not belong to. A model that ignores that and
    # types a number is REJECTED (reason `unsubstituted_digit`) and the reader
    # gets the deterministic report — the failure is safe and logged at ERROR,
    # which is what makes enabling this defensible where B1's silent
    # mis-attribution was not. The digit-compliance rate of the serving model
    # is unmeasured until Alpha; `unsubstituted_digit` in the logs IS that
    # measurement (promotion checklist 2.12).
    portfolio_health_llm_enabled: bool = True

    # CR136 M03. Tick cadence for the daily portfolio-value snapshot job.
    # Idempotent per trading day, so hourly only bounds post-restart catch-up
    # delay to <= 1h — it does not mean hourly rows.
    portfolio_snapshot_interval_seconds: int = 3600

    # CR095. Tick cadence for the daily-challenge reminder sweep
    # (app/services/daily_reminder.py). Users only pick an HOUR (0-23), not a
    # minute, so this has to be meaningfully finer than 3600s or the reminder
    # habitually lands up to 59 minutes into the user's chosen hour — an
    # hourly tick would be a worse experience than the feature it's gating.
    # 15 min bounds the worst-case delay to <15 min after the target hour
    # while keeping the per-tick query (one `daily_reminder_hour IS NOT NULL`
    # scan) cheap at alpha scale. The tick is idempotent per (user, local
    # calendar day) — see the module docstring — so a shorter interval only
    # changes latency, never correctness, and a restart can't cause a
    # double-send.
    daily_reminder_tick_interval_seconds: int = 900

    # CR170 §5. Tick cadence for the resting-order sweep.
    #
    # A setting rather than a module constant precisely because this tick moves
    # a real user's ledger, and the interval is the one lever that changes what
    # the feature *is*: it is a **sampling interval on a continuous price
    # path**, so it can miss the touch entirely — a buy limit at $190 polled at
    # 10:00 ($192) and 10:05 ($192) never fills even though the tape printed
    # $189 at 10:02. The three existing 5-minute ticks (CR027 price alerts,
    # CR109's queue drain and desk fill) bound *latency*; this one bounds
    # *detection*, which is a different thing to be able to turn.
    #
    # The bias is conservative — we under-fill, never over-fill, the same
    # direction as Rule 2 — so it is the right way to be wrong. The known
    # upgrade path is intraday OHLC bars (trigger on `bar.low <= limit`), which
    # answers "did it touch" exactly rather than sampling; out of scope here.
    sim_resting_order_tick_interval_seconds: int = 300

    # CR109 slice 3c — the house strategy desks' kill switch (design §11.2
    # "scaling and control"). Off removes desks from all FUTURE fields
    # without disturbing a field they are already settled in; a locked field
    # they already entered plays out, because retracting a live entrant
    # mid-week would rewrite a contest a human is currently in.
    games_desks_enabled: bool = True
    # Fill TO this field size, never a fixed desk count — desks taper as real
    # entrants arrive and stop appearing once a field clears it on its own.
    # 8 is slice 4's placement threshold: below it the board falls back to the
    # benchmark path, so this is the smallest number that makes a field score
    # as a field.
    games_desk_target_field_size: int = 8

    # CR035: hide the Street's analyst rating/target from the agents'
    # fundamentals context. Benchmark-only toggle — measures whether the
    # Room's verdict is its own or parrots the consensus it is fed. Must
    # be false outside an ablation batch window.
    suppress_analyst_consensus: bool = False

    # News provider for the agent pipeline (Room + 1-on-1), see
    # app/services/news_context.py. Yahoo (free, via the existing
    # market-data provider stack) is always tried. When
    # alpha_vantage_api_key is also set, its per-article + per-ticker
    # sentiment-scored headlines are merged in alongside Yahoo's — same
    # "presence of the key turns the feature on" convention as
    # resend_api_key / google_audiences elsewhere in this file.
    alpha_vantage_api_key: str = ""

    # Social sentiment provider for the agent pipeline (Room + 1-on-1), see
    # app/services/social_context.py. Adanos (Reddit-only stock sentiment
    # aggregator) — presence of the key turns the feature on, same
    # convention as alpha_vantage_api_key above. Free tier is 250 calls/month
    # (plus a 100-call burst window), so results are cached in Postgres.
    adanos_api_key: str = ""
    # DEF063 (second instance, found by CR148 Tier B) — a SECOND live Adanos key
    # has sat in `infra/alpha.env` with no Settings field and no compose forward,
    # so no code path could ever see it: 250 paid calls/month idle, while CR148
    # Tier B was being asked to make a TTL-shortening decision under exactly that
    # quota ceiling (30-day TTL ≈ 250 distinct tickers/month vs 7-day ≈ 58).
    #
    # This is the shape `test_config_compose_parity.py` structurally could not
    # catch: it walked `Settings.model_fields → compose`, so a key present in the
    # env file but ABSENT from Settings was invisible in both directions. Adding
    # the field is what makes it visible; the test now also walks env-file →
    # Settings so the next one cannot hide the same way.
    adanos_api_key_secondary: str = ""
    # CR041: how long a cached Adanos row stays usable. The cache is durable
    # (social_sentiment_cache table) precisely so the monthly budget survives
    # container restarts. Readers compare fetched_at against this, so changing
    # it re-dates every row with no backfill.
    # NOTE: 30d is a benchmark-reproducibility figure. Sentiment a month stale
    # presented to a user as current is CR038's failure mode with real numbers
    # — shorten it, or render the age, before this fronts live users.
    # CR148 Tier B — 30 → 7, Saiful's call 2026-08-11. At 30 days the live cache
    # measured mean age 20.2d with 162 of 175 rows (93%) older than a week, all
    # rendered under "as of this call". 7 days costs ~4.3 calls per distinct
    # ticker/month against a 500-call budget (two keys, failover wired in
    # `social_context._get_with_failover`) — a ~116 distinct-ticker/month ceiling
    # that Alpha, at 175 cached tickers over its entire life, is nowhere near.
    social_cache_ttl_days: int = 7

    # Room dedup windows (see app/services/room_runner.py::start_run).
    # Same user+ticker submitted while a run is in flight always returns the
    # in-flight run_id, regardless of these knobs (running_minutes is just an
    # upper bound on how stale a "running" row can be before it's considered
    # abandoned). The completed_hours window prevents accidental re-runs of an
    # analysis whose underlying data hasn't meaningfully changed — a tap of
    # "Convene the Room" the same day returns yesterday's verdict instead of
    # burning another 5 minutes of LLM time.
    #   running_minutes:    30 min  — also the startup-sweep cutoff
    #   completed_hours:    24 h    — design doc default is 5 days; we start
    #                                 tighter so re-runs after meaningful
    #                                 market moves (next-day open) are not
    #                                 blocked. Raise via env to taste.
    room_dedup_running_minutes: int = 30
    room_dedup_completed_hours: int = 24

    # CR098 — tenure-drip analyst pull-back. Account-age day (`users.created_at`)
    # at which each withholdable Room voice goes dark for a FLOOR_PASS user.
    # `0` (default) = never withheld — ships as a no-op. Independent, not
    # ordered steps: any combination is a legal operator choice.
    # Fundamentals has NO threshold here — it is structurally unwithholdable.
    room_pullback_days_social: int = 0
    room_pullback_days_news: int = 0
    room_pullback_days_market: int = 0

    @field_validator(
        "room_pullback_days_social", "room_pullback_days_news",
        "room_pullback_days_market",
    )
    @classmethod
    def _pullback_days_non_negative(cls, v: int) -> int:
        # CR040 degrade-loudly: a negative threshold is nonsensical (an
        # account can't be "-5 days old") and a silent clamp to 0 would look
        # like "never withheld" when the operator meant something else —
        # fail boot instead of guessing.
        if v < 0:
            raise ValueError("room pull-back day threshold must be >= 0")
        return v

    # GTM funnel selector (CR047, under the CR045 tactic library). Chooses which
    # conversion-nudge mechanic sits on top of the CR039 credit wall:
    #   none    — legacy CR039 behaviour: exhausted Floor Pass → hard 402 until
    #             the monthly reset. [default]
    #   winzip  — "The Winzip": on Floor-Pass exhaustion, reset +1 Room the
    #             instant the 402 is sent but enforce a cooldown before the next
    #             convene (see credit_service.spend / winzip_cooldown_minutes).
    # A Literal on purpose (not a plain str like concierge_context_mode): a
    # typo'd funnel must fail boot LOUDLY, never silently fall back to "no
    # funnel" and quietly change how every free user's paywall behaves (CR040).
    gtm_funnel: Literal["none", "winzip"] = "none"
    # How long the Winzip cooldown lasts. "A few minutes" — the felt wait
    # between free Rooms. Only consulted when gtm_funnel == "winzip".
    winzip_cooldown_minutes: int = 5

    # DEF113 — 1-on-1 chat's credit price. credits.md:18 prices it at 1; Saiful
    # ruled (2026-07-30) to wire the full spend()/ledger/402 spine now but keep
    # Alpha priced at 0 so no existing tester hits a paywall they've never seen
    # mid-test. This is a DECLARED setting, not a literal 0 at the call site —
    # flipping to 1 in credits.md's spec is then a one-line env change, already
    # exercised by the 402 test at a non-zero price (test_def113_one_on_one_credit_gate.py).
    one_on_one_credit_cost: int = 0

    @field_validator("one_on_one_credit_cost")
    @classmethod
    def _one_on_one_cost_non_negative(cls, v: int) -> int:
        # CR040 degrade-loudly, same shape as the CR098 pull-back validator: a
        # negative price is nonsensical — fail boot instead of charging garbage.
        if v < 0:
            raise ValueError("one_on_one_credit_cost must be >= 0")
        return v

    # Reputation + weekly leagues (CR004, D-060).
    # daily_cap bounds total points/user/local-day so no single behaviour
    # can be farmed. eligible_plans empty = every plan competes (Engagement
    # phase); set to "trader,floor_manager" at M1 per paywall axis 21.
    reputation_daily_cap: int = 25
    league_cohort_size: int = 30
    league_promote_count: int = 5
    league_relegate_count: int = 5
    league_eligible_plans: CsvList = Field(default_factory=list)

    # CR136 — Portfolio Health access gating. Tiles are FREE in every mode; only
    # full Finding generation is gated.
    #   open   — no access gate at all (the daily cap still applies)
    #   trial  — trial window OR budget, whichever exhausts first, then plan
    #   plan   — plan membership only, from day one
    # A Literal on purpose, the `gtm_funnel` idiom: a typo'd mode must fail boot
    # LOUDLY rather than silently fall through to whichever branch a plain str
    # happens to miss, quietly changing who pays for the feature (CR040).
    portfolio_health_gate_mode: Literal["open", "trial", "plan"] = "trial"
    portfolio_health_trial_days: int = 14
    portfolio_health_trial_findings: int = 3   # DEF219 — see TRIAL_FINDINGS_DEFAULT
    portfolio_health_daily_cap: int = 2
    portfolio_health_plans: CsvList = Field(
        default_factory=lambda: ["trader", "floor_manager"]
    )

    @field_validator(
        "portfolio_health_trial_days", "portfolio_health_trial_findings",
        "portfolio_health_daily_cap",
    )
    @classmethod
    def _portfolio_health_counters_non_negative(cls, v: int) -> int:
        # Same shape as the CR098 pull-back validator. `0` is LEGAL and
        # documented — trial_days=0 or trial_findings=0 exhausts the trial
        # immediately, daily_cap=0 generates nothing at all. Those are loud
        # operator choices; a negative is nonsense and fails boot rather than
        # being clamped into one of them.
        if v < 0:
            raise ValueError("portfolio health gate counters must be >= 0")
        return v

    # CR069 — Sharia-compliance indicator for the `halal` mandate flag.
    # Off by default so the flag degrades LOUDLY (pauses) rather than silently
    # enforcing the retired 7-ticker demo set. Flip on Alpha once the source
    # fetch is verified. The URLs are the published daily-transparency holdings
    # CSVs: SPUS = the S&P 500 Sharia Industry Exclusions Index (AAOIFI, the
    # compliant set); the parent index = a large-cap S&P 500 ETF (IVV) used ONLY
    # to distinguish "screened out" from "unknown" (CR069 constraint 2). Both are
    # config, not literals — this file's CR040 rule forwards them in compose.
    sharia_screen_enabled: bool = False
    sharia_spus_holdings_url: str = (
        "https://www.sp-funds.com/wp-content/uploads/data/TidalFG_Holdings_SPUS.csv"
    )
    # DEF089: this was the iShares IVV holdings endpoint, which answers a plain
    # server-side client with HTTP 200 and an HTML interstitial that still carries
    # `content-type: text/csv` — bot mitigation in front of the origin. The screen
    # could only ever pause. Now a published S&P 500 constituent list on a plain
    # static endpoint: no key, no browser emulation, auto-updated on membership
    # changes. Tradeoff, stated rather than buried: it is a community-maintained
    # mirror, not a regulatory disclosure like SPUS. It is used for *membership
    # only*, and the failure direction is safe — a name missing from a lagging
    # mirror resolves UNKNOWN (permitted + disclosed), never a false PASS. The
    # 400-row floor in `sharia_universe.py` catches truncation.
    sharia_parent_index_url: str = (
        "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/"
        "main/data/constituents.csv"
    )
    # SPUS refreshes daily; the index rebalances quarterly. CR075 split the one
    # window into two, each named:
    #   sharia_staleness_days   — the SOURCE's own freshness. After a successful
    #     fetch, `_sharia_universe_refresh()` logs `sharia_source_lagging` if the
    #     file's own as-of is already older than this. It is the "the mirror looks
    #     frozen" signal — the reader does not gate on it.
    #   sharia_hold_window_days — the READER's window for a persisted row. CR075
    #     reads from a stored snapshot instead of fetching on the request path, so
    #     a source outage no longer blocks (the held list is served with its held
    #     as-of). A held row is a lower risk to serve stale-ish than a just-fetched
    #     file was, so its window is deliberately longer than the 7-day fetch
    #     window — 30 days keeps every served list inside one quarterly rebalance
    #     cycle while still pausing loudly (UNAVAILABLE) if the source has been
    #     effectively dead for a month. This is the "much longer runway before the
    #     pause fires" the CR buys, named rather than inherited.
    sharia_staleness_days: int = 7
    sharia_hold_window_days: int = 30

    # DEF061 — sourced sector/industry classification backing the `no_fossil_fuels`
    # and `no_tobacco_alcohol_gambling` mandate flags (the CR069/CR075 architecture
    # applied to sector/industry exclusions). OFF by default → both flags PAUSE
    # loudly (UNAVAILABLE) rather than silently permitting every name from an empty
    # set. Flip on Alpha once the first live classify pass is verified (the daily
    # refresh logs its classified/fossil/sin counts). The universe classified is the
    # ~503 S&P parents already persisted by CR075, so this depends on the Sharia
    # snapshot being seeded first. No URL: the source is yfinance sector/industry.
    classification_screen_enabled: bool = False
    # The reader's window for a persisted classification row — a classify outage
    # serves the held sets (no request-path yfinance calls) until the row's classify
    # date ages past this, then pauses loudly. Longer than the Sharia fetch window
    # for the same reason CR075's hold window is (a recorded list is safer to hold
    # than a fresh fetch), and sector/industry drifts far slower than an index
    # rebalance — 40 days keeps a run inside a comfortable refresh runway.
    classification_hold_window_days: int = 40

    # CR069-DIVERGE — second-source (HLAL/FTSE Shariah) holdings CSV for the
    # divergence MONITOR only (app/services/sharia_divergence.py). Log-only:
    # never read by the `halal` flag's enforcement path. Same Tidal schema as
    # SPUS, measured 2026-07-22 (213 rows). Config, not a literal — CR040 rule
    # forwards it in compose.
    sharia_hlal_holdings_url: str = (
        "https://docs.google.com/spreadsheets/d/"
        "1UC1Bk67bGuYsos_i8y_HQpNoHpVHAvqf71MbgrafJOQ/export?format=csv&gid=0"
    )

    # CR128 — ticker existence validation. NASDAQ Trader's public, no-auth
    # symbol-directory files: nasdaqlisted.txt (NASDAQ-listed) + otherlisted.txt
    # (NYSE/AMEX/ARCA-listed), together ~13k US-listed symbols incl. ETFs.
    # Refreshed daily by `_ticker_reference_refresh()`, same pattern as CR075/
    # DEF061 above. Config, not a literal — CR040 rule forwards it in compose.
    ticker_reference_nasdaq_listed_url: str = (
        "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
    )
    ticker_reference_nasdaq_other_url: str = (
        "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"
    )

    # Concierge lesson-context router (CR021). Selects how much lesson
    # knowledge the Floor Concierge is given:
    #   saver        — first 25 lessons, id/title/track/level (legacy)
    #   full_context — compact index of ALL lessons (number+title+topic+tags) [default]
    #   embedding    — semantic top-K retrieval (CR019; not built → degrades to full_context)
    # Unknown/empty → full_context. Kept a plain str (not Literal) so an
    # unrecognised value degrades gracefully instead of crashing boot
    # (the DEF038 lesson — strict source-layer typing took Alpha down once).
    concierge_context_mode: str = "full_context"

    # In-app bug-report attachments — written to this directory by the
    # /v1/feedback/bug endpoint, retrieved by Saiful via SSH (no public
    # download endpoint in alpha). On melehost a named docker volume
    # mounts here; for Mac tests a tempfile fixture overrides.
    bug_attachments_dir: str = "/data/bug_attachments"
    # Hard cap per upload — generous enough for a phone photo at native
    # resolution, small enough that an abusive client can't flood the disk.
    bug_attachment_max_bytes: int = 5 * 1024 * 1024
    # DEF201 (H9 follow-up): the per-file cap bounds one upload; nothing
    # bounded the VOLUME, so uploads above zero net rate filled the disk
    # over time regardless of the per-file cap. 2 GiB is generous for an
    # alpha-scale tester population while still being a real ceiling.
    bug_attachments_total_cap_bytes: int = 2 * 1024 * 1024 * 1024
    # DEF201: once the total cap above is reached, EVERY future upload is
    # rejected until something frees space — nothing did. Read by
    # scripts/prune_bug_attachments.py (a melehost cron job, not this
    # process), not by the API itself; lives here so both the cap and the
    # window that keeps it from becoming permanent are one settings class.
    bug_attachments_retention_days: int = 60

    # DEF201 (H6 follow-up): 1-on-1 + Brief were rate-limited to 12/min/user
    # (DEF186) but nothing bounded how many SSE streams one account could
    # hold open AT ONCE — pace was capped, concurrency was not. Shared
    # across both surfaces (same underlying LLM compute budget).
    agent_stream_max_concurrent_per_user: int = 2

    # Auth — HMAC key for scaffold tokens. Override in prod/.env.
    # The default is only used in local/dev; melehost .env must set SECRET_KEY.
    secret_key: str = "dev-secret-change-in-prod"

    # CR125 — scaffold Bearer token lifetime, in days, from issue time.
    # `parse_scaffold_token()` 401s once `exp` passes; `DELETE /v1/auth/session`
    # (token_version bump) is the immediate-revocation path, this is the
    # backstop for a token nobody ever explicitly signed out.
    auth_token_ttl_days: int = 30

    # CR125 audit MAJOR — how long past `exp` a token may still prove account
    # OWNERSHIP on `/v1/auth/anon` (never authenticate a request). Without a
    # bound, an expired stolen token resurrects a session forever, which is
    # strictly worse than an unexpired stolen one — that at least dies on its
    # own. 180 days is generous for a returning user and finite for a thief.
    # 0 disables the leniency entirely, which re-opens the day-31 orphaning,
    # so it is a deliberate choice and not a safe default.
    # `ge=0` because a negative value moves the cutoff BEFORE `exp` and starts
    # refusing ownership proof from tokens that have not even expired yet —
    # silently re-orphaning accounts via the very setting added to stop that.
    # Refusing at boot beats discovering it from support tickets (DEF038/063).
    auth_rebootstrap_grace_days: int = Field(default=180, ge=0)

    # CR125 audit BLOCKER — the last date on which a PRE-CR125 token may prove
    # ownership on `/v1/auth/anon`. Every installed token is in the old format
    # when CR125 ships, so without this every existing account is orphaned on
    # day zero, not day 31. Legacy tokens carry no `token_version` and so
    # cannot be revoked — that is not a regression (nothing revoked them
    # before either) but it is a real widening, so it expires by wall clock.
    # ISO date, e.g. "2027-02-07". Empty = legacy proof refused.
    auth_legacy_rebootstrap_until: str = "2027-02-07"

    # DEF044 — at-rest encryption for Alpaca brokerage creds. Optional: when
    # empty the cipher key is derived from SECRET_KEY, so encryption is active
    # out-of-box. Set a dedicated urlsafe secret here to rotate independently.
    alpaca_encryption_key: str = ""

    # Admin back-office secret (AT:R27). Static bearer for Alpha single-operator
    # access. All /v1/admin/* routes require this. Empty = admin disabled.
    # Generate: openssl rand -hex 32
    # Beta: replace with admin_users table + JWT (middleware accepts both).
    admin_secret: str = ""

    # CR121 — iOS store deep link for the client-version-gate block screen.
    # We do NOT have a numeric App Store ID (no App Store record exists yet —
    # same provisioning gap as DEF100/CR084), so this is the TestFlight
    # public join link, set once Saiful creates one. Android needs no
    # equivalent setting: its Play Store URL is derived from the known,
    # stable applicationId (`ai.agenticmarketintel.ami_trade`), a compile-time
    # constant, not an operational secret. Empty = the release-floor endpoint
    # falls back to the generic https://testflight.apple.com/ page and logs
    # `release_floor_ios_store_url_unconfigured` — degrades loudly, never a
    # dead link with no signal (CR040).
    ios_testflight_join_url: str = ""

    # RevenueCat webhook shared secret (CR084). RC sends this verbatim as the
    # `Authorization` header on every webhook POST to /v1/webhooks/revenuecat;
    # the endpoint constant-time-compares it and fails CLOSED (401) on any
    # mismatch — a wrong grant is real dollars + a real trust breach (D-5).
    # Empty = the webhook refuses LOUDLY (503 + logged error), never
    # silent-accept and never silent-reject-all (CR040 degrade-loudly). Set it
    # in infra/alpha.env once the RC project exists; it is forwarded in
    # docker-compose.yml's api-alpha block (test_config_compose_parity gate).
    # Generate to match the value pasted into the RC dashboard webhook config.
    revenuecat_webhook_secret: str = ""

    # RevenueCat server-side REST secret key (DEF099). Used ONLY server→RC, to
    # transfer a customer alias orphan→adopter on account claim so post-merge
    # webhooks target the surviving account (app/services/revenuecat_client.py).
    # This is the RC *secret* API key (starts `sk_...`) from Project Settings →
    # API keys — NOT the public SDK key and NOT the webhook shared secret above.
    # Empty = the alias transfer degrades LOUDLY (logs an error, returns
    # not_configured, makes no network call, CR040); the webhook's merge-trail
    # safety net still re-targets deliveries. Set it in infra/alpha.env; it is
    # forwarded in docker-compose.yml's api-alpha block (compose-parity gate).
    revenuecat_secret_api_key: str = ""

    # Apple Sign-In — accepted audiences for the identity token's `aud`
    # claim. iOS native flow uses the bundle ID; a Web Services ID would
    # be added here if we ever ship Apple sign-in via web/Android. Comma-
    # separated env var (`APPLE_AUDIENCES=ai.agenticmarketintel.amiTrade`),
    # or `,` in the value to allow multiple.
    apple_audiences: CsvList = Field(
        default_factory=lambda: ["ai.agenticmarketintel.amiTrade"]
    )

    # Google Sign-In — wired when Android lands. Audience = the OAuth Web
    # client_id (one per Android signing key configuration in Google Cloud
    # Console). Leave empty until Android slice starts.
    google_audiences: CsvList = Field(default_factory=list)

    # SMTP (magic-link email delivery). When smtp_host is empty the backend
    # falls back to debug-code-only mode (code shown in UI for alpha testers).
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # Alpaca paper trading OAuth (AT:R45).
    # Register at https://app.alpaca.markets/oauth-clients to get these.
    # client_id is public (also passed to mobile via --dart-define).
    # client_secret is backend-only — never put it in the mobile build.
    alpaca_client_id: str = ""
    alpaca_client_secret: str = ""
    alpaca_paper_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_oauth_token_url: str = "https://api.alpaca.markets/oauth/token"
    # Redirect URI registered with Alpaca; webview intercepts this before OS.
    alpaca_redirect_uri: str = "amitrade://alpaca/callback"

    # CORS
    cors_origins: CsvList = Field(default_factory=lambda: ["*"])

    # Server
    port: int = 8000


settings = Settings()
