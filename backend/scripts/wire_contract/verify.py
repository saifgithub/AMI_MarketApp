"""ISS002/CR208 — the gate. Run after the backend suite; exits non-zero on drift.

    backend/.venv/bin/python backend/scripts/wire_contract/verify.py [--update-baseline]

**Why UNVERIFIED is ratcheted rather than failed outright.** ISS002's verdict
says `UNVERIFIED` must be a hard failure, never a silent pass, and it is right
about the principle: a surface nobody observed has not been checked, and
treating "no evidence" as "no problem" is the DEF169/DEF190 defect exactly.

But 40 of 85 surfaces are unverified today (DEF367 — 47%, measured, not
estimated). Failing on all of them ships a gate that is red on the day it lands,
and a gate whose failing state is its normal state teaches the operator that
firing does not mean stop. This project has paid for that lesson three separate
times — DEF277's audit gate, the tree gate, and DEF200's own vacuity guard,
which asserted on the number that was supposed to reach zero and went red the
moment the work got done.

So the honest form is a ratchet, the same shape DEF200 already uses: today's
unverified surfaces are enumerated by name in `unverified_baseline.json`, a
NEW unverified surface fails immediately, and the baseline may only shrink.
Nothing passes silently — every unverified surface is written down, countable,
and in the way. What changes is that the count is a debt with a name attached
rather than an alarm nobody can act on.

A FAIL is never ratcheted. There is no baseline for a key the server cannot
emit, because that is a live client/server disagreement, not coverage debt.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compare import run, surface_id  # noqa: E402
from unreachable import find_unreachable  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CAPTURE = REPO / "backend" / "tests" / "_wire_capture.jsonl"
BASELINE = HERE / "unverified_baseline.json"


def _load_baseline() -> Counter:
    """The baseline as a MULTISET, not a set.

    DEF367: two distinct `fromJson` call sites in `api_client.dart` can share a
    (verb, endpoint, class) triple and therefore a `surface_id` —
    `gamesRecordPrs` has one, parsing `prs` as a list and again as a scalar.
    They are two checks. Loaded as a set, one of them could become verified
    while the other stayed unverified and the gate would say nothing: the id is
    still present on both sides, so neither the NEW nor the RECOVERED
    comparison fires. Counter arithmetic keeps the two apart without changing a
    single baseline string.
    """
    if not BASELINE.exists():
        return Counter()
    return Counter(json.loads(BASELINE.read_text())["unverified"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update-baseline", action="store_true")
    args = ap.parse_args()

    if not CAPTURE.exists():
        print("WIRE CONTRACT: no capture file at", CAPTURE)
        print("  The backend suite must run first — it writes the capture.")
        print("  An absent capture makes every surface look UNVERIFIED for the")
        print("  wrong reason, so this is a hard failure, not an empty pass.")
        return 1

    # DEF367 — the branch above checked EXISTENCE, and the hazard is CONTENT.
    # `conftest.py` truncates and rewrites the capture on every pytest session,
    # so running one test file leaves a real, present, near-empty capture behind.
    # Measured 2026-08-29: a 0-row capture reported "82 UNVERIFIED" — every
    # surface on the board, for exactly the reason the missing-file branch calls
    # out — and `--update-baseline` wrote all 82 into the baseline without a
    # word. The guard was there and did not cover the way it actually breaks.
    n_captured = sum(1 for line in CAPTURE.read_text(encoding="utf-8").splitlines()
                     if line.strip())
    if n_captured == 0:
        print(f"WIRE CONTRACT: capture at {CAPTURE} is EMPTY ({n_captured} responses).")
        print("  Some pytest session ran and observed nothing, which is not the")
        print("  same fact as 'the surfaces are unobserved'. Re-run the FULL")
        print("  suite: backend/.venv/bin/python -m pytest backend/tests/unit/ -q")
        return 1

    results = run(CAPTURE)
    fails = [r for r in results if r["status"] == "FAIL"]
    unverified = sorted(surface_id(r) for r in results if r["status"] == "UNVERIFIED")
    passes = [r for r in results if r["status"] == "PASS"]
    skips = [r for r in results if r["status"] == "SKIP"]
    nested_fails = [
        (r, n) for r in results for n in r.get("nested", []) if n["status"] == "FAIL"
    ]
    dead_models = find_unreachable()

    print(f"WIRE CONTRACT: {len(results)} auto-discovered surfaces | "
          f"{len(passes)} PASS  {len(fails)} FAIL  {len(unverified)} UNVERIFIED  "
          f"{len(skips)} SKIP")

    if args.update_baseline:
        # DEF367 — the file's own comment says "do not add an entry to get a
        # build past the gate". That was a request, and this is the same
        # sentence with an exit code behind it. A baseline update may only ever
        # REMOVE: an addition means either a genuine new blind spot (which must
        # be argued for, not absorbed) or a capture that did not see enough
        # (which is the empty-capture hazard one branch up, in partial form).
        # Both are refusals. Found by doing it: one --update-baseline against a
        # truncated capture turned a 40-entry ratchet into an 82-entry rubber
        # stamp in a single command, with a success message.
        additions = sorted((Counter(unverified) - _load_baseline()).elements())
        if additions:
            print(f"  REFUSED: {len(additions)} surface(s) would be ADDED to the "
                  f"baseline. A ratchet only shrinks.")
            for a in additions[:10]:
                print(f"        {a}")
            if len(additions) > 10:
                print(f"        ... and {len(additions) - 10} more")
            print("  If a genuinely new blind spot exists, add it deliberately by "
                  "hand and say why in the DEF367 row.")
            print(f"  Capture held {n_captured} responses — a full suite run "
                  f"produces well over a thousand.")
            return 1
        BASELINE.write_text(json.dumps({
            "_comment": (
                "ISS002/CR208 — surfaces with no observable response during the "
                "backend suite. DEF367. This list is meant to SHRINK: a new entry "
                "fails the gate, and removing one is the celebration. Do not add "
                "an entry to get a build past the gate."
            ),
            "count": len(unverified),
            "unverified": unverified,
        }, indent=2) + "\n")
        print(f"  baseline updated -> {len(unverified)} unverified surfaces")
        return 0

    ok = True

    for r in fails:
        ok = False
        print(f"  FAIL  {r['class']} <- {r['verb']} {r['endpoint']}")
        if r.get("missing_and_unemittable"):
            print(f"        client reads keys the server has no branch for: "
                  f"{r['missing_and_unemittable']}")
        if r.get("unsatisfied_alt_groups"):
            print(f"        no alternative satisfied: {r['unsatisfied_alt_groups']}")
    for r, n in nested_fails:
        ok = False
        print(f"  FAIL  {n['class']} via {n['via']}: {n['missing_and_unemittable']}")

    baseline = _load_baseline()
    new_unverified = sorted((Counter(unverified) - baseline).elements())
    if new_unverified:
        ok = False
        print(f"  {len(new_unverified)} NEW unverified surface(s) — a surface with no "
              f"observable response has not been checked:")
        for s in new_unverified:
            print(f"        {s}")
        print("        Add a route-level test that produces a real response.")

    recovered = sorted((baseline - Counter(unverified)).elements())
    if recovered:
        ok = False
        print(f"  {len(recovered)} surface(s) are now verified — remove them from "
              f"{BASELINE.name} in the same commit, or the count stops meaning "
              f"'still outstanding':")
        for s in recovered:
            print(f"        {s}")

    if dead_models:
        ok = False
        print(f"  {len(dead_models)} Dart model(s) parse nothing — a fromJson with no "
              f"caller cannot be observed and is dead on the client:")
        for c in dead_models:
            print(f"        {c}")

    print("WIRE VERDICT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
