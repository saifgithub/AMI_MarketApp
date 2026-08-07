"""AUDITOR pin (CR131 round 1) — the mandate.py <-> day_trader_outcomes.py string coupling.

`day_trader_outcomes.DAY_TRADER_JOURNAL_MARKER` cohort-detects by PREFIX-matching a
journal summary sentence that `mandate.py:154-157` writes independently, on its own
copy, with nothing structurally forcing the two to agree. The architect flagged this
himself as CR131's weakest seam; CR129 (which owns that copy) is `in_progress`.

Every existing CR131 test drives the marker through a hand-rolled test helper
(`_switch_day_trader`, built from `DAY_TRADER_JOURNAL_MARKER` itself) rather than the
real PATCH endpoint, so none of them can catch real drift. Proven by mutation during
audit round 1: rewording `mandate.py`'s summary from "...preset applied — ..." to
"...preset now active — ..." (still containing the substring "Day Trader preset",
which is all CR129's OWN test — `test_day_trader_preset_patch_journals_its_own_
distinct_summary` — checks for) left the full 2588-test suite green while silently
making `compute_day_trader_outcomes` return `not_in_cohort` for a user who had, in
fact, just switched on the preset. That failure is indistinguishable from "this user
never tried the preset" — exactly the silent-degrade shape CLAUDE.md's "degrade
loudly" rule exists to catch, and exactly what this pin closes: it drives the REAL
`PATCH /v1/mandate/{user_id}` handler (not a hand-rolled summary) and asserts the
REAL cohort-detection function accepts what it wrote.

Judged MAJOR, not MINOR, in `orchestration/audit/cr/CR131.auditor.md`: CR129 is
actively in flight (a live `coder.api-CR129-BE` lane existed at audit time), the
failure is 100% silent, and this pin is the only thing in the suite that would have
caught it. Delete only once a shared constant replaces the two independent literals
(the architect's own suggested fix) and note why in the same commit.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.mandate import router as mandate_router
from app.services.auth_service import AuthService
from app.services.day_trader_outcomes import (
    STATUS_NOT_IN_COHORT,
    compute_day_trader_outcomes,
)
from app.services.day_trader_preset import DAY_TRADER_PRESET_OVERRIDES


def _new_user() -> tuple[UUID, dict]:
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


def test_real_mandate_patch_is_recognised_by_real_cohort_detection():
    app = FastAPI()
    app.include_router(mandate_router)
    client = TestClient(app, raise_server_exceptions=False)

    user_id, hdr = _new_user()
    r = client.patch(
        f"/v1/mandate/{user_id}", json=dict(DAY_TRADER_PRESET_OVERRIDES), headers=hdr,
    )
    assert r.status_code == 200, r.text

    result = compute_day_trader_outcomes(user_id)
    assert result["status"] != STATUS_NOT_IN_COHORT, (
        "mandate.py's real PATCH-written journal summary was not recognised by "
        "day_trader_outcomes.py's cohort marker — the two literals have drifted. "
        f"Got: {result!r}"
    )
