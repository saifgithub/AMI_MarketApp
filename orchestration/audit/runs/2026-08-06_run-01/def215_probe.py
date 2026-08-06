"""DEF215 r1 audit — turn §6.2's "I believe this is harmless" into a reading.

Two threads enter init_schema() on a FRESH db and both pass the identity
check. Both then create_all (benign, checkfirst=True) AND both stamp. The
question the submission does not answer: can that leave alembic_version with
TWO rows? If it can, `get_current_revision()` raises on multiple heads and
`alembic upgrade head` has no single revision to walk from — which would make
the concurrency window a schema-integrity bug, not a benign double-log.
"""
from __future__ import annotations

import tempfile
import threading
from pathlib import Path

from sqlalchemy import inspect, text

from app.db import session as db_session
from app.db.session import get_engine, init_schema, reset_for_tests


def _rows() -> list[str]:
    with get_engine().connect() as conn:
        return [r[0] for r in conn.execute(text("SELECT version_num FROM alembic_version"))]


def test_two_threads_on_a_fresh_db(capsys) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        reset_for_tests(f"sqlite:///{Path(tmp) / 'race.db'}")
        try:
            # Fresh: strip everything the fixture's own init built.
            with get_engine().begin() as conn:
                for t in inspect(get_engine()).get_table_names():
                    conn.execute(text(f"DROP TABLE {t}"))
            db_session._schema_checked_for = None
            assert inspect(get_engine()).get_table_names() == []

            barrier = threading.Barrier(2)
            errors: list[BaseException] = []

            def go() -> None:
                try:
                    barrier.wait(timeout=10)
                    init_schema()
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)

            ts = [threading.Thread(target=go) for _ in range(2)]
            for t in ts:
                t.start()
            for t in ts:
                t.join(timeout=30)

            names = inspect(get_engine()).get_table_names()
            versions = _rows()
            print(f"\nthread exceptions      : {[type(e).__name__ for e in errors]}")
            print(f"alembic_version rows   : {versions}")
            print(f"row count              : {len(versions)}  (>1 == corrupt)")
            print(f"tables built           : {len(names)}")

            # Does alembic itself still read a single revision back?
            from alembic.runtime.migration import MigrationContext
            with get_engine().connect() as conn:
                try:
                    cur = MigrationContext.configure(conn).get_current_revision()
                    print(f"get_current_revision() : {cur}")
                except Exception as exc:  # noqa: BLE001
                    print(f"get_current_revision() : RAISED {type(exc).__name__}: {exc}")

            assert len(versions) <= 1, f"alembic_version has {len(versions)} rows"
        finally:
            reset_for_tests()


def test_repeated_init_does_not_repair_a_dropped_table(capsys) -> None:
    """§6.1's contract change, stated as a reading rather than a grep.

    init_schema() used to be restorative. It is now once-per-engine. This is
    the behaviour any caller relying on the old contract would now get.
    """
    with tempfile.TemporaryDirectory() as tmp:
        reset_for_tests(f"sqlite:///{Path(tmp) / 'contract.db'}")
        try:
            assert "price_history_daily" in inspect(get_engine()).get_table_names()
            with get_engine().begin() as conn:
                conn.execute(text("DROP TABLE price_history_daily"))

            init_schema()  # the old contract says this restores it
            back = "price_history_daily" in inspect(get_engine()).get_table_names()
            print(f"\nafter DROP + init_schema(): table restored? {back}")
            print("  (False = once-per-engine; Alembic owns repair now)")
        finally:
            reset_for_tests()
