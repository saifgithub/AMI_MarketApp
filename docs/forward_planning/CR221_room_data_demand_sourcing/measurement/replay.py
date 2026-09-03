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
NEGATIVE_CONTROL = "H2"

# One arm per shipped GROUP, never one arm for everything: demand extinction is
# a per-item claim, and two groups behind one switch cannot be attributed
# separately. Every flag not named by an arm is forced False for that arm, so
# `off` is a real baseline rather than "whatever the process last set".
ARMS: dict[str, dict[str, bool]] = {
    "off": {},
    "debt": {
        "room_debt_maturity_enabled": True,
        "room_cost_of_debt_enabled": True,
    },
    "cash": {
        "room_cashflow_bridge_enabled": True,
        "fundamentals_fcf_from_statements_enabled": True,
    },
    "history": {
        "room_fcf_history_enabled": True,
        "room_fcf_conversion_enabled": True,
        "room_roe_history_enabled": True,
    },
}
ARM_ITEMS = {
    "debt": ("A1", "A3"),
    "cash": ("C3", "C4"),
    "history": ("C2", "C5", "B2"),
}
FLAGS = tuple(sorted({flag for spec in ARMS.values() for flag in spec}))


def _apply_def400(profile: dict) -> dict:
    """DEF400's effect, applied to the ONE cached profile the arms share.

    `fundamentals_fcf_from_statements_enabled` acts inside
    `fetch_live_fundamentals`, so on a replay it would need a second profile
    build — and R46's one-pickle rule exists because market data moves between
    fetches, which would confound every arm in the comparison. This does the
    same substitution on the pickle instead: deterministic arithmetic over
    `free_cash_flow_ttm`, `market_cap` and `capital_return_ttm`, all three of
    which are already IN the pickle, so no second fetch and no second snapshot.
    """
    derived = profile.get("free_cash_flow_ttm")
    if derived is None:
        return profile
    patched = dict(profile)
    patched["free_cash_flow"] = derived
    market_cap = patched.get("market_cap")
    if market_cap:
        patched["fcf_yield"] = round(derived / market_cap * 100, 1)
    returned = patched.get("capital_return_ttm")
    if returned is not None and derived > 0:
        patched["capital_return_pct_fcf"] = round(returned / derived * 100)
    return patched


class AddendumClient(VLLMClient):
    """The production prompt, plus the instrument, on the user message only."""

    def chat(self, system: str, user: str, **kw):  # type: ignore[override]
        return super().chat(system, user + ADDENDUM, **kw)


_BULLET = re.compile(r"^[ \t]*(?:[-*\u2022]|\d+\.)[ \t]+", re.M)
_DATUM_LABEL = re.compile(r"\*{0,2}Datum:?\*{0,2}[ \t]*(.+)", re.I)


def _clean(text: str) -> str:
    return re.sub(r"\*\*|\s+", " ", text).strip().strip(":").strip().rstrip(".")


def _datum_of(bullet: str) -> str | None:
    """The DATUM a bullet names, across the three shapes the models actually emit.

    The addendum asks for `(a) the datum`. `gemini-3.1-pro-preview` — which
    produced CR219's 127-line corpus and therefore the register's per-item
    counts — complied literally, so `inventory.load_requests` reads `(a)` and
    is right to. `qwen3.8-flash-next`, the production model this replay runs
    against, complies three different ways WITHIN A SINGLE CONVENE (measured
    2026-09-03, CAT x long):

        - Real-time order flow imbalance near $771.39; (b) ...   <- (a) is the datum
        - Segment revenue breakdown: (a) The specific percentage ...  <- headline is
        *   **Datum:** Segment-level revenue and EBITDA ...           <- labelled

    Reading `(a)` blindly across all three scores the RATIONALE as the ask for
    two of them, which is how the first pilot recorded a request for the debt
    maturity ladder as an interest-coverage ask. This is measurement plumbing,
    not a scoring choice: `inventory.py` stays exactly as it is, because the
    banked corpus it reads has exactly one shape.
    """
    text = bullet.strip()
    if not text:
        return None
    labelled = _DATUM_LABEL.match(text)
    if labelled:
        return _clean(labelled.group(1).split("(b)")[0]) or None
    head, marker, rest = text.partition("(a)")
    if not marker:
        return None
    head = _clean(head)
    if head:
        return head
    return _clean(rest.split("(b)")[0]) or None


