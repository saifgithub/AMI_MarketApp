"""Tests for the Mandate store + resolver."""

from __future__ import annotations

from uuid import uuid4

from app.services.mandate_store import MandateStore, resolve_mandate, get_mandate_store


def test_default_is_returned_when_nothing_stored():
    store = MandateStore()
    user_id = uuid4()
    m = store.get_or_default(user_id)
    assert m.user_id == user_id
    assert m.risk_score == 3  # hydrate default


def test_patch_bumps_version_and_merges_compliance():
    store = MandateStore()
    user_id = uuid4()
    m1 = store.patch(user_id, {"risk_score": 5})
    assert m1.version == 1
    assert m1.risk_score == 5

    m2 = store.patch(user_id, {"compliance": {"halal": True}})
    assert m2.version == 2
    assert m2.risk_score == 5  # preserved
    assert m2.compliance.halal is True

    # second compliance edit keeps prior compliance fields
    m3 = store.patch(user_id, {"compliance": {"esg_lite": True}})
    assert m3.version == 3
    assert m3.compliance.halal is True
    assert m3.compliance.esg_lite is True


def test_resolve_mandate_prefers_store_over_override():
    # Use the module-level singleton so resolve_mandate sees the same instance
    store = get_mandate_store()
    store.clear()
    user_id = uuid4()
    store.patch(user_id, {"risk_score": 5})

    resolved = resolve_mandate(user_id, {"risk_score": 1}, locale="ar")
    # Stored mandate (risk_score=5) wins; locale override applies
    assert resolved.risk_score == 5
    assert resolved.locale == "ar"


def test_resolve_mandate_falls_back_to_override_when_no_store():
    store = get_mandate_store()
    store.clear()
    user_id = uuid4()
    resolved = resolve_mandate(user_id, {"risk_score": 1}, locale="en")
    assert resolved.risk_score == 1
    assert resolved.user_id == user_id
