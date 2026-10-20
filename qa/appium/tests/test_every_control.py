"""UAT-CTRL-001 (CR264): every screen reached, every control pressed.

Runs the exhaustive crawl (crawler/exhaustive_run.py) and fails when:

1. a known screen (every `ami.screen.*` in config/semantics_ids.py) was not reached;
2. a discovered control was neither pressed nor exempted (with a reason);
3. any press produced a finding: crash, new error-sink entry, overflow/clipping,
   dead tap, a control with no catalogue entry, or an outcome that contradicts
   the catalogue's stated intent (qa/uat/controls/*.yaml).

Everything is listed in the failure message; the full record is
`<report dir>/control_coverage.json` + `coverage.md`.

Deselect for normal runs: `-m "not exhaustive"`. It takes up to the global cap
(default 90 min) and, on a real session, spends one Room run.
"""

from __future__ import annotations

import os

import pytest

from crawler.exhaustive_run import run_exhaustive

pytestmark = [pytest.mark.exhaustive, pytest.mark.uat("UAT-CTRL-001")]


def test_every_screen_reached_every_control_pressed(device_profile, run_dir):
    out = run_exhaustive(
        device_profile,
        run_dir / "controls",
        per_screen_s=float(os.environ.get("AMI_CRAWL_PER_SCREEN", "90")),
        global_cap_s=float(os.environ.get("AMI_CRAWL_CAP", "5400")),
    )
    t = out.coverage.totals()
    summary = (f"screens {t['screens_reached']}/{t['screens_expected']} · controls "
               f"{t['controls_pressed']} pressed, {t['controls_exempt']} exempt, "
               f"{t['controls_unpressed']} unpressed of {t['controls_discovered']}")
    print(summary)
    if out.gate_failures:
        shown = "\n".join(f"  {i}. {f}" for i, f in enumerate(out.gate_failures[:60], 1))
        more = f"\n  ... and {len(out.gate_failures) - 60} more" if len(out.gate_failures) > 60 else ""
        pytest.fail(f"{summary}\n{len(out.gate_failures)} gate failure(s):\n{shown}{more}\n"
                    f"full record: {run_dir / 'controls' / 'coverage.md'}", pytrace=False)
