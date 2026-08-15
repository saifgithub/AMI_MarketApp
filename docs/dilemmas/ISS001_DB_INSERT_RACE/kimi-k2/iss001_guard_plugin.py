"""ISS001 measurement plugin — observes unmanaged collidable inserts across the REAL suite.

Usage (writes nothing outside this folder):
    cd backend
    PYTHONPATH="docs/dilemmas/ISS001_DB_INSERT_RACE/kimi-k2:$PWD" \
      .venv/bin/python -m pytest tests/unit -q --tb=line -p iss001_guard_plugin -p no:cacheprovider

No repo file is modified. The plugin attaches the prototype's `before_flush`
rule to the global `Session` class in OBSERVE mode: instead of raising, it
records every unstamped collidable insert with the topmost `app/` frame that
caused it (or "tests/" when the insert originates in test code — the AST guard
scans only `app/services/`, so test-side inserts are invisible to it).

At session end it prints a histogram: (model, origin frame) -> flush count.
That is the suite-as-detector claim, measured: which of the 20 known sites the
suite actually exercises, and whether anything outside the inventory exists.

A first run in ENFORCE mode (raising variant) errored all 4,226 tests at the
first fixture: `tests/conftest.py:66` seeds `TickerReferenceRow` (natural PK)
with a bare `session.add` — the hook's very first sighting is a collidable
insert the source-scanning guard structurally cannot see.
"""

from __future__ import annotations

import collections
import os
import traceback

import pytest  # noqa: F401 — ensures we are inside pytest

os.environ.setdefault("AMI_TEST_DATABASE_URL", "sqlite:///:memory:")

_HITS: collections.Counter = collections.Counter()


def _derive_collidable(metadata):
    from sqlalchemy import Integer, UniqueConstraint

    out: dict[str, list[tuple[str, ...]]] = {}
    for table in metadata.tables.values():
        keys: set[tuple[str, ...]] = set()
        for c in table.constraints:
            if isinstance(c, UniqueConstraint):
                keys.add(tuple(sorted(col.name for col in c.columns)))
        for idx in table.indexes:
            if idx.unique:
                keys.add(tuple(sorted(col.name for col in idx.columns)))
        for col in table.columns:
            if col.unique:
                keys.add((col.name,))
        pk = list(table.primary_key.columns)
        if (
            pk
            and all(c.default is None and c.server_default is None for c in pk)
            and not (
                len(pk) == 1
                and isinstance(pk[0].type, Integer)
                and pk[0].autoincrement in (True, "auto")
            )
        ):
            keys.add(tuple(sorted(c.name for c in pk)))
        if keys:
            out[table.name] = sorted(keys)
    return out


def _origin_frame() -> str:
    """Topmost backend/app frame in the stack; else topmost tests/ frame."""
    app_frame = None
    test_frame = None
    for fr in traceback.extract_stack():
        f = fr.filename.replace("\\", "/")
        if "/backend/app/" in f:
            app_frame = f"app/{f.split('/backend/app/')[-1]}:{fr.lineno} {fr.name}"
        elif "/backend/tests/" in f:
            test_frame = f"tests/{f.split('/backend/tests/')[-1]}:{fr.lineno} {fr.name}"
    return app_frame or test_frame or "<external>"


def pytest_configure(config) -> None:
    from sqlalchemy import event
    from sqlalchemy.orm import Session

    from app.db.base import Base
    import app.db.models  # noqa: F401 — registers every mapper

    table_keys = _derive_collidable(Base.metadata)
    by_class = {}
    for m in Base.registry.mappers:
        name = m.persist_selectable.name
        if name in table_keys:
            by_class[m.class_] = table_keys[name]

    print(f"\n[iss001] observer armed over {len(by_class)} collidable models (measurement run)")

    @event.listens_for(Session, "before_flush")
    def _observe(session, flush_context, instances) -> None:
        seen_this_flush = set()
        for obj in session.new:
            keys = by_class.get(type(obj))
            if keys is None:
                continue
            origin = _origin_frame()
            marker = (type(obj).__name__, origin)
            if marker not in seen_this_flush:  # one entry per (model, origin) per flush
                seen_this_flush.add(marker)
                _HITS[marker] += 1


def pytest_sessionfinish(session, exitstatus) -> None:
    print("\n[iss001] unmanaged collidable inserts observed (model, origin) -> flushes:")
    for (model, origin), n in sorted(_HITS.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        print(f"  {n:5d}  {model:32s} {origin}")
    print(f"[iss001] distinct (model, origin) sites: {len(_HITS)}")
