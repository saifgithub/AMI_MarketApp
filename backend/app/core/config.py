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
        "cors_origins", mode="before",
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

    # LLM providers
    openrouter_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_ai_api_key: str = ""
    deepseek_api_key: str = ""

    # On-prem vLLM (OpenAI-compatible). When `vllm_base_url` is set the
    # gateway routes every call to it instead of Anthropic/mock.
    # Example: VLLM_BASE_URL=http://192.168.20.74:8000
    #          VLLM_MODEL=ami-llm
    vllm_base_url: str = ""
    vllm_model: str = "ami-llm"
    vllm_api_key: str = ""  # optional bearer auth — leave empty for unauth LAN servers

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
    # CR041: how long a cached Adanos row stays usable. The cache is durable
    # (social_sentiment_cache table) precisely so the monthly budget survives
    # container restarts. Readers compare fetched_at against this, so changing
    # it re-dates every row with no backfill.
    # NOTE: 30d is a benchmark-reproducibility figure. Sentiment a month stale
    # presented to a user as current is CR038's failure mode with real numbers
    # — shorten it, or render the age, before this fronts live users.
    social_cache_ttl_days: int = 30

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

    # Reputation + weekly leagues (CR004, D-060).
    # daily_cap bounds total points/user/local-day so no single behaviour
    # can be farmed. eligible_plans empty = every plan competes (Engagement
    # phase); set to "trader,floor_manager" at M1 per paywall axis 21.
    reputation_daily_cap: int = 25
    league_cohort_size: int = 30
    league_promote_count: int = 5
    league_relegate_count: int = 5
    league_eligible_plans: CsvList = Field(default_factory=list)

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

    # CR069-DIVERGE — second-source (HLAL/FTSE Shariah) holdings CSV for the
    # divergence MONITOR only (app/services/sharia_divergence.py). Log-only:
    # never read by the `halal` flag's enforcement path. Same Tidal schema as
    # SPUS, measured 2026-07-22 (213 rows). Config, not a literal — CR040 rule
    # forwards it in compose.
    sharia_hlal_holdings_url: str = (
        "https://docs.google.com/spreadsheets/d/"
        "1UC1Bk67bGuYsos_i8y_HQpNoHpVHAvqf71MbgrafJOQ/export?format=csv&gid=0"
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

    # Auth — HMAC key for scaffold tokens. Override in prod/.env.
    # The default is only used in local/dev; melehost .env must set SECRET_KEY.
    secret_key: str = "dev-secret-change-in-prod"

    # DEF044 — at-rest encryption for Alpaca brokerage creds. Optional: when
    # empty the cipher key is derived from SECRET_KEY, so encryption is active
    # out-of-box. Set a dedicated urlsafe secret here to rotate independently.
    alpaca_encryption_key: str = ""

    # Admin back-office secret (AT:R27). Static bearer for Alpha single-operator
    # access. All /v1/admin/* routes require this. Empty = admin disabled.
    # Generate: openssl rand -hex 32
    # Beta: replace with admin_users table + JWT (middleware accepts both).
    admin_secret: str = ""

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
