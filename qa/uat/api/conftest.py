"""Fixtures for the live-Alpha UAT API suite (CR263).

    backend/.venv/bin/python -m pytest qa/uat/api -q            # full run
    backend/.venv/bin/python -m pytest qa/uat/api -q --no-llm   # skip LLM-spending cases

`seed.user(plan=..., credits=...)` makes a fresh tagged user; all of them are
suspended at session end, and a teardown that fails to suspend one fails the
run loudly rather than leaving live accounts behind (CR040 — degrade loudly).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from client import Seeder, admin_secret, base_url, new_client

_RESULTS: dict[str, str] = {}


def pytest_addoption(parser):
    parser.addoption("--no-llm", action="store_true",
                     help="skip cases marked llm (Room streams, 1-on-1, Brief turns)")


def pytest_configure(config):
    config.addinivalue_line("markers", "uat(*ids): the UAT catalogue case(s) this test executes")
    config.addinivalue_line("markers", "llm: spends real LLM calls on Alpha")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--no-llm"):
        return
    skip = pytest.mark.skip(reason="--no-llm")
    for item in items:
        if item.get_closest_marker("llm"):
            item.add_marker(skip)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    marker = item.get_closest_marker("uat")
    if marker is None:
        return
    if rep.when == "call" or (rep.when == "setup" and rep.outcome != "passed"):
        result = "skipped" if rep.skipped else rep.outcome
        for case_id in marker.args:
            prior = _RESULTS.get(case_id)
            if prior != "failed":
                _RESULTS[case_id] = result


def pytest_sessionfinish(session, exitstatus):
    out = os.environ.get("UAT_RESULTS_JSON")
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps({"layer": "api", "base_url": base_url(),
                                         "results": _RESULTS}, indent=2, sort_keys=True))


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
