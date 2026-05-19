"""Runtime config — all secrets via env vars, all environments via Pydantic Settings."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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

    # SMTP (magic-link email delivery). When smtp_host is empty the backend
    # falls back to debug-code-only mode (code shown in UI for alpha testers).
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # Server
    port: int = 8000


settings = Settings()
