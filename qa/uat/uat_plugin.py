"""Pytest plugin shared by every UAT executor (CR263): the API suite and the
Appium harness both load it, so both record results the same way.

1. Registers the `uat(*ids)` and `llm` markers.
2. `--uat-ids a,b` / `--uat-ids @file` runs only tests citing those cases.
3. `--no-llm` skips tests marked `llm`.
4. After every test (and at session end), writes `{layer, platform,
   exitstatus, results: {case_id: outcome}}` to `$UAT_RESULTS_JSON` for
   `ledger.py record` — so a killed run keeps what it finished. `$UAT_LAYER` (api|device) and
   `$UAT_PLATFORM` (api|ios|android) label the run.

A case cited by several tests takes its worst outcome — it passes only if
every test behind it passed. Skipped is recorded as such and never counts as
evidence.

Load it with `-p uat_plugin` (qa/uat on the path) or `pytest_plugins`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

_RESULTS: dict[str, str] = {}
_RANK = {"passed": 0, "xfailed": 1, "skipped": 2, "failed": 3}


def pytest_addoption(parser):
    group = parser.getgroup("uat")
    group.addoption("--no-llm", action="store_true",
                    help="skip cases marked llm (Room streams, 1-on-1, Brief turns)")
    group.addoption("--uat-ids", default="",
                    help="comma-separated UAT ids (or @file of ids) — run only tests citing them")


def pytest_configure(config):
    config.addinivalue_line("markers", "uat(*ids): the UAT catalogue case(s) this test executes")
    config.addinivalue_line("markers", "llm: spends real LLM calls on Alpha")


def _wanted_ids(raw: str) -> set[str]:
    if raw.startswith("@"):
        raw = Path(raw[1:]).read_text().replace("\n", ",")
    return {i.strip() for i in raw.split(",") if i.strip()}


def pytest_collection_modifyitems(config, items):
    wanted = _wanted_ids(config.getoption("--uat-ids"))
    if wanted:
        keep, drop = [], []
        for item in items:
            m = item.get_closest_marker("uat")
            (keep if m and wanted & set(m.args) else drop).append(item)
        config.hook.pytest_deselected(items=drop)
        items[:] = keep
    if config.getoption("--no-llm"):
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
    if rep.when == "call" or (rep.when != "call" and rep.outcome == "failed") or (
        rep.when == "setup" and rep.skipped
    ):
        if hasattr(rep, "wasxfail"):
            result = "xfailed" if rep.skipped else "failed"
        else:
            result = "skipped" if rep.skipped else rep.outcome
        for case_id in marker.args:
            prior = _RESULTS.get(case_id, "passed")
            _RESULTS[case_id] = max(prior, result, key=_RANK.__getitem__)
        _write(None)


def _write(exitstatus: int | None) -> None:
    """Written after every test, not only at session end: a run killed an hour
    in (SIGTERM, measured 2026-10-19) must keep the evidence it gathered.
    `exitstatus` stays null until the session actually finishes."""
    out = os.environ.get("UAT_RESULTS_JSON")
    if not out:
        return
    layer = os.environ.get("UAT_LAYER", "api")
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({
        "layer": layer,
        "platform": os.environ.get("UAT_PLATFORM", "api" if layer == "api" else ""),
        "exitstatus": exitstatus,
        "results": _RESULTS,
    }, indent=2, sort_keys=True))
    tmp.replace(path)


def pytest_sessionfinish(session, exitstatus):
    _write(int(exitstatus))
