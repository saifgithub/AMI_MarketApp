"""CR200 — admin action audit trail.

Every admin WRITE (plan change, credits, trial, suspend, push send, bug
claim/resolve, broadcast, release floor) records one `admin_audit` row naming
the operator (CF Access email, service-token name, or "static_bearer") and
what they did. This is the multi-operator attribution layer the single shared
ADMIN_SECRET never had.

The row is added to the CALLER's session, so it commits atomically with the
action it describes — an audit row never records an action that rolled back,
and a second session never contends with the in-flight transaction. Row
construction is still guarded: a malformed payload must never break the admin
request itself. Deliberately NOT included in `trim_audit_tables()`'s 90-day
retention — volume is human-scale and forensic value is permanent.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog

from app.db.models import AdminAuditRow
from app.services.cf_access import AdminIdentity

logger = structlog.get_logger(__name__)


def record_admin_action(
    session,
    identity: AdminIdentity,
    action: str,
    target: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Add one admin-audit row to the caller's session. Never raises."""
    try:
        session.add(AdminAuditRow(
            id=uuid4(),
            operator=identity.operator,
            auth_kind=identity.kind,
            action=action,
            target=target,
            payload=payload,
            created_at=datetime.now(timezone.utc),
        ))
    except Exception as e:
        logger.warning(
            "admin_audit_write_failed",
            action=action,
            target=target,
            error=str(e),
        )
