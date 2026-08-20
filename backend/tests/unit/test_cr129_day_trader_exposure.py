"""CR129 Slice A — the mandate read path serves the Day Trader preset.

`DAY_TRADER_PRESET_OVERRIDES` and `DAY_TRADER_DISCLOSURE` existed as module
constants that nothing served (only tests and `is_day_trader_preset` inside
the PATCH handler referenced them), which blocked CR129-MOBILE items 2-3: the
mobile picker is fenced to be server-sourced only ("Do NOT hard-code any
preset value or cap"). These tests pin the exposure:

1. GET/PATCH responses carry `day_trader_preset` whose values ARE the module
   constants — asserted by importing them, never by re-typing a literal, so
   there stays exactly one source of truth.
2. The load-bearing round-trip: PATCHing the SERVED overrides map back
   verbatim is recognised by `is_day_trader_preset()` and journals the CR131
   cohort marker, and the REAL cohort detector accepts it. A future rename of
   one key in the constant goes RED here instead of silently breaking the
   mobile picker and `day_trader_outcomes.py` cohort detection at once.
3. The stamped objects are client-unwritable (CLIENT_UNWRITABLE_MANDATE_FIELDS):
   a hostile PATCH of `day_trader_preset` / `resolved` must not pollute the
   stored snapshot — current reads re-stamp, but BL5 historical version reads
   return RAW snapshots un-restamped.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import router as auth_router
from app.api.mandate import router as mandate_router
from app.schemas.journal import EntryType
from app.services.auth_service import AuthService
from app.services.day_trader_outcomes import (
    STATUS_NOT_IN_COHORT,
    compute_day_trader_outcomes,
)
from app.services.day_trader_preset import (
    DAY_TRADER_DISCLOSURE,
    DAY_TRADER_JOURNAL_MARKER,
    DAY_TRADER_PRESET_OVERRIDES,
)
from app.services.journal_store import get_journal_store
from app.services.mandate_store import MandateStore


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(mandate_router)
    return TestClient(app, raise_server_exceptions=False)


def _new_user():
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


def _last_mandate_edit_summary(user_id: UUID) -> str:
    entries, _, _ = get_journal_store().list_for_user(
        user_id, entry_type=EntryType.MANDATE_EDIT, limit=20,
    )
    assert entries, "expected a MANDATE_EDIT journal entry"
    return entries[0].summary or ""


def test_get_serves_the_day_trader_constants_verbatim(client: TestClient):
    """t1: both constants on the GET body, equal to the imported module
    constants — one source of truth, no literals in this test."""
    user_id, headers = _new_user()
    resp = client.get(f"/v1/mandate/{user_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    preset = resp.json()["day_trader_preset"]
    assert preset is not None
    assert preset["overrides"] == dict(DAY_TRADER_PRESET_OVERRIDES)
    assert preset["disclosure"] == DAY_TRADER_DISCLOSURE


def test_patching_the_served_overrides_verbatim_is_recognised_as_the_preset(
    client: TestClient,
):
    """t2 — the load-bearing round-trip: served payload == recognised payload.

    Unlike test_cr131_cohort_marker_coupling_pin (which PATCHes the constant
    directly), this drives the SERVED map: GET → PATCH the response's own
    overrides → the journal summary carries the CR131 cohort marker AND the
    real cohort detector accepts the user. Renaming one key in
    DAY_TRADER_PRESET_OVERRIDES (or doctoring one served value) goes red here.
    """
    user_id, headers = _new_user()
    served = client.get(f"/v1/mandate/{user_id}", headers=headers).json()[
        "day_trader_preset"
    ]["overrides"]

    r = client.patch(f"/v1/mandate/{user_id}", json=served, headers=headers)
    assert r.status_code == 200, r.text

    summary = _last_mandate_edit_summary(user_id)
    assert summary.startswith(DAY_TRADER_JOURNAL_MARKER), (
        "PATCHing the SERVED overrides map verbatim was not recognised as the "
        f"Day Trader preset — served != recognised. Journal summary: {summary!r}"
    )
    result = compute_day_trader_outcomes(user_id)
    assert result["status"] != STATUS_NOT_IN_COHORT, (
        "real cohort detection did not accept a switch applied from the "
        f"SERVED overrides — got {result!r}"
    )


def test_patch_response_also_carries_the_stamp(client: TestClient):
    """t3: patch_mandate returns through _with_plan_state too, so the mobile
    notifier (which replaces its state with the PATCH response) keeps the
    preset data without a follow-up GET."""
    user_id, headers = _new_user()
    r = client.patch(
        f"/v1/mandate/{user_id}", json={"max_open_positions": 5}, headers=headers,
    )
    assert r.status_code == 200, r.text
    preset = r.json()["day_trader_preset"]
    assert preset is not None
    assert preset["overrides"] == dict(DAY_TRADER_PRESET_OVERRIDES)
    assert preset["disclosure"] == DAY_TRADER_DISCLOSURE


def test_stamped_objects_are_client_unwritable(client: TestClient):
    """t4: a hostile PATCH of `day_trader_preset` / `resolved` is dropped
    before the merge (CLIENT_UNWRITABLE_MANDATE_FIELDS) — the next GET still
    serves the real constants and, decisively, the STORED snapshot stays
    unpolluted (BL5 version reads return raw snapshots without re-stamping)."""
    user_id, headers = _new_user()
    r = client.patch(
        f"/v1/mandate/{user_id}",
        json={
            "day_trader_preset": {
                "overrides": {"sector_cap_pct": 1.0},
                "disclosure": "junk the client made up",
            },
            "resolved": {
                "sector_cap_pct": 1.0,
                "single_name_cap_pct": 1.0,
                "max_open_positions": 1,
                "post_loss_cooldown_hours": 1.0,
                "max_trades_per_day": 1,
                "max_trades_per_week": 1,
                "max_open_risk_pct": 1.0,
            },
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text

    body = client.get(f"/v1/mandate/{user_id}", headers=headers).json()
    assert body["day_trader_preset"]["overrides"] == dict(DAY_TRADER_PRESET_OVERRIDES)
    assert body["day_trader_preset"]["disclosure"] == DAY_TRADER_DISCLOSURE

    stored = MandateStore().get(user_id)
    assert stored is not None
    assert stored.day_trader_preset is None, (
        "client junk persisted into the stored mandate snapshot — BL5 raw "
        "version reads would serve it un-restamped"
    )
    assert stored.resolved is None, (
        "client-supplied `resolved` persisted into the stored snapshot"
    )
