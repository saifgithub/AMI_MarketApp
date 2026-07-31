"""DEF195 — coverage for `scripts/check_release_schema_parity.py`, the
client-vs-deployed-backend schema parity gate. Added round 2 of the R65-BATCH1
audit, closing MAJOR M1: the gate shipped with **no tests and no caller**, which
the auditor graded (and the architect pre-graded) as a shipped no-op of the
DEF038/DEF063 "dark for months" class.

TWO DIFFERENT CHECKS LIVE HERE, and conflating them would be the whole point
missed:

  1. **Does the gate's logic work?** (`test_gate_*`) — driven off fixture
     OpenAPI docs, asserting it PASSES on parity and FAILS on a missing key.
     This is the smoke test the audit asked for by name.

  2. **Is the client in parity with THIS checkout's backend right now?**
     (`test_client_patch_keys_all_exist_in_this_checkouts_schema`) — a real
     caller, running on every suite run, so the gate is no longer something
     that never executes.

**(2) does NOT replace the release gate and must not be read as doing so.** It
compares the client against the schema *in this repo*; DEF195 exists because a
client can be in parity with `main` and still ahead of what is **deployed** on
Alpha — that was the `0.1.0+61` near-miss exactly. Only
`check_release_schema_parity.py --base-url <live host>`, run at release time
against the actually-promoted backend, closes that. Wiring THAT into
`scripts/build_*.sh` is still owed (see the DEF195 row) and is blocked on the
CR084-ALPHA edits to those scripts landing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GATE = _REPO_ROOT / "scripts" / "check_release_schema_parity.py"

sys.path.insert(0, str(_REPO_ROOT / "scripts"))
from check_release_schema_parity import (  # noqa: E402
    backend_keys,
    client_patch_keys,
)


def _spec(mandate_props: set[str], compliance_props: set[str], version: str = "9.9.9") -> dict:
    return {
        "info": {"version": version},
        "components": {
            "schemas": {
                "Mandate": {"properties": {k: {} for k in mandate_props}},
                "Compliance": {"properties": {k: {} for k in compliance_props}},
            }
        },
    }


def _run_gate(spec: dict, tmp_path: Path) -> subprocess.CompletedProcess:
    f = tmp_path / "openapi.json"
    f.write_text(json.dumps(spec), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(_GATE), "--openapi-file", str(f)],
        capture_output=True, text=True, cwd=str(_REPO_ROOT),
    )


# ── 1. the gate's own logic ────────────────────────────────────────────────


def test_gate_passes_when_the_backend_serves_every_client_key(tmp_path):
    top, compliance = client_patch_keys()
    r = _run_gate(_spec(top, compliance), tmp_path)
    assert r.returncode == 0, f"gate failed on a parity spec:\n{r.stdout}\n{r.stderr}"


def test_gate_fails_when_the_backend_is_missing_one_client_key(tmp_path):
    """The `0.1.0+61` shape: the client PATCHes a key the deployed backend
    has never heard of, the PATCH 200s, and pydantic's extra='ignore' drops
    it — a control that looks authoritative and writes nothing."""
    top, compliance = client_patch_keys()
    victim = sorted(top)[0]
    r = _run_gate(_spec(top - {victim}, compliance), tmp_path)
    assert r.returncode == 1, (
        f"gate PASSED while the backend was missing {victim!r} — it would have "
        f"cleared the exact deployment-order bug DEF195 exists to catch"
    )
    assert victim in (r.stdout + r.stderr)


def test_gate_fails_when_a_nested_compliance_key_is_missing(tmp_path):
    top, compliance = client_patch_keys()
    victim = sorted(compliance)[0]
    r = _run_gate(_spec(top, compliance - {victim}), tmp_path)
    assert r.returncode == 1, f"gate missed a dropped compliance key {victim!r}"


def test_gate_fails_closed_when_the_spec_has_no_mandate_schema(tmp_path):
    """CR040: 'could not perform the check' must exit 1, never 0. A gate that
    passes when it could not verify reports safety it never checked."""
    r = _run_gate({"info": {"version": "9.9.9"}, "components": {"schemas": {}}}, tmp_path)
    assert r.returncode == 1


def test_gate_fails_closed_on_an_unreachable_host():
    r = subprocess.run(
        [sys.executable, str(_GATE), "--base-url", "http://127.0.0.1:9"],
        capture_output=True, text=True, cwd=str(_REPO_ROOT),
    )
    assert r.returncode == 1, "an unreachable backend must fail the gate, not skip it"


# ── 2. a real caller, so the gate actually runs ────────────────────────────


def test_client_patch_keys_scrape_is_not_vacuous():
    """The scrape is regex-over-Dart-source. If a rename empties it, every
    parity check silently passes. The gate has its own vacuity leg; this
    pins it from the test side too."""
    top, compliance = client_patch_keys()
    assert len(top) >= 5, f"suspiciously few client PATCH keys scraped: {sorted(top)}"
    assert compliance, "zero compliance keys scraped — the scrape is broken, not the app"


def test_client_patch_keys_all_exist_in_this_checkouts_schema():
    """Commit-time parity: every key the client can PATCH exists in the
    Mandate/Compliance schema THIS checkout would serve.

    Weaker than the release gate (which asks the DEPLOYED backend) but it runs
    on every suite run, and it catches the case where a client key matches no
    backend field anywhere in the codebase.
    """
    from fastapi.openapi.utils import get_openapi

    from app.main import app

    spec = get_openapi(title=app.title, version=app.version, routes=app.routes)
    top, compliance = client_patch_keys()
    be_top, be_compliance, _ = backend_keys(spec)

    missing_top = sorted(top - be_top)
    missing_compliance = sorted(compliance - be_compliance)
    assert not missing_top and not missing_compliance, (
        "the client can PATCH Mandate keys this checkout's backend does not "
        f"define — top-level {missing_top}, compliance {missing_compliance}. "
        "Either the backend field was removed/renamed, or the client shipped "
        "ahead of it (DEF195)."
    )


def test_the_gate_script_is_executable_and_self_documents():
    assert _GATE.is_file()
    r = subprocess.run(
        [sys.executable, str(_GATE), "--help"],
        capture_output=True, text=True, cwd=str(_REPO_ROOT),
    )
    assert r.returncode == 0
    assert "--openapi-file" in r.stdout
