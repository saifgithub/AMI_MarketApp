"""test_registers_no_drift.py — CR081 + DEF203 guards on the generated registers.

The CR/Defect registers (`docs/defect/def_list.md`, `docs/forward_planning/cr_list.md`) are
GENERATED from one row-file per item (`_registry/<ID>.row.md`) by
`scripts/registers/gen_registers.py`.

**CR081 — drift.** Fails if the generated table drifts from its row-file source, i.e.
someone hand-edited the table, or edited a row file without regenerating. Degrade-loudly
(CR040): silent drift is exactly the failure the generated model exists to remove.

**DEF203 — the status cell holds a state, not a sentence.** The vocabulary lives in
`gen_registers.REGISTERS[...]["statuses"]` and is read from there rather than restated
here, so there is one definition to change. Worth its own test even though `verify` now
covers it, because the drift assertion below would report a status failure as "register
DRIFT" and send the reader to regenerate a table that is already correct.

Runs in the promote preflight. Tests our governance invariant, not a framework.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
GEN = REPO / "scripts" / "registers" / "gen_registers.py"


def _gen_module():
    spec = importlib.util.spec_from_file_location("gen_registers", GEN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not GEN.exists(), reason="register generator not present in this checkout")
def test_registers_match_their_row_files():
    r = subprocess.run(
        [sys.executable, str(GEN), "verify", "all"],
        capture_output=True, text=True, cwd=str(REPO),
    )
    assert r.returncode == 0, (
        "CR/Defect register DRIFT — def_list.md / cr_list.md do not match their "
        "_registry/*.row.md source. Edit the row file (not the generated table), then run "
        "`python scripts/registers/gen_registers.py gen all` and commit both.\n"
        + r.stdout + r.stderr
    )


@pytest.mark.skipif(not GEN.exists(), reason="register generator not present in this checkout")
def test_every_row_status_is_one_of_the_register_vocabulary():
    """DEF203. A status cell holding prose is not merely untidy — it is INVISIBLE to
    every filter that matches a token, and always in the same direction: the backlog
    reads shorter than it is.

    Measured 2026-08-06 before the fix: 22 distinct DEF values across 221 rows and 10
    CR values across 134, including four spellings of "fixed" and 20 cells holding whole
    sentences. DEF100's cell read `**open** — Saiful-liaison (via coder.store)...` and a
    token filter dropped it silently; three more (DEF063, DEF084, DEF093) carried a
    fixed-family token whose own prose said a half was still open.
    """
    gen = _gen_module()
    offenders: list[str] = []
    for name, reg in gen.REGISTERS.items():
        allowed = set(reg["statuses"])
        for path in sorted(reg["registry"].glob(f"{reg['prefix']}*.row.md")):
            status = gen.status_of(path.read_text())
            if status not in allowed:
                shown = status if len(status) <= 70 else status[:67] + "..."
                offenders.append(f"{path.stem.split('.')[0]}: {shown!r} "
                                 f"(allowed: {sorted(allowed)})")
    assert not offenders, (
        "DEF203 — register row(s) whose status cell is not one of the register's own "
        "vocabulary. A qualifier belongs in the DESCRIPTION column, where nothing "
        "parses it; the status column is read by counters.\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.skipif(not GEN.exists(), reason="register generator not present in this checkout")
def test_the_status_vocabularies_stay_distinct_per_register():
    """Non-vacuity for the test above, and a pin on the reason the two lists differ.

    A defect is broken or it is not; a CR is planned work that can legitimately sit in
    progress or stand open forever. Collapsing them to one shared list would make the
    test above pass while letting a CR be marked `fixed` and a defect `proposed`, which
    is how the four-spellings-of-fixed state arose in the first place.
    """
    gen = _gen_module()
    defs = set(gen.REGISTERS["def"]["statuses"])
    crs = set(gen.REGISTERS["cr"]["statuses"])
    assert defs != crs
    assert "proposed" not in defs, "a defect is not proposed — it is found"
    assert "fixed" not in crs, "a CR is delivered, not fixed"
    for reg in gen.REGISTERS.values():
        assert set(reg["open_statuses"]) <= set(reg["statuses"]), (
            "an open-state token that is not in the register's own vocabulary can never "
            "match, so the open count would silently read zero"
        )
