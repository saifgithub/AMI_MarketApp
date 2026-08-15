"""ISS001 / opus5.0 — a runtime observer for check-then-INSERT on collidable models.

Load as a pytest plugin. It does not modify a single line of application code or of the real
suite; it attaches one SQLAlchemy `before_flush` listener and watches what actually happens.

    cd backend
    PYTHONPATH=<this dir> .venv/bin/python -m pytest tests/unit/ -q -p insert_race_observer

Two modes, chosen by env var:

    ISS001_MODE=observe   (default) record every collidable INSERT, fail nothing
    ISS001_MODE=enforce             raise on an unprotected one

Why this exists in observe mode first: the honest unknown in any "fail the build" proposal is how
many LEGITIMATE inserts it would flag. Guessing that number is how a control becomes a nuisance
that everyone learns to work around. So measure it before proposing to enforce it.

Output: `iss001_observations.json` in the working directory.
"""

from __future__ import annotations

import json
import os
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

MODE = os.environ.get("ISS001_MODE", "observe")
OUT = Path(os.environ.get("ISS001_OUT", "iss001_observations.json")).resolve()

# model name -> list of colliding constraint descriptions
_COLLIDABLE: dict[str, list[str]] = {}
_RECORDS: dict[str, dict[str, Any]] = {}
_COUNTS: defaultdict[str, int] = defaultdict(int)
_READS: defaultdict[int, set[str]] = defaultdict(set)   # session id -> models SELECTed
_ADDED_AT: dict[int, str] = {}                          # object id -> frame that called add()


class InsertRaceViolation(RuntimeError):
    """An INSERT on a model that can collide, with no protection in scope."""


def _collidable_columns(table) -> list[str]:
    """Constraints that make a duplicate INSERT raise, read from LIVE metadata.

    Note this needs no source parsing at all. The existing detector re-derives this by walking
    the AST of `models.py`; the mapper already knows it, exactly and for every model, including
    any added by a migration or a mixin the AST would not have seen.
    """
    out: list[str] = []
    for col in table.columns:
        if col.unique:
            out.append(f"unique:{col.name}")
        # A primary key with no default is a NATURAL key — it collides like any
        # other unique. A uuid4-defaulted PK cannot, and must not be counted, or
        # every append-only insert in the codebase is flagged.
        if col.primary_key and col.default is None and col.server_default is None:
            out.append(f"natural-pk:{col.name}")
    for con in table.constraints:
        if con.__class__.__name__ == "UniqueConstraint":
            out.append("uq:" + ",".join(c.name for c in con.columns))
    for idx in table.indexes:
        if idx.unique:
            out.append("uqidx:" + ",".join(c.name for c in idx.columns))
    return out


def _build_collidable_map() -> None:
    from app.db.models import Base

    for mapper in Base.registry.mappers:
        cols = _collidable_columns(mapper.local_table)
        if cols:
            _COLLIDABLE[mapper.class_.__name__] = cols


def _app_frame() -> str:
    """The application line responsible, skipping SQLAlchemy and this file."""
    for frame in reversed(traceback.extract_stack()[:-1]):
        p = frame.filename
        if "/app/" in p and "sqlalchemy" not in p and "site-packages" not in p:
            if p.endswith("/app/db/session.py"):
                continue  # the session context manager, never the culprit
            idx = p.find("/app/")
            return f"{p[idx + 1:]}:{frame.lineno} in {frame.name}"
    return "unknown"


def _protected(session: Session) -> bool:
    """Is this INSERT covered by something that survives a constraint violation?

    A SAVEPOINT is the only in-scope protection we can see from here. An `except IntegrityError`
    in the CALLER's frame is real protection this cannot detect — which is a stated limitation,
    not an oversight, and is why observe mode reports rather than judges.
    """
    return session.in_nested_transaction()


# ── 1. what did this session READ? ───────────────────────────────────────────


