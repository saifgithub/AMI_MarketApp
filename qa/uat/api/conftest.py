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
