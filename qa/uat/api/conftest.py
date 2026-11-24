"""Fixtures for the live-Alpha UAT API suite (CR263).

    backend/.venv/bin/python -m pytest qa/uat/api -q            # full run
    backend/.venv/bin/python -m pytest qa/uat/api -q --no-llm   # skip LLM-spending cases

`seed.user(plan=..., credits=...)` makes a fresh tagged user; all of them are
suspended at session end, and a teardown that fails to suspend one fails the
run loudly rather than leaving live accounts behind (CR040 — degrade loudly).
"""

from __future__ import annotations

import os
import time

import pytest

from client import Seeder, admin_secret, new_client

pytest_plugins = ["uat_plugin"]


@pytest.fixture(scope="session")
def run_id() -> str:
    return os.environ.get("UAT_RUN_ID") or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


@pytest.fixture(scope="session")
def api():
    with new_client() as c:
        yield c


@pytest.fixture(scope="session")
def admin():
    secret = admin_secret()
    if not secret:
        pytest.exit("no ADMIN_SECRET (set UAT_ADMIN_SECRET or infra/alpha.env) — "
                    "the UAT suite cannot seed users, so it did not run", returncode=4)
    with new_client(secret) as c:
        yield c


@pytest.fixture(scope="session")
def seed(admin, run_id):
    s = Seeder(admin, run_id)
    yield s
    failures = s.close()
    if failures:
        pytest.fail("UAT teardown left live users unsuspended:\n" + "\n".join(failures))


@pytest.fixture(scope="session")
def bursa_on(api) -> bool:
    """CR282: is MARKET_BURSA_ENABLED on in the backend under test? Read once per
    session from the endpoint a client uses: with the switch on a well-formed
    Bursa code validates (`exists` true), with it off no `.KL` code does. The Bursa
    cases assert the matching behaviour for whichever state this reports, so a flag
    flip never turns them into false failures and never hides a regression behind
    a skip."""
    r = api.get("/v1/tickers/validate", params={"ticker": "1155.KL"})
    assert r.status_code == 200, f"cannot read the Bursa switch state: {r.status_code} {r.text}"
    body = r.json()
    assert body["ticker"] == "1155.KL", body
    return bool(body["exists"])
