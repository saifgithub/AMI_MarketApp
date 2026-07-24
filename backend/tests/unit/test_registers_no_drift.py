"""test_registers_no_drift.py — CR081 guard.

The CR/Defect registers (`docs/defect/def_list.md`, `docs/forward_planning/cr_list.md`) are
GENERATED from one row-file per item (`_registry/<ID>.row.md`) by
`scripts/registers/gen_registers.py`. This guard fails if the generated table drifts from its
row-file source — i.e. someone hand-edited the table, or edited a row file without
regenerating. Degrade-loudly (CR040): silent drift is exactly the failure the generated model
exists to remove. Runs in the promote preflight. Tests our governance invariant, not a
framework.
"""
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
GEN = REPO / "scripts" / "registers" / "gen_registers.py"


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
