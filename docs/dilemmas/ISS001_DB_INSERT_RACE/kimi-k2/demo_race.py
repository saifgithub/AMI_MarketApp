"""ISS001 demo — the race is real, shown with nothing but stdlib sqlite3.

Two threads, one tempfile database, a barrier between the read and the write
so both pre-checks land before either INSERT — P15's read-to-commit gap,
staged without any AMI code. Variant A is the pattern as written across the
backend; variant B is the same site with a declared collision outcome.

Run:  python3 docs/dilemmas/ISS001_DB_INSERT_RACE/kimi-k2/demo_race.py

Threads are fine here because this ISN'T the flaky stack: no uvicorn
serialization, no in-process throttle — just two connections and one UNIQUE
constraint, which is exactly the Cloud Run shape the brief warns about.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import threading

TRIALS = 20


def _db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _fresh(path: str) -> None:
    conn = _db(path)
    conn.execute("DROP TABLE IF EXISTS kv")
    conn.execute("CREATE TABLE kv (k TEXT PRIMARY KEY, v TEXT)")
    conn.commit()
    conn.close()


def _writer(path: str, name: str, barrier: threading.Barrier, recover: bool, out: list) -> None:
    conn = _db(path)
    try:
        found = conn.execute("SELECT k FROM kv WHERE k = 'race'").fetchone()
        barrier.wait(timeout=10)  # both reads land before either write
        if found is None:
            try:
                conn.execute("INSERT INTO kv (k, v) VALUES ('race', ?)", (name,))
                conn.commit()
                out.append(("inserted", name))
            except sqlite3.IntegrityError:
                if recover:
                    row = conn.execute("SELECT v FROM kv WHERE k = 'race'").fetchone()
                    conn.commit()
                    out.append(("recovered" if row else "LOST", name))
                else:
                    out.append(("IntegrityError", name))
        else:
            out.append(("seen", name))
    finally:
        conn.close()


def _trial(recover: bool) -> list:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        _fresh(path)
        barrier = threading.Barrier(2)
        out: list = []
        threads = [
            threading.Thread(target=_writer, args=(path, "A", barrier, recover, out)),
            threading.Thread(target=_writer, args=(path, "B", barrier, recover, out)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return [r for r, _ in out]
    finally:
        os.unlink(path)


def main() -> None:
    naive = [_trial(recover=False) for _ in range(TRIALS)]
    fixed = [_trial(recover=True) for _ in range(TRIALS)]

    naive_errors = sum(r.count("IntegrityError") for r in naive)
    naive_clean = sum(1 for r in naive if "IntegrityError" not in r)
    print(f"A. check-then-INSERT, no handler ({TRIALS} trials, barrier-widened window):")
    print(f"     trials where the loser ate IntegrityError: {TRIALS - naive_clean}/{TRIALS}")
    print(f"     total IntegrityErrors reaching the caller: {naive_errors}")

    fixed_recovered = sum(r.count("recovered") for r in fixed)
    fixed_lost = sum(r.count("LOST") for r in fixed)
    fixed_errors = sum(r.count("IntegrityError") for r in fixed)
    print(f"B. same race, declared outcome (recover = re-read the winner):")
    print(f"     IntegrityErrors reaching the caller: {fixed_errors}")
    print(f"     losers who recovered the winning row:  {fixed_recovered}/{TRIALS}")
    print(f"     rows lost:                           {fixed_lost}")

    if naive_errors > 0 and fixed_errors == 0 and fixed_lost == 0:
        print("VERDICT: the race fires on demand; the declared outcome absorbs every loss.")
    else:
        print("VERDICT: unexpected distribution — read the tallies, not this line.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
