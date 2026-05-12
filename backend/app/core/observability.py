"""Sentry initialisation for the AMI Trade backend (A10).

Imported once from `app.main` before the FastAPI app is constructed. We
keep the integration tiny on purpose:

  * `auto_enabling_integrations` is enabled — FastAPI + Starlette get
    picked up automatically.
  * No PII is sent. The default `send_default_pii=False` already covers
    that; we still scrub `Authorization` and `cookie` headers in
    `before_send` defensively.
  * Sampling defaults are conservative for Alpha. Beta will bump them
    once we have real traffic to see.

When `SENTRY_DSN` is empty (dev), `init_sentry` is a no-op and no SDK
is initialised — so unit tests don't accidentally talk to Sentry.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.logging import logger

_SENSITIVE_HEADERS = {"authorization", "cookie", "x-api-key"}


def _before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Scrub sensitive request headers before shipping the event."""
    request = event.get("request") or {}
    headers = request.get("headers")
    if headers:
        if isinstance(headers, list):
            request["headers"] = [
                (k, "***") if k.lower() in _SENSITIVE_HEADERS else (k, v)
                for k, v in headers
            ]
        elif isinstance(headers, dict):
            request["headers"] = {
                k: ("***" if k.lower() in _SENSITIVE_HEADERS else v)
                for k, v in headers.items()
            }
    return event


def init_sentry() -> bool:
    """Idempotent. Returns True if the SDK initialised, False otherwise."""
    dsn = settings.sentry_dsn.strip()
    if not dsn:
        logger.info("sentry_skipped", reason="no SENTRY_DSN in env")
        return False
    try:
        import sentry_sdk
    except ImportError:  # pragma: no cover — sentry-sdk listed in pyproject
        logger.warn("sentry_skipped", reason="sentry_sdk not importable")
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=settings.env,
        release="ami-trade-backend@0.1.0",
        send_default_pii=False,
        traces_sample_rate=0.1 if settings.env == "prod" else 0.0,
        profiles_sample_rate=0.0,
        before_send=_before_send,
        attach_stacktrace=True,
        max_breadcrumbs=50,
    )
    logger.info("sentry_initialised", env=settings.env)
    return True
