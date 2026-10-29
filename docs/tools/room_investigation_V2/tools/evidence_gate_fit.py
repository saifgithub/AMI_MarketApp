#!/usr/bin/env python3
"""CR266 — fit the per-model evidence-gate threshold ladder.

Reads run JSONL + llm_audit CLAIMS/OBJECTIONS, computes THE SAME evidence
score as the backend contract (`backend/app/services/evidence_record.py`:
net_support = SUM(direction×grade contributions over data-present cards) / 20
(four desks × five required items — complete support scores exactly 1.0),
score = net_support − 0.1 × unresolved adequate objections — each objection
costs a MATERIAL 0.1, not 0.005), and fits ONE monotone
R1 ≥ R2 ≥ R3 ≥ R4 ≥ R5 threshold ladder per model targeting the locked CR256
approval curve 5/15/30/45/46 per 60 rooms (R5 re-anchored 60 → 46,
investable universe, 2026-10-13). Emits provider-specific threshold JSON in
the exact shape `ROOM_EVIDENCE_GATE_THRESHOLDS_JSON` parses.

Honesty constraints, load-bearing:

  * In-sample quantile fitting reproduces ANY curve trivially (review M5 in
    evidence_bar.py) — the headline number is the SPLIT read: thresholds fit
    on `--fit-rep` rooms, achieved approvals reported on the OTHER reps.
    Curve-matching is NOT evidence the gate is correct; it only sets the bar.
  * Thresholds are fit per model and keyed by the single `--provider` given.
    NEVER reuse one model's ladder for another — discrimination differs by
    provider and an imported bar is an unmeasured gate.
  * Fit on the CALIBRATION corpus only. Do not fit against acceptance/test
    rooms; acceptance is a fresh-run evaluation, a separate step.
  * The 7-name holdout set (APD BA FCEL RIOT RIVN SNAP SPCE) is excluded from
    the approval set at every level BEFORE ranking — the RIOT-shaped
    falsifier: a fitted bar any holdout clears at its level fails validation.
  * Legacy corpora without `verdict.sheet_state` cannot decide data presence
    the way the backend does (registry liveness, never LLM self-report). The
    data-absent branch falls back to the cards' own `data=yes/no` flag,
    LABELLED AS AN APPROXIMATION in the report, and the fit must be re-run
    once sheet_state persists. An in-range, monotone ladder produced under
    the approximation is provisional.
  * A level that cannot be fit (empty scores, or a quantile outside [0,1],
    the range `parse_gate_thresholds` accepts) is reported and OMITTED from
    the gate JSON — never clamped, never guessed (CR040). A provider with any
    omitted level stays OFF.

Usage:
  python3 evidence_gate_fit.py --provider ami-llm \
      --runs ../out/cr266-calibration/runs_all.jsonl \
      --turns-file ../out/cr266-calibration/repaired.jsonl \
      --out-dir ../out/evidence_gate_fit_ami
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# The pilot-validated card grammar (tools/cards_run.py) — same regexes the
# harness composite and the runner's parser use, so a card read here is the
# card the backend would read.
from cards_run import (  # noqa: E402
    CLAIMS_BLOCK, OBJ_BLOCK, CARD_LINE, OBJ_LINE, DESKS, ITEMS,
)

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "docs/tools/room_investigation_V2/out"

# ── Backend contract mirrors (evidence_record.py) ───────────────────────────
# Byte-parity constants: the fit score must be the score the gate will compute
# in production, or the ladder is fit against a different quantity than it
# gates. If the backend contract changes, these must change with it.
REQUIRED_DESKS: tuple[str, ...] = (
    "fundamentals_analyst", "bull_researcher", "bear_researcher",
    "research_manager",
)
ITEM_FIELD_REGISTRY: dict[str, tuple[str, ...]] = {
    "eq": ("free_cash_flow", "sbc", "net_cash"),
    "vc": ("roic", "wacc"),
    "vh": ("pe", "forward_pe", "ev_to_ebitda", "peg_ratio", "price_to_sales"),
    "bs": (
        "total_debt", "net_cash", "interest_coverage", "debt_maturity",
        "current_ratio", "quick_ratio", "debt_to_equity",
    ),
    "moat": ("gross_margin", "operating_margin", "rev_growth", "profit_margin"),
}
_DIRECTION_WEIGHT = {"support": 1.0, "oppose": -1.0, "neutral": 0.0}
_GRADE_WEIGHT = {"well": 1.0, "partial": 0.5, "unsupported": 0.0}
ADEQUATE_SEVERITIES = frozenset({"high", "medium"})
UNRESOLVED_PENALTY = 0.1

# Normalized net support divides by the full census size (four required desks
# x five required items = 20), never by the cards actually filed: a thin or
# partial filing can never reach 1.0 by inflation, and complete support is
# exactly 1.0.
NET_SUPPORT_NORMALIZER = len(REQUIRED_DESKS) * len(ITEM_FIELD_REGISTRY)  # 20

# CR256 locked curve (R5 amended 60 -> 46, 2026-10-13): approvals per 60 rooms.
TARGET = {1: 5, 2: 15, 3: 30, 4: 45, 5: 46}
HOLDOUTS = ("APD", "BA", "FCEL", "RIOT", "RIVN", "SNAP", "SPCE")
RISK_LEVELS = ("R1", "R2", "R3", "R4", "R5")

CAVEATS = (
    "In-sample quantile fit reproduces any curve trivially — read the "
    "split-fit line (thresholds from --fit-rep, approvals on the other reps), "
    "not the in-sample one. Curve-matching is NOT evidence the gate is "
    "correct.",
    "Thresholds are provider-specific. Never reuse this ladder for another "
    "model.",
    "Fit on the calibration corpus only; do not fit against acceptance/test "
    "rooms. Acceptance is a separate fresh-run evaluation.",
    "Targets are the locked policy curve (5/15/30/45/46 per 60 rooms), not a "
    "market-derived optimum.",
)


class FitError(ValueError):
    """The corpus cannot support a fit (empty scores, no provider, bad
    shape). Loud, never a guessed ladder."""


@dataclass(frozen=True)
class RoomScore:
    ticker: str
    level: int
    rep: str
    score: float | None          # None when evidence was incomplete
    net_support: float | None
    unresolved: int | None
    evidence_available: bool
    missing: tuple[str, ...]
    holdout: bool
    field_state_source: str      # "sheet_state" | "card_self_report"


# ── Parsing (cards_run grammar + backend data-flag validation) ──────────────

def parse_room_turns(turns: list[dict]) -> dict:
    """Cards + objections out of one room's desk turns.

    Unlike the cards_run pilot composite, objections are read from ALL four
    evidence desks — the backend contract lets any desk file an adequate
    objection. The `data` flag is validated to yes/no here (backend
    `_CARD_DATA_FLAGS`); anything else drops the card, counted, never guessed.
    """
    cards: list[dict] = []
    objections: list[dict] = []
    malformed_cards = 0
    malformed_objections = 0
    data_flag_unrecognised = 0
    for t in turns:
        desk = t.get("agent_id")
        if desk not in DESKS:
            continue
        text = t.get("response_text") or ""
        cm = CLAIMS_BLOCK.search(text)
        if cm:
            for line in cm.group(1).strip().splitlines():
                line = line.strip().lstrip("-*").strip()
                if not line:
                    continue
                m = CARD_LINE.match(line)
                if (not m or m.group(1).lower() not in ITEMS
                        or m.group(2).lower() not in _DIRECTION_WEIGHT
                        or m.group(3).lower() not in _GRADE_WEIGHT):
                    malformed_cards += 1
                    continue
                data = m.group(4).lower()
                if data not in ("yes", "no"):
                    data_flag_unrecognised += 1
                    malformed_cards += 1
                    continue
                cards.append({
                    "desk": desk, "item": m.group(1).lower(),
                    "direction": m.group(2).lower(), "grade": m.group(3).lower(),
                    "data": data,
                })
        om = OBJ_BLOCK.search(text)
        if om:
            for line in om.group(1).strip().splitlines():
                line = line.strip().lstrip("-*").strip()
                if not line:
                    continue
                m = OBJ_LINE.match(line)
                if not m or m.group(1).lower() not in ITEMS:
                    malformed_objections += 1
                    continue
                objections.append({
                    "desk": desk, "target": m.group(1).lower(),
                    "severity": m.group(2).lower(),
                })
    return {
        "cards": cards, "objections": objections,
        "malformed_cards": malformed_cards,
        "malformed_objections": malformed_objections,
        "data_flag_unrecognised": data_flag_unrecognised,
    }


# ── Scoring (backend build_evidence_record parity) ──────────────────────────

def _data_present_from_sheet(item: str, sheet_state: dict[str, str]) -> bool:
    """The backend `_live` test: a registry field whose value is exactly
    'live' (case-insensitive). Nothing else counts."""
    return any(str(sheet_state.get(n, "")).lower() == "live"
               for n in ITEM_FIELD_REGISTRY[item])


def score_room(
    parsed: dict,
    field_state: dict[str, str] | None,
) -> dict:
    """The backend contract score for one room.

    With `field_state` (the run's `verdict.sheet_state`) data presence is the
    registry-liveness read, exactly as the backend computes it. Without it —
    the data-absent branch — presence falls back to ANY card on the item
    self-reporting `data=yes`. That is the approximation the backend refuses
    at gate time; here it is allowed for fitting legacy corpora but LABELLED
    in the returned `field_state_source` and the fit report.

    The contract is exactly the 20 desk/item cells (4 desks x 5 items), one
    card each: a duplicate makes the room's evidence unavailable with an
    explicit `duplicate:<desk>:<item>` marker, and a gap makes it unavailable
    with `missing:<desk>:<item>` — a desk that files only eq is NOT complete
    just because other desks cover the other items. A wholly absent desk
    keeps the established `cards:<desk>` marker (its five cells implicitly).
    net_support is normalized by the full 20-cell census (complete support =
    1.0); the raw sum is kept only as a diagnostic.
    """
    cards = parsed["cards"]
    objections = parsed["objections"]
    by_desk: dict[str, list[dict]] = {d: [] for d in REQUIRED_DESKS}
    for c in cards:
        if c["desk"] in by_desk:
            by_desk[c["desk"]].append(c)

    if field_state is not None:
        data_present = {item: _data_present_from_sheet(item, field_state)
                        for item in ITEMS}
        source = "sheet_state"
        # Backend parity: presence is per ITEM; the card's own data flag is
        # ignored (it is a claim, not a measurement).
        card_present = lambda c: data_present[c["item"]]
    else:
        data_present = {
            item: any(c["data"] == "yes" for c in cards if c["item"] == item)
            for item in ITEMS
        }
        source = "card_self_report"
        # Approximation: a desk that self-reports data=no cannot back its own
        # card — zero THAT card (the backend zeroes the whole item instead;
        # per-card is the conservative reading of the same absence).
        card_present = lambda c: data_present[c["item"]] and c["data"] == "yes"

    missing: list[str] = []
    items_out: list[dict] = []
    cards_per_item: dict[str, list[dict]] = {i: [] for i in ITEMS}
    seen_desk_item: set[tuple[str, str]] = set()
    for desk in REQUIRED_DESKS:
        desk_cards = by_desk[desk]
        if not desk_cards:
            missing.append(f"cards:{desk}")
            continue
        for c in desk_cards:
            key = (c["desk"], c["item"])
            if key in seen_desk_item:
                missing.append(f"duplicate:{c['desk']}:{c['item']}")
                continue
            seen_desk_item.add(key)
            present = card_present(c)
            contribution = (_DIRECTION_WEIGHT[c["direction"]]
                            * _GRADE_WEIGHT[c["grade"]] if present else 0.0)
            out = dict(c, data_present=present, contribution=contribution)
            items_out.append(out)
            cards_per_item[c["item"]].append(out)
    # Exact-20-cell contract: a desk that filed anything must file exactly
    # one card on EVERY item — a single gap marks the room unavailable,
    # explicitly, per cell.
    for desk in REQUIRED_DESKS:
        if not by_desk[desk]:
            continue  # wholly absent desk already marked cards:<desk>
        for item in ITEMS:
            if (desk, item) not in seen_desk_item:
                missing.append(f"missing:{desk}:{item}")

    raw_net_support = round(sum(c["contribution"] for c in items_out), 6)
    net_support = round(raw_net_support / NET_SUPPORT_NORMALIZER, 6)

    by_desk_dir = {(c["desk"], c["item"]): c["direction"]
                   for c in items_out if c["data_present"]}
    unresolved: list[str] = []
    seen: dict[tuple[str, str], int] = {}
    objections_out: list[dict] = []
    for desk in REQUIRED_DESKS:
        for obj in (o for o in objections if o["desk"] == desk):
            target = obj["target"]
            if target not in cards_per_item:
                continue
            seen[(desk, target)] = seen.get((desk, target), 0) + 1
            oid = f"{desk}:{target}:{seen[(desk, target)] - 1}"
            adequate = obj["severity"] in ADEQUATE_SEVERITIES
            own_dir = by_desk_dir.get((desk, target))
            resolved = False
            if adequate:
                for ev in cards_per_item[target]:
                    if ev["desk"] == desk or not ev["data_present"]:
                        continue
                    if _GRADE_WEIGHT[ev["grade"]] <= 0:
                        continue
                    if own_dir is None or ev["direction"] != own_dir:
                        resolved = True
                        break
            if adequate and not resolved:
                unresolved.append(oid)
            objections_out.append(dict(obj, id=oid, adequate=adequate,
                                       resolved=resolved))

    evidence_available = not missing
    score = (round(net_support - UNRESOLVED_PENALTY * len(unresolved), 6)
             if evidence_available else None)
    return {
        "score": score, "net_support": net_support if evidence_available else None,
        "raw_net_support": raw_net_support,
        "unresolved": len(unresolved) if evidence_available else None,
        "unresolved_ids": tuple(unresolved),
        "evidence_available": evidence_available,
        "missing": tuple(missing),
        "field_state_source": source,
        "items": items_out, "objections": objections_out,
    }


# ── Fit ─────────────────────────────────────────────────────────────────────

def fit_ladder(
    rooms: list[RoomScore],
    targets: dict[int, int] | None = None,
    fit_rep: str = "1",
) -> dict:
    """One monotone R1 ≥ … ≥ R5 ladder over the corpus.

    SPLIT-FIT (review M5 — in-sample quantile fitting reproduces any curve
    trivially): thresholds rank ONLY `fit_rep` rooms; achieved approvals are
    reported per rep so the non-fit reps are the honest out-of-sample read.
    Per level the threshold is the score at rank `target` among eligible
    (scored, non-holdout) fit rooms — holdouts are excluded from the approval
    set BEFORE ranking. Raw per-level quantiles are then walked R4→R1 to force
    the single monotone ladder the backend config requires; achieved approvals
    are recomputed on the enforced ladder, never reported against the raw one.
    """
    targets = targets or TARGET
    if not any(r.score is not None for r in rooms):
        raise FitError("no scored rooms in corpus — nothing to fit against")

    raw: dict[int, float] = {}
    eligible_n: dict[int, int] = {}
    unscorable_n: dict[int, int] = {}
    for lvl in range(1, 6):
        eligible = sorted((r.score for r in rooms
                           if r.level == lvl and r.rep == fit_rep
                           and not r.holdout and r.score is not None),
                          reverse=True)
        eligible_n[lvl] = len(eligible)
        unscorable_n[lvl] = sum(1 for r in rooms
                                if r.level == lvl and r.score is None)
        if not eligible:
            raise FitError(
                f"R{lvl}: no eligible scored rooms on fit rep {fit_rep!r} — "
                "cannot fit a threshold from an empty score list (never guessed)"
            )
        k = max(1, min(targets[lvl], len(eligible)))
        raw[lvl] = eligible[k - 1]

    enforced = dict(raw)
    for lvl in (4, 3, 2, 1):
        if enforced[lvl] < enforced[lvl + 1]:
            enforced[lvl] = enforced[lvl + 1]

    ladder = {f"R{l}": round(enforced[l], 6) for l in range(1, 6)}
    vals = [ladder[k] for k in RISK_LEVELS]
    if any(a < b for a, b in zip(vals, vals[1:])):
        raise FitError(f"enforced ladder not monotone: {ladder}")

    achieved = {
        str(rep): {
            f"R{l}": sum(1 for r in rooms if r.level == l and r.rep == str(rep)
                         and not r.holdout and r.score is not None
                         and r.score >= ladder[f"R{l}"])
            for l in range(1, 6)
        }
        for rep in sorted({r.rep for r in rooms})
    }
    holdout_above: dict[str, dict[str, bool]] = {h: {} for h in HOLDOUTS}
    for r in rooms:
        if r.holdout and r.score is not None:
            key = f"R{r.level}"
            above = r.score >= ladder[key]
            holdout_above[r.ticker][key] = (
                holdout_above[r.ticker].get(key, False) or above
            )
    return {
        "raw_thresholds": {f"R{l}": round(raw[l], 6) for l in range(1, 6)},
        "thresholds": ladder,
        "eligible_fit_rooms": {f"R{l}": eligible_n[l] for l in range(1, 6)},
        "unscorable_rooms": {f"R{l}": unscorable_n[l] for l in range(1, 6)},
        "achieved_approvals_by_rep": achieved,
        "holdout_at_or_above_bar": holdout_above,
        "raw_non_monotone": raw != enforced,
    }


def holdout_leaks(fit_result: dict) -> dict[str, list[str]]:
    """The RIOT-shaped falsifier: a fitted bar any holdout clears at any
    level is a failed fit, reported by ticker and level."""
    return {
        ticker: [lvl for lvl, above in levels.items() if above]
        for ticker, levels in fit_result["holdout_at_or_above_bar"].items()
        if any(levels.values())
    }


def validate_for_gate(ladder: dict[str, float]) -> list[str]:
    """The checks `parse_gate_thresholds` will apply at boot, run HERE so a
    bad ladder is caught at fit time, not at deploy. Out-of-range levels are
    reported, never clamped."""
    errors: list[str] = []
    vals = [ladder[k] for k in RISK_LEVELS]
    for k, v in zip(RISK_LEVELS, vals):
        if not 0.0 <= v <= 1.0:
            errors.append(f"{k}={v} outside [0, 1] — backend would reject boot")
    if any(a < b for a, b in zip(vals, vals[1:])):
        errors.append(f"not monotone {'>='.join(RISK_LEVELS)}: {vals}")
    return errors


def gate_json(provider: str, ladder: dict[str, float]) -> dict[str, dict[str, float]]:
    """The ROOM_EVIDENCE_GATE_THRESHOLDS_JSON shape for ONE provider."""
    return {provider: {k: ladder[k] for k in RISK_LEVELS}}


# ── IO ──────────────────────────────────────────────────────────────────────

def _room_identity(row: dict) -> tuple[str, str]:
    """(ticker, rep) from the row's AUTHORITATIVE fields.

    Ticker NEVER comes from arm_key: current arm keys are shaped
    `RIOT-r4-rep1`, so an arm_key split yields `RIOT-r4` — which silently
    breaks holdout exclusion and per-ticker grouping. Rep uses the row's rep
    field when present, else the `-rep<i>` arm_key suffix; a row with neither
    is a loud error, never a guessed grouping.
    """
    ticker = str(row["ticker"]).upper().strip()
    rep = row.get("rep")
    if rep is None:
        arm_key = str(row.get("arm_key") or "")
        if "-rep" not in arm_key:
            raise FitError(
                f"row for {ticker}: no rep field and arm_key {arm_key!r} "
                "has no '-rep' suffix — cannot group reps"
            )
        rep = arm_key.rsplit("-rep", 1)[1]
    return ticker, str(rep)


def _room_record_from_arm(arm: dict, turns: list[dict]) -> dict:
    verdict = arm.get("verdict") or {}
    ticker, rep = _room_identity(arm)
    return {
        "ticker": ticker, "rep": rep,
        "risk_score": int(arm["risk_score"]),
        "turns": turns,
        "sheet_state": verdict.get("sheet_state"),
        "verdict_action": verdict.get("action"),
    }


def _load_turns_file(path: Path) -> list[dict]:
    """cards_repair.py output: one record per room with its desk turns."""
    out = []
    for line in open(path):
        rec = json.loads(line)
        ticker, rep = _room_identity(rec)
        out.append({
            "ticker": ticker, "rep": rep,
            "risk_score": int(rec["risk_score"]),
            "turns": rec["turns"],
            "sheet_state": rec.get("sheet_state"),
            "verdict_action": rec.get("verdict"),
        })
    return out


def _load_runs_with_dsn(runs_path: Path, dsn: str) -> list[dict]:
    """Run rows joined with llm_audit turns, mirroring cards_run.fetch_turns."""
    from cards_run import fetch_turns

    arms = [json.loads(l) for l in open(runs_path)]
    out = []
    for arm in arms:
        if arm.get("status") != "completed":
            continue
        out.append(_room_record_from_arm(arm, fetch_turns(dsn, arm)))
    return out


def score_corpus(records: list[dict]) -> tuple[list[RoomScore], dict]:
    rooms: list[RoomScore] = []
    tally: collections.Counter = collections.Counter({
        "rooms_bad_level": 0, "malformed_cards": 0,
        "malformed_objections": 0, "data_flag_unrecognised": 0,
        "rooms_evidence_unavailable": 0, "rooms_duplicate_cards": 0,
        "field_state_source:sheet_state": 0,
        "field_state_source:card_self_report": 0,
    })
    for rec in records:
        level = int(rec.get("risk_score") or 0)
        if level not in range(1, 6):
            tally["rooms_bad_level"] += 1
            continue
        parsed = parse_room_turns(rec["turns"])
        tally["malformed_cards"] += parsed["malformed_cards"]
        tally["malformed_objections"] += parsed["malformed_objections"]
        tally["data_flag_unrecognised"] += parsed["data_flag_unrecognised"]
        scored = score_room(parsed, rec.get("sheet_state"))
        tally[f"field_state_source:{scored['field_state_source']}"] += 1
        if not scored["evidence_available"]:
            tally["rooms_evidence_unavailable"] += 1
        tally["rooms_duplicate_cards"] += sum(
            1 for m in scored["missing"] if m.startswith("duplicate:"))
        rooms.append(RoomScore(
            ticker=rec["ticker"].upper(),
            level=level,
            rep=str(rec["rep"]),
            score=scored["score"],
            net_support=scored["net_support"],
            unresolved=scored["unresolved"],
            evidence_available=scored["evidence_available"],
            missing=scored["missing"],
            holdout=rec["ticker"].upper() in HOLDOUTS,
            field_state_source=scored["field_state_source"],
        ))
    return rooms, dict(tally)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True,
                    help="model/provider key for the ladder — one invocation "
                         "per model; never reuse a ladder across models")
    ap.add_argument("--runs", default=None, help="runs_<bench>.jsonl (DB fetch mode)")
    ap.add_argument("--turns-file", default=None,
                    help="cards_repair.py output (no DB needed)")
    ap.add_argument("--dsn", default=None, help="DATABASE_URL fallback for DB mode")
    ap.add_argument("--fit-rep", default="1",
                    help="rep whose rooms fit the thresholds; other reps give "
                         "the honest out-of-sample read")
    ap.add_argument("--out-dir", default=str(OUT / "evidence_gate_fit"))
    args = ap.parse_args()

    if not args.turns_file and not (args.runs and args.dsn):
        raise SystemExit("either --turns-file or (--runs + --dsn) required")

    records = (_load_turns_file(Path(args.turns_file)) if args.turns_file
               else _load_runs_with_dsn(Path(args.runs), args.dsn))
    if not records:
        raise SystemExit("no rooms loaded — nothing to fit")

    rooms, tally = score_corpus(records)
    if not rooms:
        raise SystemExit("no rooms carried a risk level R1..R5 — check the corpus")

    try:
        fit = fit_ladder(rooms, fit_rep=args.fit_rep)
    except FitError as exc:
        print(f"fit failed for {args.provider}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    errors = validate_for_gate(fit["thresholds"])
    leaks = holdout_leaks(fit)
    for ticker, levels in sorted(leaks.items()):
        errors.append(
            f"holdout {ticker} at/above the fitted bar at {levels} — "
            "holdouts must stay out at every level (falsifier)"
        )

    od = Path(args.out_dir)
    od.mkdir(parents=True, exist_ok=True)
    report = {
        "provider": args.provider,
        "targets_per_60": TARGET,
        "holdouts": list(HOLDOUTS),
        "fit_rep": args.fit_rep,
        "rooms": len(rooms),
        "tally": tally,
        **fit,
        "gate_validation_errors": errors,
        "caveats": list(CAVEATS),
    }
    (od / f"fit_report_{args.provider}.json").write_text(
        json.dumps(report, indent=2))

    if errors:
        print(f"NOT emitting gate thresholds for {args.provider}: {errors}",
              file=sys.stderr)
        print(f"report: {od / f'fit_report_{args.provider}.json'}")
        raise SystemExit(1)

    gate_path = od / f"thresholds_{args.provider}.json"
    gate_path.write_text(json.dumps(gate_json(args.provider, fit["thresholds"]),
                                    indent=2))
    achieved = report["achieved_approvals_by_rep"]
    print(f"thresholds {args.provider}: {fit['thresholds']}")
    print(f"achieved approvals by rep: {achieved}")
    print(f"holdout at/above bar: {leaks or 'none'}")
    print(f"written: {gate_path} + fit_report_{args.provider}.json")


if __name__ == "__main__":
    main()
