"""Prototype pytest plugin: capture every JSON response any test's
`TestClient` receives during a real run of the backend unit suite, keyed by
(method, concrete path). Writes them to `captured_responses.jsonl` next to
this file at session end.

This is the "measure the real wire, don't trust the static schema" half of
the mechanism. It is loaded via `-p` from OUTSIDE `backend/tests/` — no
production or test file is modified. See SOLUTION.md for how this would be
wired for real (a fixture inside the suite itself, not an external `-p`
flag) versus this prototype's standalone form.

Usage:
  cd backend && ../backend/.venv/bin/python -m pytest tests/unit -q \
      -p docs.dilemmas...sonnet5.wire_capture_plugin   # (see run_capture.sh)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_OUT = Path(__file__).with_name("captured_responses.jsonl")
_records: list[dict] = []


def pytest_configure(config):
    # Patch at import time, before any test module builds its own
    # `TestClient(app)` — Starlette's TestClient funnels every verb method
    # (`.get`, `.post`, ...) through `httpx.Client.request`, so one patch
    # point catches all 92 files that use it, with zero changes to any of
    # them.
    from starlette.testclient import TestClient

    original_request = TestClient.request

    def _capturing_request(self, method, url, *args, **kwargs):
        response = original_request(self, method, url, *args, **kwargs)
        try:
            path = response.request.url.path
            ctype = response.headers.get("content-type", "")
            body = response.json() if "application/json" in ctype else None
        except Exception:
            body = None
            path = str(url)
        _records.append(
            {
                "method": method.upper(),
                "path": path,
                "status": response.status_code,
                "body": body,
            }
        )
        return response

    TestClient.request = _capturing_request
    config._wire_capture_original_request = original_request


def pytest_sessionfinish(session, exitstatus):
    with _OUT.open("w") as f:
        for r in _records:
            f.write(json.dumps(r) + "\n")
    print(f"\n[wire_capture] {len(_records)} responses captured -> {_OUT}")