@event.listens_for(Session, "do_orm_execute")
def _watch_reads(state) -> None:
    if not state.is_select:
        return
    try:
        for mapper in state.all_mappers:
            _READS[id(state.session)].add(mapper.class_.__name__)
    except Exception:  # pragma: no cover - never break a real query
        pass


# ── 2. WHERE was add() called? ───────────────────────────────────────────────
#
# Captured here, not at flush time. `before_flush` fires when the session COMMITS, by which
# point the frame that called add() has returned — v1 attributed 15 sites to the session
# context manager's own __exit__, which names the wrong code.


@event.listens_for(Session, "transient_to_pending")
def _watch_add(session, instance) -> None:  # noqa: ARG001
    if type(instance).__name__ in _COLLIDABLE:
        _ADDED_AT[id(instance)] = _app_frame()


# ── 3. is this a check-then-INSERT, and is it protected? ─────────────────────


@event.listens_for(Session, "before_flush")
def _watch_flush(session: Session, flush_context, instances) -> None:  # noqa: ARG001
    if not _COLLIDABLE:
        return
    read_here = _READS.get(id(session), set())
    for obj in session.new:
        name = type(obj).__name__
        constraints = _COLLIDABLE.get(name)
        if constraints is None:
            continue
        checked_first = name in read_here
        where = _ADDED_AT.get(id(obj), _app_frame())
        key = f"{name}@{where}"
        _COUNTS[key] += 1
        risky = checked_first and not _protected(session)
        # Aggregate across executions, never first-write-wins. Found the hard way:
        # `ensure_anonymous` SELECTs only when a device id is supplied and otherwise inserts a
        # fresh uuid4 that cannot collide. First-write-wins filed 528 executions under the safe
        # branch and the site vanished from the report. A detector whose verdict depends on test
        # ORDER is worse than one that is merely incomplete.
        rec = _RECORDS.get(key)
        if rec is None:
            _RECORDS[key] = {
                "model": name, "site": where, "constraints": constraints,
                "check_then_insert": checked_first,
                "protected_by_savepoint": _protected(session),
                "risky_executions": 1 if risky else 0,
            }
        else:
            rec["check_then_insert"] = rec["check_then_insert"] or checked_first
            rec["protected_by_savepoint"] = (
                rec["protected_by_savepoint"] and _protected(session)
            )
            rec["risky_executions"] += 1 if risky else 0
        if MODE == "enforce" and risky:
            raise InsertRaceViolation(
                f"{name} at {where}: this session SELECTed {name} and is now INSERTing it "
                f"with nothing to catch a violation of {constraints} (ISS001)."
            )


@event.listens_for(Session, "after_soft_rollback")
def _forget(session, previous_transaction) -> None:  # noqa: ARG001
    _READS.pop(id(session), None)


# ── pytest plugin hooks ──────────────────────────────────────────────────────


def pytest_configure(config):  # noqa: ARG001
    try:
        _build_collidable_map()
    except Exception as exc:  # pragma: no cover
        print(f"[ISS001] could not build collidable map: {exc}")


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    for key, rec in _RECORDS.items():
        rec["times_executed"] = _COUNTS[key]
    obs = sorted(_RECORDS.values(), key=lambda r: (-r["times_executed"], r["site"]))
    flagged = [r for r in obs if r["check_then_insert"] and not r["protected_by_savepoint"]]
    payload = {
        "mode": MODE,
        "collidable_models": len(_COLLIDABLE),
        "distinct_sites_executed": len(obs),
        "append_only_sites_silent": sum(1 for r in obs if not r["check_then_insert"]),
        "check_then_insert_sites": sum(1 for r in obs if r["check_then_insert"]),
        "flagged": len(flagged),
        "observations": obs,
    }
    OUT.write_text(json.dumps(payload, indent=2))
    print(
        f"\n[ISS001] {payload['collidable_models']} collidable models \u00b7 "
        f"{payload['distinct_sites_executed']} sites executed \u00b7 "
        f"{payload['append_only_sites_silent']} append-only (silent) \u00b7 "
        f"{payload['flagged']} FLAGGED \u2192 {OUT}"
    )
