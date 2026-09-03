"""CR221 §7 — did shipping the data stop the Room asking for it?

Runs the CR219 convene twice against ONE cached profile, with the CR221 render
flags off and then on, and scores the `DATA I LACKED:` sections with the 49-item
register. The primary endpoint is demand extinction per item, not the verdict:
`risk_officer.py:32` records 19.7% of convenes splitting across byte-identical
inputs, so a verdict that moves after a field lands cannot be told from a coin
at any n this can afford.

Three deliberate reuses, because a re-implementation would measure a different
thing:

  * `harness/run_convene.py::run_convene` drives the turns — same phase order,
    same production `build_room_messages`, same n-draw PM vote.
  * The evaluation addendum is copied BYTE-IDENTICAL from
    `evidence/convene_gemini.py`. It is the instrument the 127-line corpus was
    measured with, and a reworded one would not be the same measurement.
  * `evidence/items.py::claims` scores the lines, so "did A1 stop being asked
    for" is answered by the same matcher that built the register.

**Why not R53's shipped `DATA GAPS:` tail.** It landed 2026-09-03 and is the
right permanent instrument, but it is ANALYSTS-only (`room_prompts.py:1693`)
— four agents. The register's demand comes from twelve: A1's fourteen lines
span six agents, most of them researchers and risk debators the shipped tail
never reaches. Measuring with it would score a fraction of the demand and call
it the whole.

The addendum rides on a `VLLMClient` SUBCLASS rather than an edit to the
harness: `run_convene` takes the client, so appending there puts the addendum
on the user message exactly where `convene_gemini.py` puts it, and CR219's
files stay untouched.

Needs the measurement fact store, which is not the solo-dev `.local.db`:

    DATABASE_URL="sqlite:///$PWD/docs/forward_planning/CR221_room_data_demand_sourcing/measurement/edgar.db" \\
      backend/.venv/bin/python <this>/replay.py --mandates long
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_CR = os.path.abspath(os.path.join(_HERE, ".."))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(_CR, "evidence"))
sys.path.insert(0, os.path.join(
    _ROOT, "docs/forward_planning/CR219_room_prompt_contradictions/harness"))

from _paths import bootstrap  # noqa: E402  (CR219 harness)

bootstrap()

import items  # noqa: E402  (CR221 evidence)
from app.core.config import settings  # noqa: E402
from run_convene import run_convene  # noqa: E402
from vllm_client import DEFAULT_BASE_URL, VLLMClient  # noqa: E402

PROFILES = os.path.join(_HERE, "profiles")
RESULTS = os.path.join(_HERE, "results")

# Byte-identical to `evidence/convene_gemini.py::ADDENDUM`. Do not reword it:
# the 127-line baseline corpus was elicited with these exact words, and the
# register's per-item counts are counts of what THIS question produced.
ADDENDUM = """

─── EVALUATION ADDENDUM (not part of your normal turn — answer it AFTER your normal answer) ───
Having written your turn, append a final section headed exactly `DATA I LACKED:`.

List as bullets any datum you needed to reach a better decision that this prompt did not
give you. For each one state:
  (a) the datum,
  (b) what your answer would have changed to if you had it,
  (c) whether you believe it was ABSENT, WITHHELD from you deliberately, or you were
      FORBIDDEN from using it.

Then append a second section headed exactly `PROMPT CONTRADICTIONS:`. If any instruction in
this prompt contradicts any other instruction, or contradicts the fact sheet you were given,
quote BOTH sides verbatim and say which one you obeyed and why. If there are none, write
`PROMPT CONTRADICTIONS: none`.

