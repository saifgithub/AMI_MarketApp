#!/usr/bin/env python3
"""UAT release gate (CR263) — run before every promote-to-alpha, TestFlight
build and Play Store publish.

Saiful, 2026-10-19: "before sending the app to testflight, play store and
promote-to-alpha, the test scripts must be updated. the added/updated tests
must have been run before any of these 3 activities were done."

Three checks, in order:

1. **Catalogue guards** — `qa/uat/tests_offline` green: schema valid, script
   freshly rendered, every active case has a test, and every screen/router file
   belongs to an area (a new screen with no UAT area fails here).
2. **Script updated** — every source file changed since this activity last
   passed the gate must have its area's catalogue or tests changed in the same
   range, or a commit touching it must carry a `UAT-Impact: none (<reason>)`
   trailer. Changing a feature without saying what that does to its UAT is the
   thing being forbidden.
3. **Tests run** — every active case for the activity's targets has a passing
   ledger entry at its *current* fingerprint (case + citing tests + covered
   source). A changed case, test or feature therefore needs a fresh run.

   | activity    | targets that must be green          |
   |-------------|-------------------------------------|
   | testflight  | api + ios                           |
   | playstore   | api + android                       |
   | alpha       | ios or android (api runs post-deploy, see `alpha-post`) |
   | alpha-post  | api — run by /promote-to-alpha right after the deploy    |

   Alpha is the odd one: the API cases for a backend change can only pass once
   that change is deployed, so pre-deploy demands device evidence and the API
   evidence is demanded immediately after, by `alpha-post`, which fails the
   promotion loudly.

Escape hatch: `UAT_GATE_OVERRIDE="<reason>"` passes the gate with a banner and
an appended line in `.deliveryos/uat_overrides.log`. Never silent (CR040).

On a pass the activity's base moves to HEAD, so the next run's "changed since"
range starts here. Exit 0 = pass, 1 = fail, 2 = could not run.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UAT_DIR = REPO_ROOT / "qa" / "uat"
sys.path.insert(0, str(UAT_DIR))

import catalogue  # noqa: E402
import ledger  # noqa: E402

OVERRIDE_LOG = REPO_ROOT / ".deliveryos" / "uat_overrides.log"
# The commit the gate was wired into the release paths at — the "changed
# since" floor until an activity has passed once. Earlier commits predate the
# rule and are not held against it.
GATE_EPOCH = "48ba26b8"
ACTIVITIES = {
    "testflight": [["api"], ["ios"]],
    "playstore": [["api"], ["android"]],
    "alpha": [["ios", "android"]],
    "alpha-post": [["api"]],
}
IMPACT_TRAILER = "UAT-Impact: none"
COVERAGE_ROOTS = ("mobile/lib/**", "backend/app/**")


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO_ROOT), *args],
                          capture_output=True, text=True, check=True).stdout


def _is_ancestor(sha: str) -> bool:
    return subprocess.run(["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", sha, "HEAD"],
                          capture_output=True).returncode == 0


def _base(activity: str) -> str:
    key = "alpha" if activity == "alpha-post" else activity
    base = ledger.load().get("releases", {}).get(key)
    if base and _is_ancestor(base):
        return base
    return GATE_EPOCH


def check_guards() -> list[str]:
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests_offline"],
                       cwd=UAT_DIR, capture_output=True, text=True)
    if r.returncode == 0:
        return []
    tail = "\n".join(r.stdout.strip().splitlines()[-25:])
    return [f"catalogue guards failed (cd qa/uat && pytest tests_offline):\n{tail}"]


def check_script_updated(base: str) -> list[str]:
    changed = set(_git("diff", "--name-only", base, "--").split())
    changed |= set(_git("ls-files", "--others", "--exclude-standard").split())
    areas = catalogue.load()
    cites = {layer: catalogue.citations(layer) for layer in catalogue.EXECUTORS}
    problems = []
    for a in areas:
        sources = sorted(f for f in changed
                         if any(fnmatch.fnmatch(f, g) for g in a.covers)
                         and any(fnmatch.fnmatch(f, r) for r in COVERAGE_ROOTS))
        if not sources:
            continue
        uat_files = {f"qa/uat/cases/{a.area}.yaml"}
        for c in a.cases:
            for paths in cites.values():
                uat_files |= {p.relative_to(REPO_ROOT).as_posix() for p in paths.get(c.id, [])}
        if uat_files & changed:
            continue
        unexplained = [f for f in sources
                       if IMPACT_TRAILER not in _git("log", "--format=%B", f"{base}..HEAD", "--", f)]
        if unexplained:
            problems.append(
                f"area '{a.area}': source changed but its UAT cases/tests did not — "
                f"update qa/uat/cases/{a.area}.yaml (or its tests), or add a "
                f"'{IMPACT_TRAILER} (<reason>)' trailer to the commit:\n    "
                + "\n    ".join(unexplained))
    return problems


def check_runs(activity: str) -> list[str]:
    problems = []
    for alternatives in ACTIVITIES[activity]:
        pend = {t: ledger.pending(t) for t in alternatives}
        if any(not ids for ids in pend.values()):
            continue
        for t, ids in pend.items():
            head = ", ".join(ids[:15]) + (f" … +{len(ids) - 15} more" if len(ids) > 15 else "")
            problems.append(f"{t}: {len(ids)} case(s) not passing at their current version — "
                            f"run scripts/uat/run_uat.sh --{'api' if t == 'api' else 'device ' + t} "
                            f"--changed-only\n    {head}")
        if len(alternatives) > 1:
            problems.append("(any ONE of " + " / ".join(alternatives) + " being fully green satisfies this)")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--for", dest="activity", required=True, choices=sorted(ACTIVITIES))
    ap.add_argument("--no-mark", action="store_true", help="don't move the activity's base on pass")
    args = ap.parse_args()

    try:
        base = _base(args.activity)
        problems = check_guards()
        if not problems:
            problems += check_script_updated(base)
            problems += check_runs(args.activity)
    except (subprocess.CalledProcessError, catalogue.CatalogueError) as exc:
        print(f"UAT GATE: COULD NOT RUN — {exc}")
        return 2

    print(f"UAT gate — {args.activity} (changes since {base[:10]})")
    if problems:
        for i, p in enumerate(problems, 1):
            print(f"{i}. {p}")
        reason = os.environ.get("UAT_GATE_OVERRIDE", "").strip()
        if not reason:
            print("VERDICT: FAIL")
            return 1
        OVERRIDE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with OVERRIDE_LOG.open("a") as fh:
            fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {args.activity} "
                     f"{_git('rev-parse', 'HEAD').strip()} {len(problems)} problem(s) "
                     f"OVERRIDDEN: {reason}\n")
        print("!" * 72)
        print(f"!! UAT GATE OVERRIDDEN ({len(problems)} problem(s)): {reason}")
        print("!" * 72)
        print("VERDICT: OVERRIDE")
        return 0

    if not args.no_mark:
        data = ledger.load()
        key = "alpha" if args.activity == "alpha-post" else args.activity
        data.setdefault("releases", {})[key] = _git("rev-parse", "HEAD").strip()
        ledger.save(data)
    print("VERDICT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
