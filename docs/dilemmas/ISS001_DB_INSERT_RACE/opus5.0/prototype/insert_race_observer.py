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

from sqlalchemy import event, inspect as sa_inspect
from sqlalchemy.orm import Session

MODE = os.environ.get("ISS001_MODE", "observe")
OUT = Path(os.environ.get("ISS001_OUT", "iss001_observations.json")).resolve()

# model name -> list of colliding constraint descriptions
_COLLIDABLE: dict[str, list[str]] = {}
_RECORDS: dict[str, dict[str, Any]] = {}
_COUNTS: defaultdict[str, int] = defaultdict(int)


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


@event.listens_for(Session, "before_flush")
def _watch(session: Session, flush_context, instances) -> None:  # noqa: ARG001
    if not _COLLIDABLE:
        return
    for obj in session.new:
        name = type(obj).__name__
        constraints = _COLLIDABLE.get(name)
        if constraints is None:
            continue
        where = _app_frame()
        key = f"{name}@{where}"
        _COUNTS[key] += 1
        if key not in _RECORDS:
            _RECORDS[key] = {
                "model": name,
                "site": where,
                "constraints": constraints,
                "protected_by_savepoint": _protected(session),
            }
        if MODE == "enforce" and not _protected(session):
            raise InsertRaceViolation(
                f"{name} inserted at {where} can violate {constraints} and is not inside a "
                "SAVEPOINT. Declare the collision outcome (ISS001)."
            )


# ── pytest plugin hooks ──────────────────────────────────────────────────────


def pytest_configure(config):  # noqa: ARG001
    try:
        _build_collidable_map()
    except Exception as exc:  # pragma: no cover
        print(f"[ISS001] could not build collidable map: {exc}")


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    for key, rec in _RECORDS.items():
        rec["times_executed"] = _COUNTS[key]
    payload = {
        "mode": MODE,
        "collidable_models": len(_COLLIDABLE),
        "distinct_sites_executed": len(_RECORDS),
        "unprotected_sites": sum(
            1 for r in _RECORDS.values() if not r["protected_by_savepoint"]
        ),
        "observations": sorted(_RECORDS.values(), key=lambda r: (-r["times_executed"], r["site"])),
    }
    OUT.write_text(json.dumps(payload, indent=2))
    print(
        f"\n[ISS001] {payload['collidable_models']} collidable models · "
        f"{payload['distinct_sites_executed']} sites executed · "
        f"{payload['unprotected_sites']} unprotected → {OUT}"
    )
