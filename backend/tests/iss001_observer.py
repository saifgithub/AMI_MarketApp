"""ISS001 — opt-in pytest plugin: the INSERT-tripwire report and the check-then-insert observer.

Not part of the default suite (it adds a per-session read log). Enable it with:

    cd backend
    ISS001_OUT=/path/report.json PYTHONPATH=. .venv/bin/python -m pytest tests/unit -q \
        -p tests.iss001_observer

It sets `INSERT_TRIPWIRE_MODE=log` (so nothing fails) unless the caller already chose one, and
registers a violation sink that records EVERY site the tripwire saw, baselined or not — which is
the retrofit checklist. At session end it writes JSON with:

  * `schema_truth`    composite unique keys that do not deduplicate NULL rows
  * `tripwire`        {table: {site: {"count": n, "baselined": bool, "reason": str}}}
  * `attach_sites`    {table: {site: n}} where each collidable row entered a session (constructor-side
                      attribution; the tripwire names the frame that flushed)
  * `observer`        one verdict per (table, site): reads followed by an INSERT of the same key,
                      statuses aggregated by WORST severity so the verdict does not depend on the
                      order two branches were reached (opus5.0's lesson)

Gate: with `ISS001_GATE=1` the session fails when the observer saw a `VACUOUS` key (a read-then-
insert whose only unique key cannot fire for these values — DEF499). `NO-ARBITER` and
`PARTIAL-KEY` stay report-only: measured precision about 2 of 6, and noise, respectively.
"""

from __future__ import annotations

import collections
import json
import os
from typing import Any, Callable

os.environ.setdefault("INSERT_TRIPWIRE_MODE", "log")

from sqlalchemy import event, inspect  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.sql import operators  # noqa: E402
from sqlalchemy.sql.elements import BinaryExpression, BindParameter, BooleanClauseList, Null  # noqa: E402

from app.db.ami_claim import (  # noqa: E402
    Arbiter,
    add_violation_sink,
    app_frames,
    arbiters,
    collidable_tables,
    normalize_sql,
    schema_truth,
)

SEVERITY = {"covered": 0, "PARTIAL-KEY": 1, "NO-ARBITER": 2, "VACUOUS": 3}


def worst(statuses) -> str:
    return max(statuses, key=lambda s: SEVERITY[s])


def aggregate(observations: list[dict]) -> list[dict]:
    """One row per (table, site); status = worst across every branch that reached it, so the
    result is the same whichever order the branches ran in."""
    by_site: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for o in observations:
        by_site[(o["table"], o["site"])].append(o)
    out = []
    for (table, site), obs in sorted(by_site.items()):
        out.append({
            "table": table,
            "site": site,
            "status": worst(o["status"] for o in obs),
            "cols": sorted({c for o in obs for c in o["cols"]}),
            "hits": sum(o.get("hits", 1) for o in obs),
        })
    return out


def _eq_preds(clause) -> dict[tuple[str, str], Any]:
    out: dict[tuple[str, str], Any] = {}
    if clause is None:
        return out
    if isinstance(clause, BooleanClauseList) and clause.operator is operators.and_:
        for c in clause.clauses:
            out.update(_eq_preds(c))
    elif isinstance(clause, BinaryExpression) and clause.operator in (operators.eq, operators.is_):
        left, right = clause.left, clause.right
        tbl = getattr(left, "table", None)
        if tbl is not None and hasattr(left, "name"):
            if isinstance(right, BindParameter):
                out[(tbl.name, left.name)] = right.value
            elif isinstance(right, Null):
                out[(tbl.name, left.name)] = None
    return out


def _real_arbiters(table) -> list[Arbiter]:
    return [a for a in arbiters(table)
            if not (a.name == "PRIMARY" and all(table.c[c].default is not None or table.c[c].server_default is not None
                                                  for c in a.columns))]


def classify(table, cols: dict[str, Any]) -> tuple[str, Arbiter | None]:
    """How well does a unique key back a read-by-`cols`?  covered | VACUOUS | PARTIAL-KEY | NO-ARBITER."""
    real = _real_arbiters(table)
    vacuous = False
    for a in real:
        if not set(a.columns) <= set(cols):
            continue
        extra = [c for c in cols if c not in a.columns]
        if a.where:
            w = normalize_sql(a.where)
            if all(cols[c] is None and f"{c.upper()} IS NULL" in w for c in extra):
                return "covered", a
        elif all(cols[c] is not None for c in a.columns if table.c[c].nullable):
            return "covered", a
        else:
            vacuous = True
    if vacuous:
        return "VACUOUS", None
    return ("PARTIAL-KEY" if real else "NO-ARBITER"), None


