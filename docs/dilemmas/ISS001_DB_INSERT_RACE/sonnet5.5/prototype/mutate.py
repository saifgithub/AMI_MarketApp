"""Mutation check for the prototype: break one load-bearing line at a time, run the tests on a
scratch copy, and require that the suite goes red. A green mutant means a claim in SOLUTION.md is
decorative. Run:  python mutate.py   (from this folder; copies to a temp dir, never edits in place)
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).parent

MUTANTS = {
    "claim ignores NULLs in the key (accepts the vacuous arbiter)":
        ('        if not null_cols and cols == set(key):', '        if cols == set(key):'),
    "tripwire never fires":
        ('        if " ON CONFLICT" in up or table in _scope.get():', '        if True:'),
    "claim drops the ON CONFLICT clause (plain INSERT)":
        ('    stmt = ins.on_conflict_do_nothing(**kw).returning(*pk_cols)', '    stmt = ins.returning(*pk_cols)'),
    "schema_truth skips composite keys":
        ('            if arb.name == "PRIMARY" or len(arb.columns) < 2:', '            if True:'),
    "unclaimed() accepts an empty reason":
        ('    if not why.strip():', '    if False:'),
    "observer never reports":
        ('                sink({', '                (lambda *_: None)({'),
}


def main() -> int:
    survived = []
    for name, (old, new) in MUTANTS.items():
        with tempfile.TemporaryDirectory() as d:
            for f in ("ami_claim.py", "test_prototype.py"):
                shutil.copy(HERE / f, d)
            p = pathlib.Path(d) / "ami_claim.py"
            src = p.read_text()
            if old not in src:
                print(f"STALE   {name}: anchor not found")
                survived.append(name)
                continue
            p.write_text(src.replace(old, new, 1))
            r = subprocess.run([sys.executable, "-m", "pytest", d, "-q", "-x", "-p", "no:cacheprovider"],
                               capture_output=True, text=True)
            killed = r.returncode != 0
            print(f"{'killed ' if killed else 'SURVIVED'} {name}")
            if not killed:
                survived.append(name)
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main())
