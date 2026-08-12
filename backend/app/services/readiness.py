"""Readiness probes — what `/v1/health` never checked (CR175 Tier A).

`/v1/health` returns a hardcoded literal. It is also the container's only
healthcheck probe AND `/promote-to-alpha`'s primary smoke check, so "healthy"
has always meant *uvicorn is accepting connections* and nothing else. A
container with an unreachable Postgres, a down vLLM, or — the one that has
actually cost us an outage — a schema behind head reports healthy, passes the
promotion's block-until-healthy step, passes the smoke check, and the promotion
is reported successful.

DEF215 is the proof. Its outage state (Alembic chain aborted, two migrations
never run, every journal read failing) is a state the healthcheck calls healthy.

This module is what a promotion should actually ask. Each probe is independent
and none of them raise: a probe that throws returns `ok=False` with the reason,
because a readiness endpoint that 500s tells the operator less than one that
says which dependency is down.

**Liveness stays liveness.** `/v1/health` keeps its contract as the container
healthcheck — a probe that fails on a transient dependency blip would have
Docker restart-loop the container, which is a worse failure than the one being
detected. `/v1/ready` is the promotion's gate, not Docker's.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Probe:
    """One dependency's verdict.

    `gating` is the whole point of the type: a probe can be worth reporting
    without being worth failing a promotion over, and collapsing the two is how
    checks end up either toothless or noisy.
    """

    name: str
    ok: bool
    gating: bool
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "gating": self.gating, **self.detail}


def _probe_db() -> Probe:
    from sqlalchemy import text

    from app.db import get_session

    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
        return Probe("db", ok=True, gating=True)
    except Exception as exc:
        return Probe("db", ok=False, gating=True, detail={"error": type(exc).__name__})


def _probe_schema() -> Probe:
    """`alembic current` vs the code's own head — the DEF215 detector.

    `app.db.session._report_if_behind_head` already logs this at boot. Logging
    it was not enough: the log line is only read by someone who already suspects
    a problem. This returns it as a value a promotion can fail on.
    """
    try:
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        from app.db.session import _alembic_config, get_engine

        engine = get_engine()
        cfg = _alembic_config(engine)
        if cfg is None:
            # The slim test image ships no alembic.ini. Not a deploy state:
            # report it rather than inventing a pass or a fail.
            return Probe("schema", ok=True, gating=False,
                         detail={"note": "alembic.ini not shipped in this image"})
        head = ScriptDirectory.from_config(cfg).get_current_head()
        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
        return Probe(
            "schema",
            ok=(head is None or current == head),
            gating=True,
            detail={"current_revision": current, "head_revision": head},
        )
    except Exception as exc:
        return Probe("schema", ok=False, gating=True,
                     detail={"error": type(exc).__name__})


def _probe_llm(env: str) -> Probe:
    """Provider resolution only — never calls the provider.

    Gating in `staging`/`prod` because of DEF059: with the LLM down the Room
    fell through to a confident fake APPROVE. A promotion that lands a container
    whose gateway resolves to `mock` has shipped that failure mode.
    """
    from app.services.llm_gateway import get_llm_gateway

    try:
        status = get_llm_gateway().status()
        real = bool(status.get("has_real_provider"))
        return Probe(
            "llm",
            ok=real,
            gating=env in ("staging", "prod"),
            detail={
                "active_provider": status.get("active_provider"),
                "has_real_provider": real,
            },
        )
    except Exception as exc:
        return Probe("llm", ok=False, gating=env in ("staging", "prod"),
                     detail={"error": type(exc).__name__})


def _probe_redis() -> Probe:
    """Reported, never gating — and the detail says why.

    `redis_url` is a Settings field, `redis>=5.2` is a main dependency, and
    compose blocks `api-alpha` on `redis: condition: service_healthy`. But
    `grep -rn "import redis" app/` returns nothing: **no application code opens
    a Redis connection.** Probing it as a gate would fail promotions over a
    service the app does not use; omitting it entirely would hide that the
    dependency is declared three ways and used none. So it is reported with the
    fact attached. Removing the dependency is not this CR's scope.
    """
    try:
        import redis

        from app.core.config import settings

        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        client.ping()
        client.close()
        return Probe("redis", ok=True, gating=False,
                     detail={"opened_by_app_code": False})
    except Exception as exc:
        return Probe("redis", ok=False, gating=False,
                     detail={"error": type(exc).__name__, "opened_by_app_code": False})


def readiness_report() -> dict[str, Any]:
    """Every probe, plus the deploy identity, plus one boolean to gate on.

    `ready` is false when any **gating** probe failed. The deploy stamp is
    reported but never gates: an unstamped container is a promotion-protocol
    failure, which `scripts/promotion/postflight.py` fails on by comparing the
    sha it promoted — making it a readiness failure here would brick a
    hand-started container over a diagnostic field.
    """
    from app.core.config import settings

    probes = [
        _probe_db(),
        _probe_schema(),
        _probe_llm(settings.env),
        _probe_redis(),
    ]
    ready = all(p.ok for p in probes if p.gating)
    failed = [p.name for p in probes if p.gating and not p.ok]
    if not ready:
        logger.error("readiness_failed", failed_probes=failed)
    return {
        "ready": ready,
        "env": settings.env,
        "git_sha": settings.git_sha,
        "alpha_tag": settings.alpha_tag,
        "deploy_stamped": settings.git_sha != "unset",
        "failed_probes": failed,
        "probes": [p.as_dict() for p in probes],
    }
