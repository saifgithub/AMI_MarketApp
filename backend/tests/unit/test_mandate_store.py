"""Tests for the Mandate store + resolver."""

from __future__ import annotations

from uuid import uuid4

import pytest

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


def test_patch_nested_risk_components_key_preserves_siblings():
    """CR101-BE1 acceptance 1: `PATCH {"risk_components": {"concentration_tolerance": 4}}`
    must not drop `drawdown_response` / `regret_asymmetry` — the shallow-merge bug that
    blocked every settable-cap PATCH (DEF062's re-validation 422'd on the resulting
    incomplete object). Assert the SIBLINGS survive, not merely that the call returns."""
    store = MandateStore()
    user_id = uuid4()
    before = store.get_or_default(user_id)
    assert before.risk_components.drawdown_response == 3
    assert before.risk_components.regret_asymmetry == 0

    updated = store.patch(user_id, {"risk_components": {"concentration_tolerance": 4}})

    assert updated.risk_components.concentration_tolerance == 4
    assert updated.risk_components.drawdown_response == 3  # sibling survived
    assert updated.risk_components.regret_asymmetry == 0  # sibling survived


def test_patch_nested_merge_still_rejects_invalid_sibling_type():
    """DEF062 must survive the merge change (CR101-BE1 acceptance 2): a nested PATCH
    that leaves a sibling with an out-of-range value still 422s via re-validation,
    it doesn't silently persist because the merge is now recursive."""
    from pydantic import ValidationError

    store = MandateStore()
    user_id = uuid4()
    with pytest.raises(ValidationError):
        store.patch(user_id, {"risk_components": {"concentration_tolerance": 99}})
    assert store.get_or_default(user_id).risk_components.concentration_tolerance != 99


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
