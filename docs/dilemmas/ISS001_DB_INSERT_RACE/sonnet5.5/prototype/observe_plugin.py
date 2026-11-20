"""ISS001 prototype — dry-run the tripwire + observer over the REAL backend suite.

Changes nothing in the repo. Loaded as a pytest plugin:

    cd backend
    PYTHONPATH=../docs/dilemmas/ISS001_DB_INSERT_RACE/sonnet5.5/prototype \
    ISS001_OUT=/path/out.json \
    .venv/bin/python -m pytest tests/unit -q -p observe_plugin

At session end writes a JSON summary:
  * `schema_truth`   unique keys that do not deduplicate NULL rows (exact, from live metadata)
  * `tripwire`       {table: {site: count}}  every INSERT into a collidable table, from app code
                     or from test fixtures ("<test-only>"), that nobody declared a behaviour for
  * `observer`       distinct (table, cols, status, site) read-then-insert observations
Tripwire is in LOG mode: nothing fails. The point is to measure what the retrofit would touch and
what the observer sees that the AST guard (P15) cannot.
"""

from __future__ import annotations

import collections
import json
import os

import ami_claim as ac

_trip: dict = collections.defaultdict(lambda: collections.Counter())
_obs: dict = collections.Counter()
_uninstall: list = []


def pytest_configure(config):
    from app.db import models  # noqa: F401
    from app.db.base import Base

    def on_violation(table, stmt, stack):
        _trip[table][stack[-1] if stack else "<test-only>"] += 1

    def sink(o):
        _obs[(o["table"], tuple(o["cols"]), o["status"], o["arbiter"], o["site"])] += 1

    _uninstall.append(ac.install_tripwire(Base.metadata, mode="log", on_violation=on_violation))
    _uninstall.append(ac.install_observer(sink))
    config._iss001_metadata = Base.metadata


def pytest_sessionfinish(session, exitstatus):
    out = os.environ.get("ISSOO1_OUT") or os.environ.get("ISS001_OUT")
    if not out:
        return
    md = session.config._iss001_metadata
    data = {
        "collidable_tables": sorted(ac.collidable_tables(md)),
        "schema_truth": ac.schema_truth(md),
        "tripwire": {t: dict(c) for t, c in sorted(_trip.items())},
        "observer": [
            {"table": t, "cols": list(c), "status": s, "arbiter": a, "site": site, "hits": n}
            for (t, c, s, a, site), n in sorted(_obs.items())
        ],
    }
    with open(out, "w") as fh:
        json.dump(data, fh, indent=1)
