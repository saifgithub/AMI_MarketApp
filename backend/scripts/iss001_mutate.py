"""ISS001 — mutation check for the insert tripwire, claim() and schema_truth.

Breaks one load-bearing line at a time in a scratch COPY of the tree (the working tree is never
edited), runs the ISS001 tests against the copy, and requires them to go red. A SURVIVED mutant
means a guarantee the docs make is decorative. STALE means the anchor moved: update this file.

Run from anywhere:  python backend/scripts/iss001_mutate.py   (exit 0 = every mutant killed)

Why a copy rather than a revert-in-place: the shared checkout may be dirty and other lanes read
these files; a crashed in-place mutation would leave a broken tripwire on disk.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

BACKEND = pathlib.Path(__file__).resolve().parent.parent
REPO = BACKEND.parent

TESTS = [
    "tests/unit/test_iss001_claim.py",
    "tests/unit/test_iss001_insert_tripwire.py",
    "tests/unit/test_iss001_observer.py",
    "tests/unit/test_cr279_beta_env.py",
    "tests/unit/test_config_compose_parity.py",
]
SUPPORT_TESTS = ["tests/unit/test_p15_check_then_insert_guard.py"]

AMI = "app/db/ami_claim.py"
OBS = "tests/iss001_observer.py"

# name -> (file, old, new)
MUTANTS = {
    "claim accepts a key with NULLs against a full (vacuous) arbiter":
        (AMI, '        if not null_cols and cols == set(key):', '        if cols == set(key):'),
    "claim drops the ON CONFLICT clause (plain INSERT)":
        (AMI, '    stmt = ins.on_conflict_do_nothing(**kw).returning(*pk_cols)', '    stmt = ins.returning(*pk_cols)'),
    "tripwire treats every table as sanctioned (never fires)":
        (AMI, '        if table in _scope.get():', '        if True:'),
    "tripwire ignores the conflict-target check (any ON CONFLICT passes)":
        (AMI, '            if table in tables and _conflict_target_ok(statement, tables[table]):', '            if True:'),
    "raise mode never raises":
        (AMI, '        if mode == "raise":\n            if baselined:', '        if False:\n            if baselined:'),
    "baseline never matches (a listed site raises)":
        (AMI, '        baselined = (table, site) in pinned', '        baselined = False'),
    "baseline matches everything (an unlisted site passes)":
        (AMI, '        baselined = (table, site) in pinned', '        baselined = True'),
    "app_frames_only is ignored (fixtures get policed)":
        (AMI, '        if app_frames_only and not frames:', '        if False:'),
    "schema_truth skips composite keys":
        (AMI, '            if arb.name == "PRIMARY" or len(arb.columns) < 2:', '            if True:'),
    "schema_truth ignores a covering partial index (DEF499 tables reappear)":
        (AMI, '                if _null_case_covered(t, arb, c):', '                if False:'),
    "unclaimed() accepts an empty reason":
        (AMI, '    if not why.strip():', '    if False:'),
    "tripwire_installed always says yes":
        (AMI, '    return handler is not None and event.contains(engine, "before_cursor_execute", handler)', '    return True'),
    "get_engine does not install the tripwire":
        ("app/db/session.py", '        _install_insert_tripwire(_engine)\n', ''),
    "Beta accepts INSERT_TRIPWIRE_MODE=off":
        ("app/core/beta_boot.py", '    if getattr(s, "insert_tripwire_mode", "log") == "off":', '    if False:'),
    "default mode is off":
        ("app/core/config.py", 'insert_tripwire_mode: Literal["off", "log", "raise"] = "log"', 'insert_tripwire_mode: Literal["off", "log", "raise"] = "off"'),
    "compose default is off":
        ("docker-compose.yml", 'INSERT_TRIPWIRE_MODE: ${INSERT_TRIPWIRE_MODE:-log}', 'INSERT_TRIPWIRE_MODE: ${INSERT_TRIPWIRE_MODE:-off}'),
    "observer aggregation takes the first status (order-dependent)":
        (OBS, '    return max(statuses, key=lambda s: SEVERITY[s])', '    return next(iter(statuses))'),
    "observer never reports":
        (OBS, '                sink({', '                (lambda *_: None)({'),
}


def _stage(dest: pathlib.Path) -> None:
    (dest / "backend").mkdir(parents=True)
    for d in ("app", "alembic", "scripts"):
        shutil.copytree(BACKEND / d, dest / "backend" / d, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(BACKEND / "alembic.ini", dest / "backend" / "alembic.ini")
    shutil.copy(BACKEND / "Dockerfile", dest / "backend" / "Dockerfile")
    tests = dest / "backend" / "tests"
    (tests / "unit").mkdir(parents=True)
    for f in ("__init__.py", "conftest.py", "iss001_observer.py"):
        shutil.copy(BACKEND / "tests" / f, tests / f)
    shutil.copytree(BACKEND / "tests" / "fixtures", tests / "fixtures")
    shutil.copy(BACKEND / "tests" / "unit" / "__init__.py", tests / "unit" / "__init__.py")
    for t in TESTS + SUPPORT_TESTS:
        shutil.copy(BACKEND / t, dest / "backend" / t)
    shutil.copy(REPO / "docker-compose.yml", dest / "docker-compose.yml")
    (dest / "infra").mkdir()
    shutil.copy(REPO / "infra" / "beta.env.example", dest / "infra" / "beta.env.example")


def _run(root: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS, "-q", "-x", "-p", "no:cacheprovider"],
        cwd=root / "backend", capture_output=True, text=True, env={**__import__("os").environ, "PYTHONPATH": "."},
    )


def main() -> int:
    survived: list[str] = []
    with tempfile.TemporaryDirectory() as d:
        base = pathlib.Path(d) / "base"
        _stage(base)
        clean = _run(base)
        if clean.returncode != 0:
            print("UNMUTATED TREE IS RED — fix that first\n" + clean.stdout[-1500:])
            return 2
        print("baseline green")
        for name, (rel, old, new) in MUTANTS.items():
            work = pathlib.Path(d) / "m"
            shutil.rmtree(work, ignore_errors=True)
            shutil.copytree(base, work)
            path = work / ("backend/" + rel if not rel.startswith("docker-compose") else rel)
            src = path.read_text()
            if old not in src:
                print(f"STALE    {name}: anchor not found in {rel}")
                survived.append(name)
                continue
            path.write_text(src.replace(old, new, 1))
            killed = _run(work).returncode != 0
            print(f"{'killed  ' if killed else 'SURVIVED'} {name}")
            if not killed:
                survived.append(name)
    print(f"\n{len(MUTANTS) - len(survived)} killed, {len(survived)} survived/stale of {len(MUTANTS)}")
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main())
