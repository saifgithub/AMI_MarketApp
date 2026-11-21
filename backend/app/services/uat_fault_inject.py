"""Scoped, non-production server-fault switch for device UAT (CR239 / WP-38).

Why: UAT-PLAT-008 must show a "Ref: xxxxxxxx" trace on a phone error state and
follow it to the backend log, the `http_audit` row and the bug report. A phone
cannot force a server 5xx through normal UI, so the operator names one lab user
and one or more routes in `UAT_FAULT_INJECT`; only that user's calls to only
those routes answer 503. It is an app-level dependency that raises
`HTTPException`, so the response goes through the same handler (and the same
server-minted `request_id` / `http_audit` row) as every other server error.

Inert unless `env` is local/dev/staging; refused loudly elsewhere. Malformed
config stops the boot (CR040) rather than leaving the operator believing a
fault is armed when it is not.
"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.core.logging import logger
from app.services.auth_service import parse_scaffold_token_user_id

ALLOWED_ENVS = frozenset({"local", "dev", "staging"})

_active: dict[UUID, frozenset[str]] = {}


def _route_key(entry: object) -> str:
    parts = entry.split(" ") if isinstance(entry, str) else []
    if len(parts) != 2 or not parts[1].startswith("/"):
        raise RuntimeError(
            'Refusing to start: UAT_FAULT_INJECT routes must be "METHOD /path" strings'
        )
    return f"{parts[0].upper()} {parts[1]}"


def _parse(raw: str) -> dict[UUID, frozenset[str]]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Refusing to start: UAT_FAULT_INJECT is not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Refusing to start: UAT_FAULT_INJECT must be a JSON object")
    out: dict[UUID, frozenset[str]] = {}
    for user, routes in data.items():
        try:
            uid = UUID(str(user))
        except ValueError as exc:
            raise RuntimeError(
                "Refusing to start: UAT_FAULT_INJECT keys must be user UUIDs"
            ) from exc
        if not isinstance(routes, list) or not routes:
            raise RuntimeError(
                "Refusing to start: UAT_FAULT_INJECT values must be non-empty route lists"
            )
        out[uid] = frozenset(_route_key(r) for r in routes)
    return out


def configure(raw: str, env: str) -> None:
    global _active
    _active = {}
    if not raw.strip():
        return
    if env not in ALLOWED_ENVS:
        logger.error("uat_fault_inject_refused", env=env)
        return
    _active = _parse(raw)
    logger.warning(
        "uat_fault_inject_active",
        users=len(_active),
        routes=sum(len(v) for v in _active.values()),
    )


def configure_from_settings() -> None:
    configure(settings.uat_fault_inject, settings.env)


async def fault_hook(request: Request) -> None:
    if not _active:
        return
    authorization = request.headers.get("authorization") or ""
    if not authorization.lower().startswith("bearer "):
        return
    try:
        user_id = parse_scaffold_token_user_id(authorization.split(" ", 1)[1])
    except Exception:
        return
    routes = _active.get(user_id) if user_id is not None else None
    key = f"{request.method.upper()} {request.url.path}"
    if routes is None or key not in routes:
        return
    logger.warning(
        "uat_fault_injected",
        route=key,
        request_id=str(getattr(request.state, "request_id", None)),
    )
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "service temporarily unavailable")
