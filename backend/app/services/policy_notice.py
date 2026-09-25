"""policy_notice — DEF430, the one-time Privacy Policy v2.1 notice.

Saiful's 2026-09-25 ruling ("publish + link-screen notice"): anyone who had
already linked an Alpaca account before the DEF430 fix shipped must be told
that Privacy Policy v2.1 now describes what the app sends AMI for a linked
account. `notify_policy_update()` is that notice, sent exactly once per
qualifying user.

Targeting: every `User` row with `alpaca_linked_at IS NOT NULL` — the exact
predicate the DEF430 row names. The sweep runs on every boot, so someone who
links later is also told once, at the next restart. That is deliberate: a
user linking from an app build older than the DEF430 disclosure never saw
it, and for one who did, a second pointer to the policy costs nothing.

Idempotency is the same three-legged shape `daily_reminder.py` documents,
minus the recompute-under-a-changing-clock leg that module needs and this
one does not (there is no "today", so no second run can compute a different
`source_ref` for the same user):

  1. `source_ref` is a FIXED constant (`_SOURCE_REF`), not date-derived —
     one qualifying user gets AT MOST one `policy_update` row, ever, no
     matter how many times this runs.
  2. `notify()`'s own `uq_notifications_dedupe` unique constraint
     (`user_id`, `type`, `source_ref`) is what actually enforces it: a
     re-run's `notify()` call for an already-notified user raises
     `IntegrityError` inside `notify()`, which converts it into a
     `push_status="duplicate"` `NotifyResult` rather than a second row or an
     exception here. That makes "at most once" a property of the data, safe
     under concurrent workers or a container restart mid-sweep, not
     something this module's own bookkeeping has to get right.

Called best-effort from the FastAPI lifespan (`app/main.py`) on every boot,
mirroring `_nightly_audit_trim`/`_sharia_universe_refresh`'s own
try/except-and-log posture — a qualifying user who is somehow missed by one
boot is caught by the next, and a failure here must never block startup.
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.logging import logger
from app.db import get_session, init_schema
from app.db.models import User
from app.services.notification_service import notify

# Named the same way `daily_reminder._NOTIFICATION_TYPE` is — the constant
# `test_cr135_notifications_api.py::test_vocabulary_matches_every_emitter`
# checks against `NOTIFICATION_TYPES`, so a typo here fails pytest, not a
# user's centre silently rendering an unlabelled row.
_NOTIFICATION_TYPE = "policy_update"

# Fixed, not date- or run-derived — see the module docstring's idempotency
# note. Changing this string would let every qualifying user be notified
# again, so it must never be touched for anything short of a deliberate
# "re-notify everyone" decision.
_SOURCE_REF = "def430_privacy_v2_1"

_TITLE = "Privacy Policy updated (v2.1)"
_BODY = (
    "Privacy Policy v2.1 describes what AMI receives when you link an "
    "Alpaca account."
)
_DEEP_LINK = {
    "route": "open_privacy_policy",
    "params": {"url": "https://www.agenticmarketintel.ai/privacy/"},
}


def notify_policy_update_v2_1() -> dict[str, int]:
    """One sweep. Returns stats the same shape `daily_reminder`'s own sweep
    does, so a boot log line answers "how many were actually notified" as a
    checkable claim, not an assumption from "the job ran"."""
    init_schema()
    stats = {"eligible": 0, "notified": 0, "already_notified": 0, "errors": 0}

    with get_session() as s:
        user_ids = s.execute(
            select(User.id).where(User.alpaca_linked_at.is_not(None))
        ).scalars().all()

    for user_id in user_ids:
        stats["eligible"] += 1
        try:
            result = notify(
                user_id=user_id,
                type=_NOTIFICATION_TYPE,
                title=_TITLE,
                body=_BODY,
                deep_link=_DEEP_LINK,
                source_ref=_SOURCE_REF,
            )
            if result.was_duplicate:
                stats["already_notified"] += 1
            else:
                stats["notified"] += 1
        except Exception:
            stats["errors"] += 1
            logger.exception(
                "policy_update_notice_error", user_id=str(user_id),
            )

    return stats