Be blunt. This section is read by the engineers who wrote the prompt, not by the user."""

# The fields this CR has shipped so far, and the item each one answers. H2 is
# the negative control: no free source was found for it, nothing was built, so
# its ask must NOT fall. A treatment arm where H2 also drops is measuring the
# model's mood, not the data.
SHIPPED_ITEMS = ("A1", "A3")
NEGATIVE_CONTROL = "H2"
FLAGS = ("room_debt_maturity_enabled", "room_cost_of_debt_enabled")


class AddendumClient(VLLMClient):
    """The production prompt, plus the instrument, on the user message only."""

    def chat(self, system: str, user: str, **kw):  # type: ignore[override]
        return super().chat(system, user + ADDENDUM, **kw)


def requests_in(convene: dict) -> list[tuple[str, str]]:
    """`(agent, request)` for every `(a)` line — `inventory.load_requests`' rule."""
    out: list[tuple[str, str]] = []
    for turn in convene.get("turns", []):
        block = re.search(
            r"DATA I LACKED:(.*?)(?=PROMPT CONTRADICTIONS:|$)",
            turn.get("answer") or "", re.S,
        )
        if not block:
            continue
        for line in re.findall(r"\(a\)\s*(.+)", block.group(1)):
            out.append((turn["agent"], re.sub(r"\*\*|\s+", " ", line).strip().rstrip(".")))
    return out


def score(convene: dict) -> dict[str, dict]:
    """Per item: how many lines asked for it, and from how many distinct agents."""
    lines = requests_in(convene)
    per: dict[str, dict] = {}
    for agent, text in lines:
        for item in items.claims(text):
            row = per.setdefault(item.id, {"lines": 0, "agents": set(), "label": item.label})
            row["lines"] += 1
            row["agents"].add(agent)
    for row in per.values():
        row["agents"] = sorted(row["agents"])
    return per


def arm(label: str, on: bool, *, ticker: str, mandate: str, client: VLLMClient) -> dict:
    for flag in FLAGS:
        setattr(settings, flag, on)
    convene = run_convene(
        ticker=ticker, mandate_label=mandate, client=client, profiles_dir=PROFILES,
    )
    convene["cr221_arm"] = label
    convene["cr221_flags"] = {f: getattr(settings, f) for f in FLAGS}
    return convene


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ticker", default="CAT")
    ap.add_argument("--mandates", nargs="+", default=["long"])
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--out-root", default=RESULTS)
    args = ap.parse_args()

    os.makedirs(args.out_root, exist_ok=True)
    os.makedirs(PROFILES, exist_ok=True)
    client = AddendumClient(args.base_url)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    totals: dict[str, collections.Counter] = {"off": collections.Counter(),
                                              "on": collections.Counter()}
    agents_seen: dict[str, dict[str, set]] = {"off": {}, "on": {}}

    for mandate in args.mandates:
        for label, on in (("off", False), ("on", True)):
            convene = arm(label, on, ticker=args.ticker, mandate=mandate, client=client)
            scored = score(convene)
            convene["cr221_scored"] = scored
            path = os.path.join(
                args.out_root, f"{stamp}_{args.ticker}_{mandate}_{label}.json")
            with open(path, "w") as fh:
                json.dump(convene, fh, indent=2, default=str)
            print(f"  [{mandate}/{label}] {len(requests_in(convene))} request lines "
                  f"-> {len(scored)} items   {os.path.basename(path)}", flush=True)
            for item_id, row in scored.items():
                totals[label][item_id] += row["lines"]
                agents_seen[label].setdefault(item_id, set()).update(row["agents"])

    print("\n" + "=" * 78)
    print(f"DEMAND EXTINCTION — {args.ticker} × {len(args.mandates)} mandate(s)")
    print("=" * 78)
    print(f"{'item':5s} {'off':>10s} {'on':>10s}  label")
    for item_id in sorted(set(totals['off']) | set(totals['on'])):
        label = next((i.label for i in items.ITEMS if i.id == item_id), "?")
        marker = ""
        if item_id in SHIPPED_ITEMS:
            marker = "  <-- SHIPPED, must fall"
        elif item_id == NEGATIVE_CONTROL:
            marker = "  <-- negative control, must NOT fall"
        print(f"{item_id:5s} {totals['off'][item_id]:>10d} {totals['on'][item_id]:>10d}"
              f"  {label[:44]}{marker}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