def install_observer(sink: Callable[[dict], None]) -> Callable[[], None]:
    """Report every (table, columns) a session SELECTed by equality and then INSERTed with the
    same values — the shape P15 describes — however many helpers the read hides in."""

    reads_key, sites_key = ("_obs_reads", id(sink)), ("_obs_sites", id(sink))

    def on_exec(state):
        if not state.is_select:
            return
        try:
            preds = _eq_preds(state.statement.whereclause)
        except Exception:
            return
        by_table: dict[str, dict[str, Any]] = {}
        for (t, c), v in preds.items():
            by_table.setdefault(t, {})[c] = v
        log = state.session.info.setdefault(reads_key, [])
        for t, cols in by_table.items():
            log.append((t, cols))

    def on_attach(session, instance):
        frames = app_frames(1, skip=2)
        site = f"{frames[-1][0]}::{frames[-1][2]}" if frames else "<non-app>"
        session.info.setdefault(sites_key, {})[id(instance)] = site

    def on_flush(session, ctx, instances):
        reads = session.info.get(reads_key, [])
        if not reads:
            return
        for obj in list(session.new):
            mapper = inspect(obj).mapper
            table = mapper.local_table
            for t, cols in reads:
                if t != table.name or not cols:
                    continue
                vals = {}
                ok = True
                for c in cols:
                    prop = mapper.get_property_by_column(table.c[c]) if c in table.c else None
                    if prop is None:
                        ok = False
                        break
                    v = getattr(obj, prop.key, None)
                    dflt = table.c[c].default
                    if v is None and dflt is not None and dflt.is_scalar:
                        v = dflt.arg
                    vals[c] = v
                if not ok or any(vals[c] != cols[c] for c in cols):
                    continue
                status, effective = classify(table, cols)
                sink({
                    "table": table.name,
                    "cols": sorted(cols),
                    "status": status,
                    "arbiter": effective.name if effective else None,
                    "site": session.info.get(sites_key, {}).get(id(obj), "<non-app>"),
                })

    event.listen(Session, "do_orm_execute", on_exec)
    event.listen(Session, "after_attach", on_attach)
    event.listen(Session, "before_flush", on_flush)

    def uninstall():
        event.remove(Session, "do_orm_execute", on_exec)
        event.remove(Session, "after_attach", on_attach)
        event.remove(Session, "before_flush", on_flush)

    return uninstall


_trip: dict[tuple[str, str], dict] = {}
_attach: collections.Counter = collections.Counter()
_obs: collections.Counter = collections.Counter()
_undo: list = []
_CANARY_SITES = ("services/_iss001_canary",)  # synthetic frames the ISS001 tests compile on purpose


def _install_attach_recorder(collidable: set[str]) -> Callable[[], None]:
    """Record WHERE each row of a collidable table entered a session (`session.add`, relationship
    append). The tripwire can only name the frame that FLUSHED, which for a row built in one
    helper and flushed in its caller is the caller; the attach site is the constructor-side
    answer (e.g. `sim_engine._apply_buy_row`, whose check is an in-memory scan of
    `p_row.holdings` and so never shows up as a SELECT)."""

    def on_attach(session, instance):
        table = getattr(getattr(type(instance), "__table__", None), "name", None)
        if table in collidable:
            frames = app_frames(1, skip=2)
            if frames and not frames[-1][0].startswith(_CANARY_SITES):
                _attach[(table, f"{frames[-1][0]}::{frames[-1][2]}")] += 1

    event.listen(Session, "after_attach", on_attach)
    return lambda: event.remove(Session, "after_attach", on_attach)


def pytest_configure(config):
    from app.db import models  # noqa: F401
    from app.db.base import Base

    tables = Base.metadata.tables

    def on_violation(v, baselined):
        if v.table not in tables or v.site.startswith(_CANARY_SITES):
            return  # a synthetic model or canary from the ISS001 tests, not application code
        e = _trip.setdefault((v.table, v.site), {"count": 0, "baselined": baselined, "reason": v.reason})
        e["count"] += 1

    def sink(o):
        if o["table"] not in tables:
            return
        _obs[(o["table"], tuple(o["cols"]), o["status"], o["site"])] += 1

    _undo.append(add_violation_sink(on_violation))
    _undo.append(install_observer(sink))
    _undo.append(_install_attach_recorder(collidable_tables(Base.metadata)))
    config._iss001_metadata = Base.metadata


def pytest_sessionfinish(session, exitstatus):
    observations = [
        {"table": t, "cols": list(c), "status": s, "site": site, "hits": n}
        for (t, c, s, site), n in sorted(_obs.items())
    ]
    aggregated = aggregate(observations)
    if os.environ.get("ISS001_GATE") == "1" and any(o["status"] == "VACUOUS" for o in aggregated):
        session.exitstatus = 1
    out = os.environ.get("ISS001_OUT")
    if not out:
        return
    md = session.config._iss001_metadata
    tripwire: dict[str, dict] = {}
    for (table, site), e in sorted(_trip.items()):
        tripwire.setdefault(table, {})[site] = e
    with open(out, "w") as fh:
        json.dump({
            "collidable_tables": sorted(collidable_tables(md)),
            "schema_truth": schema_truth(md),
            "tripwire": tripwire,
            "attach_sites": {
                t: {site: n for (tt, site), n in sorted(_attach.items()) if tt == t}
                for t in sorted({t for t, _ in _attach})
            },
            "observer": aggregated,
        }, fh, indent=1)