def requests_in(convene: dict) -> list[tuple[str, str]]:
    """`(agent, datum)` for every bullet under `DATA I LACKED:`."""
    out: list[tuple[str, str]] = []
    for turn in convene.get("turns", []):
        block = re.search(
            r"DATA I LACKED:(.*?)(?=PROMPT CONTRADICTIONS:|$)",
            turn.get("answer") or "", re.S,
        )
        if not block:
            continue
        bullets = _BULLET.split(block.group(1))[1:]
        # A `**Datum:**` block nests `(a)`/`(b)`/`(c)` as sub-bullets of the
        # datum itself. Once any bullet in the turn is labelled, the labelled
        # ones are the complete list and the sub-bullets are their rationale —
        # counting those too would triple this turn's demand.
        labelled = [b for b in bullets if _DATUM_LABEL.match(b.strip())]
        for bullet in labelled or bullets:
            datum = _datum_of(bullet)
            if datum:
                out.append((turn["agent"], datum))
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


def arm(label: str, *, ticker: str, mandate: str, client: VLLMClient) -> dict:
    spec = ARMS[label]
    for flag in FLAGS:
        setattr(settings, flag, spec.get(flag, False))

    import run_convene as harness
    plain = harness.load_or_build
    if spec.get("fundamentals_fcf_from_statements_enabled"):
        harness.load_or_build = lambda *a, **k: _apply_def400(plain(*a, **k))
    try:
        convene = run_convene(
            ticker=ticker, mandate_label=mandate, client=client, profiles_dir=PROFILES,
        )
    finally:
        harness.load_or_build = plain
    convene["cr221_arm"] = label
    convene["cr221_flags"] = {f: getattr(settings, f) for f in FLAGS}
    return convene


_MIN_ANSWER_CHARS = 40


def is_complete(convene: dict) -> bool:
    """Every turn answered. A convene with dead turns must never be scored.

    The provider went down mid-round on 2026-09-03 and two whole convenes came
    back with twelve `Connection refused` turns each. Scored, they read as ZERO
    demand — a perfect extinction result produced by an outage. That is the
    CR040 silent-fallback shape landing on the measurement instead of on the
    product, and a run that cannot tell the two apart cannot be trusted about
    either.
    """
    turns = convene.get("turns") or []
    return bool(turns) and all(
        len((turn.get("answer") or "").strip()) >= _MIN_ANSWER_CHARS for turn in turns
    )


def _banked(args) -> dict[str, list[dict]]:
    """Convenes already on disk, keyed by arm — newest stamp wins per cell.

    Re-scoring is free — no model, no cost — and it has to stay free, because
    the scorer is the part of this rig most likely to need a correction after
    the fact. The first pilot's headline was wrong for exactly that reason
    (`_datum_of`), and re-running nine convenes to find out would have made
    fixing it a decision rather than an obligation.
    """
    out: dict[str, list[dict]] = {}
    for label in args.arms:
        for mandate in args.mandates:
            found = None
            for stamp in sorted(args.score_only, reverse=True):
                path = os.path.join(
                    args.out_root, f"{stamp}_{args.ticker}_{mandate}_{label}.json")
                if not os.path.exists(path):
                    continue
                with open(path) as fh:
                    convene = json.load(fh)
                if not is_complete(convene):
                    print(f"!! DEAD TURNS, skipped: {os.path.basename(path)}")
                    continue
                found = convene
                break
            if found is None:
                print(f"!! no complete convene for {mandate}/{label}")
                continue
            out.setdefault(label, []).append(found)
    return out


