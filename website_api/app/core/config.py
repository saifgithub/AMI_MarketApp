"""Settings — loaded once at startup from environment / .env file.

Presence-of-key turns a feature on (same convention as the app backend):
  - no VLLM_BASE_URL  → concierge/contact fall back to scripted KB replies
  - no RESEND_API_KEY → email sends are logged + skipped (local/dev)
  - no TURNSTILE_SECRET → captcha verification is bypassed (local/dev)
These degrade gracefully so the site works locally without any secrets.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "local"
    database_url: str = "sqlite:///./website.db"
    cors_origins: str = "https://www.agenticmarketintel.ai,https://agenticmarketintel.ai"

    # ── On-prem model (LAN) — same server the app backend uses ──────────────
    vllm_base_url: str = ""          # e.g. http://192.168.20.74:8000
    vllm_model: str = "ami-llm"
    vllm_api_key: str = ""           # optional bearer

    # ── Transactional email (Resend HTTP API) ───────────────────────────────
    resend_api_key: str = ""
    resend_from: str = "AMI <support.ai@agenticmarketintel.ai>"
    notify_email: str = ""           # where escalations/data-requests are forwarded

    # ── Bot protection (Cloudflare Turnstile) ───────────────────────────────
    turnstile_secret: str = ""       # unset → verification bypassed (local/dev)


settings = Settings()
