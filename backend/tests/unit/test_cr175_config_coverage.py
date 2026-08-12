"""CR175 Tier B — the config gate stops being a hand-written list.

`/v1/admin/config-check` exists because DEF038 and DEF063 shipped dark for want
of one compose line. It reports `_FEATURE_GATES`, which is maintained by hand,
and **nothing fails when that list is incomplete** — so it drifted. Measured
against live Alpha on 2026-08-12 it reported **9 gates against 98 `Settings`
fields**, and the specific miss is the one that proves the shape:
`adanos_api_key_secondary` had been wired that same week *because* 250 paid
calls/month sat idle undetected, reached compose, reached `Settings`, and was
still invisible to the check whose entire job is catching exactly that.

Adding it to the list by hand would have been the fourth instance of the same
fix. These tests make the coverage derived instead, and — the part that matters —
assert the derived path covers what the hand list does not, so the guard has
been seen distinguishing the two states rather than merely passing.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin import _FEATURE_GATES, _settings_coverage
from app.api.admin import router as admin_router
from app.core.config import Settings, settings


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(admin_router)
    return TestClient(app, raise_server_exceptions=False)


def test_every_settings_field_is_covered() -> None:
    """The structural claim. A field added tomorrow is covered the day it is
    added, because the set is derived from `Settings.model_fields` rather than
    from anyone remembering."""
    covered = {row.setting for row in _settings_coverage()}
    expected = {name.upper() for name in Settings.model_fields}
    assert covered == expected, f"uncovered: {sorted(expected - covered)}"


def test_the_hand_written_list_does_not_cover_what_derivation_does() -> None:
    """F3, asserted rather than described — and this is the red-before-green.

    Against the pre-fix implementation (`_FEATURE_GATES` alone) the assertion
    below on `ADANOS_API_KEY_SECONDARY` fails: the field is genuinely absent
    from the hand-written list. It passes only because coverage is now derived.
    If someone later "fixes" this by adding the field to `_FEATURE_GATES`, the
    first assertion here fails and says why that is the wrong fix.
    """
    hand_written = {attr.upper() for attr, _n, _e in _FEATURE_GATES}
    derived = {row.setting for row in _settings_coverage()}

    assert "ADANOS_API_KEY_SECONDARY" not in hand_written, (
        "Do not close this gap by extending _FEATURE_GATES — that is the fourth "
        "instance of the same fix and leaves the next field uncovered."
    )
    assert "ADANOS_API_KEY_SECONDARY" in derived
    assert len(derived) > len(hand_written) * 5, (
        f"derived={len(derived)} hand_written={len(hand_written)} — the whole "
        "point is that the curated list is a small subset"
    )


def test_annotated_flag_marks_which_fields_carry_human_prose() -> None:
    """Derivation gives coverage; the annotations give an operator the *effect*
    of a missing key. Both are needed, and the flag says which a field has."""
    rows = {row.setting: row for row in _settings_coverage()}
    hand_written = {attr.upper() for attr, _n, _e in _FEATURE_GATES}

    for name, row in rows.items():
        assert row.annotated is (name in hand_written)

    assert rows["ADANOS_API_KEY"].annotated is True
    assert rows["ADANOS_API_KEY_SECONDARY"].annotated is False


def test_configured_is_a_boolean_never_a_value(monkeypatch) -> None:
    """CR040's rule for this endpoint: booleans only, never the secret."""
    monkeypatch.setattr(settings, "adanos_api_key_secondary", "sk-live-not-a-real-key")

    rows = {row.setting: row for row in _settings_coverage()}
    assert rows["ADANOS_API_KEY_SECONDARY"].configured is True
    assert "sk-live-not-a-real-key" not in repr(rows)


def test_false_boolean_setting_reports_false_not_truthy(monkeypatch) -> None:
    """`bool` fields are passed through rather than presence-tested, so
    `USE_REAL_MARKET_DATA=false` reads False instead of the truthiness of a
    non-empty string — the shape DEF260 turned on."""
    monkeypatch.setattr(settings, "use_real_market_data", False)
    rows = {row.setting: row for row in _settings_coverage()}
    assert rows["USE_REAL_MARKET_DATA"].configured is False

    monkeypatch.setattr(settings, "use_real_market_data", True)
    rows = {row.setting: row for row in _settings_coverage()}
    assert rows["USE_REAL_MARKET_DATA"].configured is True


def test_endpoint_surfaces_the_coverage(client: TestClient, monkeypatch) -> None:
    """The set-diff `scripts/promotion/postflight.py` runs needs the whole set
    over the wire, not just the curated view."""
    monkeypatch.setattr(settings, "admin_secret", "test-admin-secret")
    r = client.get(
        "/v1/admin/config-check",
        headers={"Authorization": "Bearer test-admin-secret"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["settings_total"] == len(Settings.model_fields)
    names = {row["setting"] for row in body["settings_coverage"]}
    assert "ADANOS_API_KEY_SECONDARY" in names
    # The curated view and its count are unchanged — this tier adds a view,
    # it does not redefine dark_count out from under the promotion protocol.
    assert len(body["gates"]) == len(_FEATURE_GATES)