def report(convenes: dict[str, list[dict]], args, *, verbatim: bool) -> int:
    labels = [label for label in args.arms if convenes.get(label)]
    if not labels:
        print("!! nothing to report")
        return 1
    sizes = {label: len(convenes[label]) for label in labels}
    if len(set(sizes.values())) != 1:
        print(f"!! arms have unequal convene counts {sizes} — the totals row would "
              f"compare a sum over N convenes with a sum over M. Re-run the missing "
              f"cells, or pass only the mandates every arm completed.")
        return 1
    totals = {label: collections.Counter() for label in labels}
    agents = {label: collections.defaultdict(set) for label in labels}
    asks = {label: 0 for label in labels}
    for label in labels:
        for convene in convenes[label]:
            rows = requests_in(convene)
            asks[label] += len(rows)
            for agent, text in rows:
                for item in items.claims(text):
                    totals[label][item.id] += 1
                    agents[label][item.id].add(agent)

    n = len(convenes[labels[0]])
    width = 9
    print("\n" + "=" * 96)
    print(f"DEMAND EXTINCTION — {args.ticker} × {n} mandate(s), "
          f"{sum(len(v) for v in convenes.values())} convenes")
    print("=" * 96)
    print(f"{'item':5s}" + "".join(f"{label:>{width}s}" for label in labels) + "  label")
    print(f"{'TOTAL':5s}" + "".join(f"{asks[label]:>{width}d}" for label in labels)
          + "  every datum named, register-matched or not")
    print("-" * 96)
    for item_id in sorted(set().union(*(set(t) for t in totals.values()))):
        label = next((i.label for i in items.ITEMS if i.id == item_id), "?")
        owner = next((a for a, ids in ARM_ITEMS.items() if item_id in ids), None)
        marker = f"  <-- {owner} arm ships this, must fall" if owner else ""
        if item_id == NEGATIVE_CONTROL:
            marker = "  <-- negative control, must NOT fall"
        print(f"{item_id:5s}"
              + "".join(f"{totals[label_][item_id]:>{width}d}" for label_ in labels)
              + f"  {label[:40]}{marker}")

    if verbatim:
        for label in labels:
            print(f"\n--- {label} " + "-" * 80)
            for convene in convenes[label]:
                for agent, text in requests_in(convene):
                    claimed = ",".join(i.id for i in items.claims(text)) or "-"
                    print(f"  [{claimed:8s}][{agent[:19]:19s}] {text[:100]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ticker", default="CAT")
    ap.add_argument("--mandates", nargs="+", default=["long"])
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--out-root", default=RESULTS)
    ap.add_argument("--arms", nargs="+", default=list(ARMS),
                    choices=list(ARMS))
    ap.add_argument("--score-only", metavar="STAMP", nargs="+", default=None,
                    help="re-score banked convenes with these run stamps instead "
                         "of driving the model — no LLM calls, no cost. Several "
                         "stamps are searched newest-first per (mandate, arm), "
                         "which is how a re-run after an outage rejoins its round.")
    ap.add_argument("--verbatim", action="store_true",
                    help="with --score-only, print every datum named, by arm")
    args = ap.parse_args()

    if args.score_only:
        return report(_banked(args), args, verbatim=args.verbatim)

    os.makedirs(args.out_root, exist_ok=True)
    os.makedirs(PROFILES, exist_ok=True)
    client = AddendumClient(args.base_url)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    labels = args.arms
    convenes: dict[str, list[tuple[str, dict]]] = {label: [] for label in labels}

    for mandate in args.mandates:
        for label in labels:
            convene = arm(label, ticker=args.ticker, mandate=mandate, client=client)
            scored = score(convene)
            convene["cr221_scored"] = scored
            path = os.path.join(
                args.out_root, f"{stamp}_{args.ticker}_{mandate}_{label}.json")
            with open(path, "w") as fh:
                json.dump(convene, fh, indent=2, default=str)
            named = len(requests_in(convene))
            asks[label] += named
            print(f"  [{mandate}/{label}] {named} data items named "
                  f"-> {len(scored)} register items   {os.path.basename(path)}",
                  flush=True)
            convenes[label].append((mandate, convene))

    return report({label: [c for _, c in convenes[label]] for label in labels},
                  args, verbatim=False)


if __name__ == "__main__":
    sys.exit(main())
