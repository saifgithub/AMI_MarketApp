"""Render a UAT run's report.md (CR263): every catalogue case, its outcome in
this run per target, and its standing in the ledger.

    python qa/uat/report.py qa/uat/_runs/<ts>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalogue  # noqa: E402
import ledger  # noqa: E402

_ICON = {"passed": "PASS", "xfailed": "XFAIL (known finding)", "failed": "**FAIL**",
         "skipped": "skip", None: "—"}


def main(run_dir: Path) -> int:
    runs = {}
    for res in sorted(run_dir.glob("*/uat_results.json")):
        data = json.loads(res.read_text())
        runs[data.get("platform") or res.parent.name] = data["results"]
    areas = catalogue.load()
    pending = {t: set(ledger.pending(t)) for t in ledger.TARGETS}
    lines = [f"# UAT run {run_dir.name}", ""]
    totals: dict[str, dict[str, int]] = {}
    for target, results in runs.items():
        t = totals.setdefault(target, {})
        for outcome in results.values():
            t[outcome] = t.get(outcome, 0) + 1
    lines.append("## Summary")
    lines.append("")
    if not runs:
        lines.append("_No layer produced results._")
    for i, (target, t) in enumerate(totals.items(), 1):
        lines.append(f"{i}. **{target}**: " + ", ".join(f"{n} {o}" for o, n in sorted(t.items())))
    for target in ledger.TARGETS:
        lines.append(f"- ledger — {target}: {len(pending[target])} active case(s) not yet green at current version")
    lines.append("")

    failed = [(target, cid) for target, res in runs.items() for cid, o in res.items() if o == "failed"]
    if failed:
        lines += ["## Failures", ""]
        cases = catalogue.all_cases(areas)
        for i, (target, cid) in enumerate(failed, 1):
            lines.append(f"{i}. `{cid}` ({target}) — {cases[cid].title if cid in cases else '?'}")
        lines.append("")

    lines += ["## All cases", "", "| Case | Layer | Title | " + " | ".join(runs) + " |",
              "|---|---|---|" + "---|" * len(runs)]
    for a in areas:
        for c in a.cases:
            cells = [_ICON.get(runs[t].get(c.id)) for t in runs]
            status = " (blocked)" if c.status == "blocked" else ""
            lines.append(f"| {c.id} | {c.layer}{status} | {c.title} | " + " | ".join(cells) + " |")
    (run_dir / "report.md").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
