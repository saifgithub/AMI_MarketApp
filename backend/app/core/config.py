"""Runtime config — all secrets via env vars, all environments via Pydantic Settings."""

import json
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
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

    # CR211 — decode-budget floor for the on-prem vLLM server, the same knob
    # `kimi_max_tokens_floor` is for Kimi and for the same reason: a REASONING
    # model spends the budget on invisible chain-of-thought before it writes a
    # visible word, and the Room's per-agent caps (800-1600, derived in
    # room_prompts.py from measured VISIBLE output against the old
    # non-reasoning `ami-llm`) do not budget for it.
    #
    # Measured 2026-08-28 against `qwen3.8-flash-next` on :8048, one realistic
    # Fundamentals Analyst turn:
    #     budget  finish  tokens  reasoning_chars  content_chars
    #        800  length     800             2771              0   <- Alpha, live
    #       1200    stop    1075             2954            728
    #       3200    stop    1075             2954            728
    # Above 1200 nothing changes — max_tokens is a CEILING and the model
    # self-terminates. So the cost of a generous floor is bounded by what the
    # model actually wants to say, not by the floor itself.
    #
    # 0 = off (the default, and the correct value for a non-reasoning server:
    # a floor that never binds is still a floor the next reader has to reason
    # about). Env-driven so the value can be retuned on melehost without a
    # promotion — that is the whole point of the knob.
    vllm_max_tokens_floor: int = 0

    # DEF389 — the HTTP read timeout for a vLLM completion. This is the
    # TRANSPORT budget and it must sit OUTSIDE the Room's orchestration budget
    # (`room_runner._AGENT_LLM_TIMEOUT_S`, 90s), not inside it. It used to be a
    # hardcoded 60.0, i.e. 30s shorter, which made the orchestration guard
    # unreachable: every slow call died in httpx first and surfaced as
    # `room_pm_llm_failed error=""` — a bare `httpx.ReadTimeout` stringifies to
    # the empty string — instead of the `room_pm_timeout` the code was written
    # to emit. The Room then fell back to its DEF059 PASS, which is a completed
    # run carrying a verdict and is indistinguishable from a decision.
    #
    # Measured 2026-08-31 against qwen3.8-flash-next on an otherwise idle
    # server, at a 3,809-token prompt (PM-shaped): 14.0s for one stream at
    # 20.7 tok/s, and 45.9s for the slowest of the five concurrent draws that
    # `pm_self_consistency_samples=5` issues. 46s against the old 60s ceiling
    # is a 1.3x margin on an IDLE box, so any second convene or live user
    # pushed the PM phase over it — which is exactly what the CR214 sweep hit.
    # `test_def389_transport_timeout.py` pins the ordering.
    vllm_request_timeout_s: float = Field(default=360.0, ge=30.0, le=1800.0)

    # DEF390 — the Room's per-agent orchestration budget. Was a hardcoded
    # `room_runner._AGENT_LLM_TIMEOUT_S = 90.0`, which is why nobody re-checked
    # it when CR211 swapped the served model underneath it: same class as the
    # 60s transport constant DEF389 fixed, one layer up.
    #
    # Sized from `llm_audit`, 2026-09-01, 6h of real convenes on
    # qwen3.8-flash-next. The portfolio_manager is the binding agent — 290 calls
    # at 7,041 input / 277 output tokens, mean 42.4s, mode 35-40s, visible tail
    # to 85s, and **21 calls stacked in the 90-95s bucket**, which is the old cap
    # clipping the distribution rather than any natural mode. ~7% of PM calls
    # were being killed. `pm_self_consistency_samples=5` issues those draws
    # concurrently, so when the host is contended all five cross together and the
    # convene degrades to a DEF059 fail-safe PASS.
    #
    # 180s is ~4.5x the mode. Raising it does NOT make users wait longer in the
    # typical case (the mode is unchanged); it changes what a slow convene
    # RETURNS — today they wait 90s for a fail-safe PASS carrying no narrative,
    # which is a worse outcome than waiting for the real verdict.
    #
    # Must stay BELOW `vllm_request_timeout_s` so this guard is the one that
    # fires and logs `room_agent_timeout` / `room_pm_timeout`; DEF389 is what
    # the inverted ordering costs. `test_def389_transport_timeout.py` pins it.
    room_agent_timeout_s: float = Field(default=180.0, ge=15.0, le=900.0)

    @model_validator(mode="after")
    def _transport_budget_outside_the_guard(self) -> "Settings":
        # DEF392 — CR040 degrade-loudly. The per-field bounds above are each
        # satisfiable while the PAIR is inverted: `ROOM_AGENT_TIMEOUT_S=800` with
        # `VLLM_REQUEST_TIMEOUT_S=45` boots clean today, and what boots is a Room
        # whose timeout guard can never fire. Every slow call then dies in httpx
        # first, and a bare `httpx.ReadTimeout` stringifies to the empty string,
        # so the failure lands as `room_pm_llm_failed error=""` and the Room
        # falls back to its DEF059 fail-safe PASS — a completed run carrying a
        # verdict indistinguishable from a decision (DEF389). An inverted pair is
        # never a legitimate operator choice, so this refuses boot outright
        # rather than logging a warning nobody reads at 3am.
        if self.vllm_request_timeout_s <= self.room_agent_timeout_s:
            raise ValueError(
                "vllm_request_timeout_s "
                f"({self.vllm_request_timeout_s}s) must be strictly greater than "
                f"room_agent_timeout_s ({self.room_agent_timeout_s}s): the HTTP "
                "transport budget has to sit OUTSIDE the Room's per-agent guard, "
                "or the guard can never fire and slow completions surface as "
                "empty-string transport errors feeding a fail-safe PASS verdict "
                "(DEF389/DEF392). Raise VLLM_REQUEST_TIMEOUT_S or lower "
                "ROOM_AGENT_TIMEOUT_S."
            )
        return self

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

    # CR217 — GLM-5.3-Flash-NVFP4, a candidate Room model served by vLLM on a
    # host reached over Tailscale (100.64.0.0/10), NOT the LAN box that serves
    # `vllm_base_url`. Registered as its own provider rather than by repointing
    # VLLM_BASE_URL, because the whole point is to run it head-to-head against
    # the incumbent: repointing would make the comparison unrunnable and would
    # swap the live Room's model as a side effect.
    #
    # base_url deliberately excludes the trailing `/v1` — OpenAICompatibleProvider
    # appends `/v1/chat/completions` itself (llm_gateway.py:685), so the `/v1/`
    # form this endpoint is usually quoted with ("http://100.94.223.38:8008/v1/")
    # would resolve to `/v1/v1/chat/completions` and 404. Same convention as
    # vllm_base_url and kimi_base_url above.
    #
    # Presence of the URL turns it on, matching vllm_base_url; the endpoint
    # needs no key today (verified live: a bare unauthenticated GET /v1/models
    # returns 200), so gating on a key would leave it permanently dark.
    glm_base_url: str = ""
    glm_model: str = "LibertAIDAI/GLM-5.3-Flash-NVFP4"
    glm_api_key: str = ""
    # GLM is a REASONING model and needs the same floor Kimi and vLLM got, for
    # the same reason (CR130, CR211): chain-of-thought shares the `max_tokens`
    # budget with the visible answer, so the Room's per-agent caps — 800 for the
    # four analysts (`room_prompts.py:_AGENT_MAX_TOKENS`) — are consumed before
    # any content is emitted, and the turn arrives empty.
    #
    # Measured 2026-09-01 against the Room's real caps:
    #   analyst @800  -> finish_reason='length', 800 tokens spent, **0 visible chars**
    #   bull     @1600 -> finish_reason='stop',  723 tokens,  782 visible chars
    #   PM       @900  -> finish_reason='stop',  778 tokens,  290 visible chars
    # i.e. ~470-490 tokens of invisible thinking on every call, and the 800 cap
    # is below that floor outright.
    #
    # **The reasoning is NOT in `reasoning_content`.** GLM returns it in a field
    # named `reasoning`, which is why a first probe that checked only
    # `reasoning_content` reported "no reasoning, no floor needed" and was wrong.
    # An empty-looking turn from this model is a starved turn, not a refusal —
    # and in a backtest a starved turn is a DEF059 fail-safe PASS, i.e. it reads
    # as the model declining to trade.
    #
    # 12000 per Saiful (2026-09-01). The 2,985 reasoning chars above are a LOWER
    # BOUND, not the requirement: that turn was cut off mid-thought at the 800
    # cap, so it says only that GLM wanted at least that much, never how much.
    # Sizing the floor to a truncated observation is how CR211's first attempt
    # would have failed.
    #
    # A ceiling, not a target — the model self-terminates (723-778 tokens
    # observed at caps of 1600 and 900), so a generous floor costs what the
    # model chooses to say, not what the floor permits.
    #
    # The real backstop is not this number. At ~14-22 tok/s a genuine 12000-token
    # generation would take ~9-14 minutes and hit `room_agent_timeout_s` (180s)
    # first — loudly, via the Room's own guard, which is what DEF389/DEF390 put
    # there. That is the intended failure: a visible timeout, not a silently
    # starved turn.
    glm_max_tokens_floor: int = 12000

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
    # DEF333 — OneSignal's auto-created Android fallback channel is
    # IMPORTANCE_DEFAULT (no heads-up banner, and vulnerable to OS-level
    # adaptive muting). This points at a dashboard-configured "Urgent"
    # Android Notification Category instead. Empty is a valid, degrading
    # state (falls back to OneSignal's own default channel) — not every
    # environment needs this configured, so no loud-failure guard here.
    onesignal_android_channel_id: str = ""

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

    # CR172 §2 / D8. The ticker quoted for the option pricer's risk-free
    # rate — `^IRX` is the 13-week T-bill yield, already served by the
    # yfinance stack, quoted in PERCENT (5.23 → 0.0523). A synthetic or
    # implausible quote is refused, never defaulted: greeks then read
    # `not_evaluated` rather than being priced off an invented rate
    # (services/option_chain.py::get_risk_free_rate).
    risk_free_rate_ticker: str = "^IRX"

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

    # DEF305 — the stop-gap kill switch for automatic position closing, while
    # the real fix (a source check on every money-moving price) is in audit.
    #
    # `SimEngine.current_price` returns a float and discards `Quote.source`, so
    # `evaluate_outcomes` cannot tell a yfinance quote from the mock walk's
    # `[50, 450]` random draw. On 2026-08-14 three sweeps closed nine positions
    # across two portfolios at fabricated prices — HPQ, a $30 stock, was booked
    # out at $334.96 — and credited the proceeds as real cash. A fabricated
    # fill never comes off the books; a stop that fires late does.
    #
    # `True` is the default and the correct long-term value: this suppresses a
    # SAFETY feature, and leaving it off is its own harm. It is off on Alpha
    # only until DEF305's guard ships. **Whoever lands that guard turns this
    # back on** — the switch is not the fix and must not become the fix.
    # Surfaced in `/v1/admin/config-check` so "is it still off" is one curl
    # rather than an assumption, and logged loudly on every suppressed pass so
    # it cannot go dark the way DEF038 and DEF063 did.
    sim_bracket_sweep_enabled: bool = True

    # ── CR171 — short selling, training lane ──────────────────────────────
    #
    # §4's Layer 3. Reached whenever neither Alpaca's `easy_to_borrow` (no
    # house key exists — measured absent in every environment 2026-08-11) nor
    # yfinance's `shortPercentOfFloat` resolves, which today is every ticker
    # outside the S&P snapshot. 3.0%/yr sits in the middle of the observed
    # liquid-name range and is deliberately a FLAT number: real borrow spans
    # 0.25%/yr to over 100%/yr, a 400x range we cannot observe, and inventing a
    # per-ticker figure would be the fabrication CR040 and DEF252 exist to
    # prevent. An honest flat rate beats a precise invented one.
    short_borrow_default_rate_annual_pct: float = 3.0

    # §7's two thresholds. Settings rather than constants because they are the
    # levers that decide how a short *feels* in the simulator: 1.50 is how much
    # cash a short ties up, 1.30 is how far it may run before the account takes
    # the decision away. Saiful chose forced buy-in over a size cap (a cap
    # teaches that bounded shorts are safe, which is false) and over negative
    # equity (which leaves a training account unrecoverable), so these two
    # numbers ARE the containment mechanism.
    short_initial_margin: float = 1.50
    short_maintenance_margin: float = 1.30

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
    #
    # DEF205 (2026-08-24) — flipped 0 -> 1, Saiful's ruling: *"1 credit per
    # turn, Brief the same."* The 2026-07-30 reason for 0 was that no tester
    # should meet a paywall they have never seen mid-test; measured before
    # flipping, that risk is gone — all 39 Floor Pass accounts on Alpha hold
    # 116-280 credits and both Floor Managers hold 4,400+, so every user has
    # at least 116 turns before a 402 is reachable.
    one_on_one_credit_cost: int = 1

    # DEF205 — Brief Your Agent's price, same flat 1/turn. Its own setting
    # rather than a shared one: credits.md prices the two surfaces separately
    # (1-on-1 per turn, Brief per session) and a single knob would make the
    # next divergence require a code change instead of an env change.
    brief_credit_cost: int = 1

    @field_validator("one_on_one_credit_cost", "brief_credit_cost")
    @classmethod
    def _one_on_one_cost_non_negative(cls, v: int) -> int:
        # CR040 degrade-loudly, same shape as the CR098 pull-back validator: a
        # negative price is nonsensical — fail boot instead of charging garbage.
        if v < 0:
            raise ValueError("credit cost must be >= 0")
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
    # CR140 — the evaluation cadence Saiful ruled monthly (2026-08-05). Rolling
    # days since the LAST Finding (shape (b) of the CR140 decision table), per
    # USER for the same reset-loophole reason the daily counter is
    # (portfolio_health_stats). 0 disables cadence entirely and restores the
    # pre-CR140 behaviour exactly — the config-revert the CR's acceptance 4
    # demands. Trial-budget-served users are exempt (DEF219: the trial is
    # bounded by budget only), as is `open` mode (an operator override, not a
    # user-facing product mode).
    portfolio_health_cadence_days: int = 30

    @field_validator(
        "portfolio_health_trial_days", "portfolio_health_trial_findings",
        "portfolio_health_daily_cap", "portfolio_health_cadence_days",
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

    # CR197 — how many independent CIO samples to draw before issuing a verdict.
    #
    # 1 keeps today's behaviour exactly (one call, one answer) and is the default,
    # because anything above it multiplies the most expensive call in the run.
    #
    # Why the knob exists: replaying 136 committed convenes three times each on
    # BYTE-IDENTICAL prompts, 26 of 132 (19.7%) did not return a unanimous verdict,
    # and a single draw disagrees with the 3-vote majority 6.6% of the time. The
    # approval RATE is stable across samples (22/21/25 of ~135) but WHICH name gets
    # approved is not — so roughly one verdict in five is settled by the sampler
    # while the user reads confident prose either way.
    #
    # Set to an odd number ≥3 to vote instead: majority on the action, median size
    # among the winners. Even numbers are allowed but waste a call, since ties fall
    # back to the safe side.
    # CR214 — raised 1 -> 5. The measurement above is the reason: roughly one
    # verdict in five was being settled by the sampler, and a diluted signal is
    # indistinguishable from no signal in any outcome test we can afford to run.
    # Five also yields `Verdict.approve_votes` in 0..5, the graded score the Room
    # backtest ranks on. Cost is 4 extra premium-tier PM calls per convene.
    pm_self_consistency_samples: int = Field(default=5, ge=1, le=9)

    # CR219 R51 — how many desks may fall back to a scripted turn before the
    # verdict stops being a confident call.
    #
    # DEF059 fixed the TOTAL outage (provider unreachable -> PASS, never a fake
    # APPROVE). The PARTIAL case was silent: `_compute_agent_text` substitutes a
    # scripted `_TEMPLATES` sentence per agent on timeout, error or empty
    # response — a complete, confident sentence populated with real computed
    # figures and carrying no mark — so a convene where most desks timed out
    # still produced a full transcript and a confident verdict. DEF397 measured
    # exactly that: 6 of 10 agent calls returning 0 chars on batch `cr217-glm-1`
    # while the run banked as COMPLETED with `error_message=None`.
    #
    # At or above this many scripted turns the verdict degrades to an explicit
    # incomplete state (NO_VERDICT) instead of an APPROVE or a reasoned PASS.
    # This extends DEF059's rule from "no AMI" to "not enough AMI".
    #
    # The default of 4 is WP08's proposal (">3 of 12") and is a threshold, not a
    # measurement: no production distribution of scripted-turn counts exists yet
    # to size it from, which is precisely because nothing counted them until this
    # CR. Treat it as an operator knob to be re-set once the counter has run on
    # Alpha for a while, not as a derived number.
    #
    # Set to 0 to disable the degrade entirely (the disclosure still renders —
    # counting and telling the user are not the part that needs an off switch).
    room_max_scripted_turns: int = Field(default=4, ge=0, le=12)

    # CR197 — hand the CIO a computed ladder of sized options (trim / reference /
    # press) with each rung's drawdown contribution, remaining headroom and
    # reward:risk, instead of leaving that arithmetic to the risk officers' prose.
    #
    # OFF by default because it is a measured behaviour change, not a pure bug fix.
    # Replayed over 136 committed convenes against the same model:
    #   debate only (today)      22 approvals, 16.3%
    #   debate + ladder          28 approvals, 21.1%   (net -7, p=0.21)
    #   ladder only, no debate   16 approvals, 11.8%
    #   neither                  10 approvals,  7.4%   (net +12, p=0.004)
    #
    # Two honest readings of the +5pp, and this knob exists because the measurement
    # cannot separate them. It is what fixing the DEF066 class predicts — that defect
    # compared a raw stop distance against the portfolio cap, overstating risk ~20x
    # and making 16 of 64 benchmark names wrongly un-buyable, so correcting the
    # arithmetic should recover refusals that were artifacts. It is ALSO what
    # DEF292's failure mode would look like from the other side: rungs that read
    # "0.3% of the cap" can make the risk budget feel empty and ours to fill.
    #
    # Known cost either way: interpolation falls from 32% of approvals (7/22) to 11%
    # (3/28) — the CIO anchors onto rungs. The rendered block says outright that the
    # rungs are not the only permitted sizes; that wording is doing real work and
    # should not be trimmed.
    pm_option_ladder_enabled: bool = False

    # CR201 — the RISK phase as ONE structured Risk Officer call instead of three
    # debating ones. The three risk-debator voices still render (transcript, SSE,
    # comb, Journal) — from the officer's JSON payload, with every figure taken
    # from the computed ladder and none from the model.
    #
    # OFF by default: it is a measured-equivalent behaviour change, staged per
    # CR201's rollout (re-run ablation arm v8 on the production assembly, then
    # Alpha, then the 150-ticker benchmark). Measured over 136 replayed convenes
    # (CR197): v8 22 approvals vs baseline 22 (16.4% vs 16.3%), net 0 verdicts
    # changed (9↑/9↓), p=1.0 — the same symmetric shape as replaying an identical
    # prompt. Designed degradation, not an outage: an unparseable or timed-out
    # officer falls back to the deterministic ladder alone (measured floor 11.8%,
    # vs 7.4% for no risk input) and the transcript is marked (CR040).
    #
    # Do NOT enable in the same window as PM_OPTION_LADDER_ENABLED above — that
    # flag shifts approvals ~5pp on its own and neither effect would be
    # attributable. Rollback is this flag; no migration.
    room_risk_officer_enabled: bool = False

    # CR219 R58 — the RESEARCHERS phase (Bull, then Bear) always speaks in that
    # fixed order today. `05_further_improvements.md` §12: LLM judges anchor on
    # order, and the Research Manager reads both — so the fixed order is a
    # standing source of decision variance nobody has measured.
    #
    # OFF by default: this flips the transcript's turn order, which is the
    # record itself, so it is a measured behaviour change like every other flag
    # in this block, not a pure fix. See WP13's replay
    # (`docs/forward_planning/CR219_room_prompt_contradictions/harness/results/`)
    # for the measurement this default is pending.
    #
    # ON: the order is a deterministic function of the run id — stable for that
    # run and any replay of it, ~50/50 Bull-first/Bear-first across runs. The
    # RISK phase's three-way debator order is OUT of scope (a different
    # question); only RESEARCHERS (Bull/Bear) is seeded.
    room_debate_order_seeded: bool = False

    # CR210 — JSON decoding grammars on the machine-read Room surfaces: the CIO
    # verdict, its DEF058 reformatter, and the CR201 Risk Officer. The model is
    # not asked to comply with a shape, it is prevented from emitting any other
    # one, so an off-ladder size and an off-contract action stop being unlikely
    # and become unrepresentable.
    #
    # OFF by default because a grammar changes what the model CAN say, which
    # makes this a measured behaviour change rather than a pure fix — the
    # before/after is CR196's held-out instrument through the same
    # `eval_surfaces.py --stage score`. Flip it after that has run, not before.
    #
    # The verdict and its reformatter move together, deliberately: the
    # reformatter exists to recover a PM reply that failed to parse, and a
    # recovery path weaker than the thing it recovers is not one. The Risk
    # Officer rides along and is itself gated by ROOM_RISK_OFFICER_ENABLED, so
    # this flag reaches it only when that one is also on — a flag on a flag would
    # be a third knob with no third decision behind it.
    #
    # Only the on-prem vLLM enforces these (verified against that server, not
    # assumed from the endpoint being OpenAI-compatible). Every other provider
    # records `constraint_status='unsupported'` in llm_audit, logs it, and runs
    # on CR143's tolerant parser — a degraded path that says so.
    room_json_constraints_enabled: bool = False

    # CR210 — the Execution Desk's money block as a regex grammar. Separate from
    # the flag above on purpose, for the reason the two flags above give about
    # not moving two things in one window: this one changes USER-VISIBLE prose
    # shape, feeds `_LEVEL_PATTERNS` / `_RR_CLAIM_RE` / `parse_stance_envelope`,
    # and takes `_verify_and_annotate_geometry` from firing rarely to firing on
    # every BUY turn. An incident on the Desk must not force the CIO's schema off
    # with it.
    #
    # This is the surface with the measured production gap: 99/136 recorded
    # convenes (73%) carried a readable `Side:` line, 119/136 (88%) allowing for
    # markdown bolding — so ~12% of Desk turns render with no labelled block.
    room_trader_regex_enabled: bool = False

    # CR221 A1 — the debt maturity ladder on the Room's fact sheet, sourced from
    # the five `LongTermDebtMaturitiesRepaymentsOfPrincipalIn*` tags the EDGAR
    # ingest now stores. Flagged not because the data is doubtful but because
    # CR221 §7 measures it: the control arm has to be a flag flip against one
    # cached profile, or "did the ask stop" is confounded by market data moving
    # between fetches. See `app/services/debt_maturity.py`.
    room_debt_maturity_enabled: bool = False

    # CR221 A3 — implied cost of debt on the fact sheet, from EDGAR interest
    # expense over EDGAR gross debt (`app/services/interest_cost.py`). Its own
    # flag rather than sharing A1's: §7 measures demand extinction PER ITEM, and
    # two fields behind one switch cannot be attributed separately. This one is
    # also the DEF399 fix vehicle — the numerator it sources is the one the
    # shipped `interest_coverage` gets wrong.
    room_cost_of_debt_enabled: bool = False

    # CR221 C3/C4 — the cash-flow bridge (operating cash flow, capex, the
    # derived free cash flow) plus the working-capital detail behind it. Nine
    # request lines from six agents, every operand already on the frame the
    # statements fetch pulls. Own flag for the same per-item attribution reason
    # as A1/A3 above.
    room_cashflow_bridge_enabled: bool = False

    # DEF400 — take `free_cash_flow` (and everything derived from it: the FCF
    # yield, and CR218's capital-return share) from the statements, OCF minus
    # capex, rather than `.info`'s pre-computed `freeCashflow`.
    #
    # Flagged because it MOVES a shipped, rendered number, and off by default
    # until CR221 §7 has measured it. What it moves it to is the checkable one:
    # measured 2026-09-03, `.info` puts CAT's TTM FCF at $5,049M against a
    # $8,994M subtraction that the frame's own `Free Cash Flow` row confirms to
    # the dollar, which turns CR218's capital-return line from 112% of free cash
    # flow into 200% — and "the 200% FCF payout" is verbatim what the Portfolio
    # Manager reasoned from in the CR219 corpus.
    fundamentals_fcf_from_statements_enabled: bool = False

    # CR221 C2 — multi-year free cash flow and capex, with their averages, off
    # the annual `tk.cashflow` frame. Its own flag from C5's below for the same
    # per-item attribution reason as A1/A3: two register items, two asks, two
    # different agents, and §7 has to be able to tell which one it moved.
    room_fcf_history_enabled: bool = False

    # CR221 C5 — free cash flow as a share of net income, year by year.
    room_fcf_conversion_enabled: bool = False

    # CR221 B2 — return on equity across the cycle plus its median, the half of
    # the Research Manager's ask R37's median multiples did not cover.
    room_roe_history_enabled: bool = False

    # CR221 A2 — the industrial vs. captive-finance debt split, read from the
    # filing's own consolidating columns (`services/filing_dimensions.py`).
    # 18 request lines from 9 agents, the single largest item in the register.
    # Renders only for filers in `edgar_tags.CAPTIVE_FINANCE`; for everyone
    # else the line does not exist, which is not a gap.
    room_debt_split_enabled: bool = False

    # CR221 D1 / D2 — revenue by business segment and by geography, from the
    # same instance documents. Two flags, one per register item, for §7's
    # per-item attribution rule.
    room_segment_revenue_enabled: bool = False
    room_geographic_revenue_enabled: bool = False

    # CR221 I1 — executive/board changes from the issuer's own 8-K Item 5.02
    # filings (`services/edgar_8k.py`). 5 request lines from one agent, the
    # News Analyst. Own flag for §7's per-item attribution; gates the RENDER
    # only, the overlay always populates. Store-backed: renders nothing until
    # `scripts/ingest_edgar_8k.py` has run (the `edgar_8k_not_ingested` warn
    # is the guard for the wrong order).
    room_executive_change_enabled: bool = False

    # CR222 §3 — pre-registration on the training trade ticket. With this on,
    # `safety_floor.check_mandate_compliance` refuses a training trade that
    # opens or adds to a position without a thesis, an invalidation and a
    # horizon. Off by default: it changes what a shipped ticket accepts, so it
    # goes live by a deliberate env flip, not by a deploy.
    training_preregistration_required: bool = False

    # CR222 §3 — whether the above also binds `long_horizon` mandates. Off:
    # the requirement is aimed at the active path, where an entry without a
    # written reason is the profile the evidence describes. A long-horizon user
    # buying an index position monthly is not that case, so they are exempt
    # until someone deliberately decides otherwise.
    prereg_applies_to_long_horizon: bool = False

    # CR222 §2 — the passive twin block in the Portfolio Health Finding: what a
    # mandate-matched passive holding would have returned on the same cash, on
    # the same dates, never traded. Off by default: it adds a block to a shipped,
    # permanently-archived report, so it goes live by a deliberate env flip.
    portfolio_passive_twin_enabled: bool = False

    # CR222 §2 — the mandate → passive instrument mapping. Two scalars rather
    # than a dict-shaped PASSIVE_TWIN_MAP: compose forwards scalars, and the map
    # has exactly two arms today (halal / everything else).
    #
    # The halal ticker DEFAULTS TO EMPTY on purpose. A halal mandate with no
    # configured Sharia-screened ETF must make the block `sufficient:false` with
    # a cause naming the unconfigured mapping — never fall back to SPY, which
    # would compare a halal user against a benchmark their own mandate forbids
    # and say nothing about it (CR040 / DEF059). An empty default is what makes
    # "nobody has chosen the halal instrument yet" impossible to mistake for
    # "the default is fine".
    passive_twin_default_ticker: str = "SPY"
    passive_twin_halal_ticker: str = ""

    # Annual expense ratio of each mapped instrument, in percentage points
    # (0.0945 = 9.45 bps). DISPLAY DATA in this slice — the block carries it so a
    # reader can see the twin is not free, and it is deliberately NOT subtracted
    # from the twin's return: the twin's prices are total-return adjusted closes
    # that already carry the fund's own drag, so applying it again would
    # double-count. A future slice that switches to an index rather than a fund
    # is where it would start being applied.
    passive_twin_default_expense_ratio_pct: float = 0.0945
    passive_twin_halal_expense_ratio_pct: float = 0.0

    # CR222 §2 — the two sufficiency floors, in MARKET DAYS (rows on the shared
    # NAV grid), not calendar days. Below the first the block carries no numbers
    # at all; between the two it carries the difference plus the machine state
    # saying that difference has no sampling-error estimate behind it. There is
    # no bootstrap in Portfolio Health and this CR does not build one
    # (CR222 Corrections §6), so the honest thing is to name the absence.
    twin_min_market_days: int = 20
    twin_min_market_days_for_se: int = 60

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

    # DEF044/DEF182 — at-rest encryption for Alpaca brokerage creds.
    # REQUIRED outside env=local: `secret_crypto.encrypt_secret` refuses to
    # store a credential without it rather than falling back to SECRET_KEY.
    # That fallback was the defect — one secret signing bearer tokens AND
    # protecting broker secrets means rotating SECRET_KEY silently orphans
    # every ciphertext row. Generate: openssl rand -hex 32
    # It must NOT equal SECRET_KEY. Setting them the same by hand recreates the
    # defect while labelling the rows enc::v2::, i.e. "independent of
    # SECRET_KEY" — refused at both the encrypt and decrypt site rather than
    # validated here, so the check sits next to the marker it defends.
    alpaca_encryption_key: str = ""

    # DEF182 — the previous ALPACA_ENCRYPTION_KEY, set ONLY during a rollover.
    # Reads try the current key first and fall back to this one, so a rotation
    # does not break rows at the instant of the swap. Clear it once every row
    # has been re-written under the new key. Empty is the steady state.
    # Read-side only: setting this while ALPACA_ENCRYPTION_KEY is empty makes
    # encrypt_secret refuse rather than write fresh rows under a retired key.
    alpaca_encryption_key_previous: str = ""

    # CR192 — how often to sample the vLLM host's /metrics for the two lifetime
    # prefix-cache counters. Hourly by default: the counters are cumulative, so
    # the sample rate sets the tightest window that can be derived, not the
    # precision of any single reading. 0 disables the tick.
    vllm_metrics_sample_interval_seconds: int = 3600

    # Admin back-office secret (AT:R27). Static bearer for Alpha single-operator
    # access. All /v1/admin/* routes require this. Empty = admin disabled.
    # Generate: openssl rand -hex 32
    # CR200: kept as the fallback path alongside Cloudflare Access below, so
    # agent scripts and LAN-direct access keep working; audit rows attribute
    # this path to the literal operator "static_bearer".
    admin_secret: str = ""

    # CR200 — Cloudflare Access (Zero Trust) in front of the management
    # console. When BOTH are set, get_admin verifies the Cf-Access-Jwt-
    # Assertion header against the team's JWKS and audit rows carry the
    # operator's CF email (human) or service-token name (agent). Half-set is
    # a config mistake: logged loudly, CF path stays disabled (CR040).
    #   CF_ACCESS_TEAM_DOMAIN: https://<team>.cloudflareaccess.com
    #   CF_ACCESS_AUD:         the Access application's Audience (AUD) tag
    cf_access_team_domain: str = ""
    cf_access_aud: str = ""

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
