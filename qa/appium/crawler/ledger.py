"""Remember what has already been reported (CR163).

Without this, an autonomous crawler is worse than no crawler. Run 2 re-reports
everything run 1 found, the report becomes 90% noise, and within a week nobody
opens it — at which point a real new defect arrives and is not read either. The
ledger is what makes "run it every night" survivable.

The ledger is **committed to git**. It is a record of decisions — "we looked at
this and it was a false positive", "this one is filed as DEF251" — and those
decisions must outlive the machine that made them, be visible in review, and be
correctable by editing a file rather than by re-running anything.

Fingerprints deliberately exclude anything volatile. A finding's identity is
*what kind of problem, on what screen, about what thing* — not the pixel count,
not the timestamp, not how many frames it repeated for. An overflow that grows
from 8px to 12px after an unrelated change is the same defect; if the
fingerprint moved with the number, every run would rediscover it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

LEDGER_PATH = Path(__file__).resolve().parent / "known_findings.json"

# Statuses a human (or the triage step) can record against a fingerprint.
NEW = "new"            # seen, not yet triaged
FILED = "filed"        # promoted to an intake stub / DEF — do not re-report
FALSE_POSITIVE = "false_positive"  # judged not a defect — do not re-report
WONTFIX = "wontfix"    # real, accepted — do not re-report

SUPPRESSED = {FILED, FALSE_POSITIVE, WONTFIX}


def fingerprint(finding: dict) -> str:
    """Stable identity for a finding across runs.

    `screen` is the semantic screen fingerprint, not a screenshot hash — two
    runs that render the same controls are the same screen even if a price
    ticked.
    """
    parts = [
        str(finding.get("check") or finding.get("rule") or "unknown"),
        str(finding.get("screen", "")),
        # `detail` carries the discriminating capture (which asset, which
        # assertion). `element_label` does the same for layout findings.
        str(finding.get("detail") or finding.get("element_label") or ""),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


class Ledger:
    def __init__(self, path: Path = LEDGER_PATH):
        self.path = path
        self.entries: dict[str, dict] = {}
        if path.exists():
            self.entries = json.loads(path.read_text())

    def is_suppressed(self, finding: dict) -> bool:
        entry = self.entries.get(fingerprint(finding))
        return bool(entry and entry.get("status") in SUPPRESSED)

    def record(self, finding: dict, *, status: str = NEW, note: str = "") -> str:
        fp = fingerprint(finding)
        existing = self.entries.get(fp)
        if existing:
            existing["times_seen"] = existing.get("times_seen", 1) + 1
            if status != NEW:
                existing["status"] = status
                if note:
                    existing["note"] = note
        else:
            self.entries[fp] = {
                "status": status,
                "rule": finding.get("check") or finding.get("rule"),
                "screen": finding.get("screen", ""),
                "detail": finding.get("detail") or finding.get("element_label") or "",
                "summary": (finding.get("note") or "")[:200],
                "times_seen": 1,
                "note": note,
            }
        return fp

    def split(self, findings: list[dict]) -> tuple[list[dict], list[dict]]:
        """Return `(new, already_known)`. Only `new` is worth anyone's time;
        `already_known` is still counted so a report can honestly say
        "3 new, 11 known" rather than silently hiding the 11."""
        fresh, known = [], []
        for finding in findings:
            (known if self.is_suppressed(finding) else fresh).append(finding)
        return fresh, known

    def save(self) -> None:
        self.path.write_text(json.dumps(self.entries, indent=2, sort_keys=True) + "\n")
