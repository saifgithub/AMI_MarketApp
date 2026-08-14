"""DEF246 — the CR040 register must not certify a feature that has no code.

`/v1/admin/config-check` exists because DEF038 and DEF063 each shipped dark for want of
one compose line. It computes `configured = bool(value)`, so listing a setting whose
feature was never built inverts the whole point: set `POSTHOG_API_KEY` and the register
built to catch silently-dark features reports product analytics LIVE, and `dark_count`
drops by one to agree.

The guard is deliberately **coupled, not a hardcoded ban**. Asserting "posthog is never a
gate" would be wrong the day someone wires it, and would train the next person to delete
the test rather than read it. Instead these tests derive whether instrumentation exists
and require the gate to match — so the gate returns automatically when the feature does,
and can never return without it.

Mac-safe: pure source inspection plus the in-process app. No backend, no DB, no network.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin import _FEATURE_GATES, _settings_coverage
from app.api.admin import router as admin_router
from app.core.config import Settings, settings

_REPO_ROOT = Path(__file__).resolve().parents[3]

# The two trees where a call site could live. `infra/`, `.env.example` and
# `docker-compose.yml` are deliberately NOT searched: those are exactly the plumbing this
# defect is about, and counting them as evidence would make the guard certify itself.
_CODE_ROOTS = (_REPO_ROOT / "backend" / "app", _REPO_ROOT / "mobile" / "lib")

# An import or a client construction, not the bare word — `posthog_api_key: str = ""` in
# config.py and this file's own prose must not read as instrumentation.
_INSTRUMENTATION = re.compile(
    r"""(import\s+posthog)|(from\s+posthog)|(package:posthog)|(Posthog\s*\()"""
    r"""|(posthog\s*\.\s*(capture|identify|flush))""",
    re.IGNORECASE,
)


def _instrumentation_sites() -> list[str]:
    """Files that actually SEND an event, as opposed to naming the setting."""
    hits: list[str] = []
    for root in _CODE_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.suffix not in {".py", ".dart"} or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:  # pragma: no cover - unreadable file
                continue
            if _INSTRUMENTATION.search(text):
                hits.append(str(path.relative_to(_REPO_ROOT)))
    return sorted(hits)


def _gate_attrs() -> set[str]:
    return {attr for attr, _name, _effect in _FEATURE_GATES}


def test_the_gate_exists_if_and_only_if_the_instrumentation_does() -> None:
    """The whole defect in one assertion, and it reads both ways.

    Today there are no call sites, so `posthog_api_key` must not be a gate. The day an
    SDK and a `capture()` land, this test flips and demands the gate back — which is why
    it is a coupling rather than a ban.
    """
    sites = _instrumentation_sites()
    gated = "posthog_api_key" in _gate_attrs()

    if sites:
        assert gated, (
            "PostHog is instrumented at "
            f"{sites} but is not in _FEATURE_GATES — a real feature that degrades "
            "silently belongs in the CR040 register. Add it back."
        )
    else:
        assert not gated, (
            "`posthog_api_key` is listed in _FEATURE_GATES but nothing in backend/app or "
            "mobile/lib ever sends an event. Setting the key would make /v1/admin/"
            "config-check report product analytics LIVE and drop dark_count by one, for "
            "a feature with no code — the register built to catch silently-dark features "
            "certifying a phantom (DEF246)."
        )


def test_setting_the_key_cannot_move_dark_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """The measurable consequence, asserted end to end over the wire.

    This is the assertion that fails against the pre-fix code: populating the key used to
    drop `dark_count` by exactly one. A promotion operator diffs that number against what
    `infra/alpha.env` intends, so a phantom moving it is a false all-clear on the one
    check whose job is catching false all-clears.
    """
    monkeypatch.setattr(settings, "admin_secret", "test-admin-secret")
    app = FastAPI()
    app.include_router(admin_router)
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Authorization": "Bearer test-admin-secret"}

    monkeypatch.setattr(settings, "posthog_api_key", "")
    before = client.get("/v1/admin/config-check", headers=headers)
    assert before.status_code == 200, before.text

    monkeypatch.setattr(settings, "posthog_api_key", "phc_not_a_real_key")
    after = client.get("/v1/admin/config-check", headers=headers)
    assert after.status_code == 200, after.text

    assert before.json()["dark_count"] == after.json()["dark_count"], (
        "setting POSTHOG_API_KEY changed dark_count, so the config gate reports a "
        "feature with zero call sites as newly live."
    )


def test_the_setting_is_still_visible_to_an_operator() -> None:
    """Dropping the gate must not hide the key.

    `settings_coverage` asks the narrower and truthful question — *is this setting
    populated* — and `annotated: False` is what says "no human prose claims this is a
    feature". Removing the row entirely would trade one wrong answer for no answer, and
    CR175 F3 exists because an invisible setting is how `adanos_api_key_secondary` sat
    idle undetected.
    """
    rows = {row.setting: row for row in _settings_coverage()}
    assert "POSTHOG_API_KEY" in rows, (
        "the setting vanished from settings_coverage — an operator can no longer see "
        "whether the key is set at all"
    )
    assert rows["POSTHOG_API_KEY"].annotated is False


def test_no_secret_value_is_echoed(monkeypatch: pytest.MonkeyPatch) -> None:
    """CR040's standing rule for this endpoint survives the change: booleans only."""
    monkeypatch.setattr(settings, "posthog_api_key", "phc_super_secret_value")
    rows = _settings_coverage()
    assert "phc_super_secret_value" not in repr(rows)
    assert {r.setting for r in rows} == {n.upper() for n in Settings.model_fields}
