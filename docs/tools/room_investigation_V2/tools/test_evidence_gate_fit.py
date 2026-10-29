#!/usr/bin/env python3
"""CR266 — tests for evidence_gate_fit.py (stdlib unittest, no DB).

Pins the three things that make the fitted ladder trustworthy:

  1. SCORE PARITY with the backend contract (`app.services.evidence_record`):
     the fit score is the quantity the production gate will compute. A parity
     test runs the real backend `build_evidence_record` on duck-typed card
     channels and asserts byte-equal net_support / unresolved / score. It
     skips when the backend cannot be imported (e.g. running outside the
     backend venv) — the hand-computed expectations below still pin the
     semantics.
  2. FIT HONESTY: holdouts excluded from the approval set before ranking,
     empty scores fail loudly (never a guessed ladder), the enforced ladder
     is monotone, out-of-range levels are reported and omitted from the gate
     JSON — never clamped.
  3. FRAMING: provider-specific output keyed by exactly one provider, and the
     data-absent branch (no sheet_state) is labelled card_self_report, never
     presented as registry liveness.

Run from anywhere:
    python3 -m unittest test_evidence_gate_fit   # inside tools/
    python3 tools/test_evidence_gate_fit.py      # from room_investigation_V2/
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import evidence_gate_fit as fit


def _turn(agent_id: str, text: str) -> dict:
    return {"agent_id": agent_id, "response_text": text}


def _claims(cards: list[str], objections: list[str] | None = None) -> str:
    body = "[CLAIMS]\n" + "\n".join(cards) + "\n[/CLAIMS]"
    if objections:
        body += "\n[OBJECTIONS]\n" + "\n".join(objections) + "\n[/OBJECTIONS]"
    return body


def _full_room_cards() -> dict:
    """One card per desk per item, all well/support, data=yes — a complete,
    fully-evidenced room (net support = 4 desks x 5 items = 20.0 with all
    data present)."""
    lines = [f"item={i} dir=support grade=well data=yes claim=x nums=1"
             for i in fit.ITEM_FIELD_REGISTRY]
    return {d: _claims(lines) for d in fit.REQUIRED_DESKS}


class ScoreContractTests(unittest.TestCase):
    def _scored(self, cards_by_desk, field_state):
        turns = [_turn(d, t) for d, t in cards_by_desk.items()]
        parsed = fit.parse_room_turns(turns)
        return fit.score_room(parsed, field_state)

    def test_complete_room_all_data_live(self) -> None:
        state = {f: "live" for fields in fit.ITEM_FIELD_REGISTRY.values()
                 for f in fields}
        out = self._scored(_full_room_cards(), state)
        self.assertTrue(out["evidence_available"])
        self.assertEqual(out["net_support"], 20.0)
        self.assertEqual(out["unresolved"], 0)
        self.assertEqual(out["score"], 20.0)
        self.assertEqual(out["field_state_source"], "sheet_state")

    def test_absent_data_zeroes_contribution_both_directions(self) -> None:
        # bs has no live field (its registry fields removed outright — some
        # are shared with other items): an oppose/well card on it contributes
        # 0 exactly like a support/well one would — absence is neutral, never
        # silently bearish (backend contract).
        live = {f for item, fields in fit.ITEM_FIELD_REGISTRY.items()
                if item != "bs" for f in fields}
        live -= set(fit.ITEM_FIELD_REGISTRY["bs"])
        state = {f: "live" for f in live}
        cards = _full_room_cards()
        cards["bear_researcher"] = cards["bear_researcher"].replace(
            "item=bs dir=support", "item=bs dir=oppose")
        out = self._scored(cards, state)
        # all four desks' bs cards contribute 0 (4 x 1.0 absent), and the
        # bearish one is 0 rather than -1.0: absence is neutral in BOTH
        # directions, never silently bearish (backend contract).
        self.assertEqual(out["net_support"], 16.0)
        # the bs card is still parsed; it just cannot carry weight
        bs = [c for c in out["items"] if c["item"] == "bs"
              and c["desk"] == "bear_researcher"]
        self.assertEqual(len(bs), 1)
        self.assertFalse(bs[0]["data_present"])
        self.assertEqual(bs[0]["contribution"], 0.0)

    def test_objection_resolution_semantics(self) -> None:
        def full(eq_lines: list[str], objections: list[str] | None = None):
            return _claims(eq_lines + [f"item={i} dir=support grade=well "
                                       f"data=yes claim=x"
                                       for i in ("vc", "vh", "bs", "moat")],
                           objections)

        # bear files an adequate objection on eq; bull's opposing well card
        # resolves it; a desk's OWN card cannot; low severity never binds.
        cards = {
            "fundamentals_analyst": full(
                ["item=eq dir=support grade=well data=yes claim=x"]),
            "bull_researcher": full(
                ["item=eq dir=support grade=well data=yes claim=x"]),
            "bear_researcher": full(
                ["item=eq dir=oppose grade=well data=yes claim=x"],
                ["target=eq severity=high objection=y"]),
            "research_manager": full(
                ["item=eq dir=support grade=well data=yes claim=x"],
                ["target=eq severity=low objection=z"]),
        }
        state = {f: "live" for fields in fit.ITEM_FIELD_REGISTRY.values()
                 for f in fields}
        out = self._scored(cards, state)
        # high objection: resolved by bull (other desk, data-present, well,
        # direction != bear's own 'oppose'). low objection: never counts.
        self.assertEqual(out["unresolved"], 0)
        # now remove the bull card — bear's own card must NOT resolve it
        cards2 = dict(cards)
        cards2["bull_researcher"] = _claims([])
        out2 = self._scored(cards2, state)
        self.assertFalse(out2["evidence_available"])  # bull filed nothing
        # unresolved needs NO other desk's positive-grade data-present card
        # on eq at all: fundamentals/bull grade eq unsupported, rm stays off
        # eq, bear keeps an oppose/well card (its own cannot resolve).
        cards3 = {
            "fundamentals_analyst": full(
                ["item=eq dir=support grade=unsupported data=yes claim=x"]),
            "bull_researcher": full(
                ["item=eq dir=support grade=unsupported data=yes claim=x"]),
            "bear_researcher": full(
                ["item=eq dir=oppose grade=well data=yes claim=x"],
                ["target=eq severity=high objection=y"]),
            "research_manager": _claims(
                [f"item={i} dir=support grade=well data=yes claim=x"
                 for i in ("vc", "vh", "bs", "moat")]),
        }
        out3 = self._scored(cards3, state)
        self.assertTrue(out3["evidence_available"])
        self.assertEqual(out3["unresolved"], 1)
        self.assertEqual(out3["score"], round(out3["net_support"] - 0.1, 6))

    def test_missing_desk_makes_room_unscorable(self) -> None:
        cards = _full_room_cards()
        del cards["research_manager"]
        out = self._scored(cards, {"free_cash_flow": "live"})
        self.assertFalse(out["evidence_available"])
        self.assertIsNone(out["score"])
        self.assertIn("cards:research_manager", out["missing"])

    def test_data_absent_branch_uses_self_report_and_is_labelled(self) -> None:
        out = self._scored(_full_room_cards(), None)
        self.assertEqual(out["field_state_source"], "card_self_report")
        self.assertEqual(out["net_support"], 20.0)
        # self-report data=no zeroes the contribution under the approximation
        cards = _full_room_cards()
        cards["bull_researcher"] = cards["bull_researcher"].replace(
            "item=eq dir=support grade=well data=yes",
            "item=eq dir=support grade=well data=no")
        out2 = self._scored(cards, None)
        self.assertEqual(out2["net_support"], 19.0)

    def test_bad_data_flag_drops_card_counted(self) -> None:
        cards = _full_room_cards()
        cards["bull_researcher"] = cards["bull_researcher"].replace(
            "item=eq dir=support grade=well data=yes",
            "item=eq dir=support grade=well data=maybe")
        parsed = fit.parse_room_turns(
            [_turn(d, t) for d, t in cards.items()])
        self.assertEqual(parsed["malformed_cards"], 1)
        self.assertEqual(parsed["data_flag_unrecognised"], 1)


class BackendParityTests(unittest.TestCase):
    def test_score_matches_backend_build_evidence_record(self) -> None:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parents[4]
                                   / "backend"))
            from dataclasses import dataclass
            from app.services.evidence_record import build_evidence_record
        except Exception:
            self.skipTest("backend app not importable in this environment")

        @dataclass(frozen=True)
        class Card:
            item: str
            direction: str
            grade: str
            data: str = "yes"
            claim: str = "x"
            nums: str | None = None

        @dataclass(frozen=True)
        class Obj:
            target: str
            severity: str
            objection: str = "y"

        @dataclass(frozen=True)
        class Channel:
            cards: tuple
            objections: tuple

        cards_by_desk = {}
        turns = []
        for desk in fit.REQUIRED_DESKS:
            cl = [Card(item=i, direction="support", grade="well")
                  for i in fit.ITEM_FIELD_REGISTRY]
            ol = [Obj(target="eq", severity="high")] if desk == "bear_researcher" \
                else ([Obj(target="vc", severity="low")] if desk == "research_manager" else [])
            cards_by_desk[desk] = Channel(cards=tuple(cl), objections=tuple(ol))
            lines = [f"item={c.item} dir={c.direction} grade={c.grade} "
                     f"data={c.data} claim={c.claim}" for c in cl]
            turns.append(_turn(desk, _claims(lines, [f"target={o.target} "
                     f"severity={o.severity} objection={o.objection}" for o in ol])))
        state = {f: "live" for fields in fit.ITEM_FIELD_REGISTRY.values()
                 for f in fields}
        rec = build_evidence_record(cards_by_desk, state)

        parsed = fit.parse_room_turns(turns)
        ours = fit.score_room(parsed, state)
        self.assertEqual(ours["net_support"], rec.net_support)
        self.assertEqual(ours["unresolved"], rec.unresolved_objection_count)
        self.assertEqual(ours["score"], rec.score)

        # and under the data-absent branch the approximation must be labelled
        ours_none = fit.score_room(parsed, None)
        self.assertEqual(ours_none["field_state_source"], "card_self_report")


class FitTests(unittest.TestCase):
    def _corpus(self, per_level: int = 16, reps=("1", "2")):
        """Tickers x reps x 5 levels with deterministic descending scores per
        level, one shared scale across levels (tiny per-level drift keeps the
        raw quantiles naturally monotone), so each level's quantile lands
        exactly on target where the target does not exceed the room count."""
        rooms = []
        for lvl in range(1, 6):
            for i in range(per_level):
                ticker = f"T{lvl}{i:02d}"
                for rep in reps:
                    rooms.append(fit.RoomScore(
                        ticker=ticker, level=lvl, rep=rep,
                        score=1.0 - i / 100.0 - (lvl - 1) * 0.0001,
                        net_support=None, unresolved=None,
                        evidence_available=True, missing=(),
                        holdout=False, field_state_source="sheet_state",
                    ))
        return rooms

    def test_hits_target_curve_in_sample_on_fit_rep(self) -> None:
        rooms = self._corpus()
        out = fit.fit_ladder(rooms, fit_rep="1")
        # 16 fit rooms per level: R1 k=5, R2 k=15 land exactly; R3..R5 targets
        # (30/45/46) exceed 16 rooms, so k = 16 → the whole level approves.
        self.assertEqual(out["achieved_approvals_by_rep"]["1"]["R1"], 5)
        self.assertEqual(out["achieved_approvals_by_rep"]["1"]["R2"], 15)
        self.assertEqual(out["achieved_approvals_by_rep"]["1"]["R3"], 16)
        vals = [out["thresholds"][k] for k in fit.RISK_LEVELS]
        self.assertTrue(all(a >= b for a, b in zip(vals, vals[1:])))
        self.assertFalse(out["raw_non_monotone"])

    def test_holdouts_excluded_from_ranking_and_leaks_surfaced(self) -> None:
        rooms = self._corpus()
        # a holdout with the TOP score at every level: excluded from the
        # approval set, and the leak is surfaced by the falsifier, never
        # hidden.
        for lvl in range(1, 6):
            for rep in ("1", "2"):
                rooms.append(fit.RoomScore(
                    ticker="RIOT", level=lvl, rep=rep,
                    score=999.0, net_support=None, unresolved=None,
                    evidence_available=True, missing=(),
                    holdout=True, field_state_source="sheet_state",
                ))
        out = fit.fit_ladder(rooms, fit_rep="1")
        self.assertEqual(fit.holdout_leaks(out),
                         {"RIOT": [f"R{l}" for l in range(1, 6)]})
        for rep in out["achieved_approvals_by_rep"]:
            # RIOT adds zero approvals at every level
            self.assertEqual(out["achieved_approvals_by_rep"][rep]["R1"], 5)
        # below the bar → no leak
        rooms2 = self._corpus()
        for lvl in range(1, 6):
            rooms2.append(fit.RoomScore(
                ticker="RIOT", level=lvl, rep="1",
                score=-5.0, net_support=None, unresolved=None,
                evidence_available=True, missing=(),
                holdout=True, field_state_source="sheet_state",
            ))
        self.assertEqual(fit.holdout_leaks(fit.fit_ladder(rooms2, fit_rep="1")), {})

    def test_empty_scores_fail_loudly(self) -> None:
        rooms = [fit.RoomScore(
            ticker="X", level=1, rep="1", score=None, net_support=None,
            unresolved=None, evidence_available=False, missing=("cards:x",),
            holdout=False, field_state_source="card_self_report",
        )]
        with self.assertRaises(fit.FitError):
            fit.fit_ladder(rooms)

    def test_nonmonotone_raw_gets_enforced_ladder(self) -> None:
        # Level populations inverted: R1 scores low, R5 scores high. The raw
        # quantiles violate R1>=R5; the enforced ladder must be monotone and
        # report the fix.
        rooms = []
        base = {1: 0.2, 2: 0.4, 3: 0.6, 4: 0.8, 5: 1.0}
        for lvl, sc in base.items():
            for i in range(30):
                for rep in ("1", "2"):
                    rooms.append(fit.RoomScore(
                        ticker=f"L{lvl}{i}", level=lvl, rep=rep,
                        score=sc + i / 1000.0, net_support=None,
                        unresolved=None, evidence_available=True, missing=(),
                        holdout=False, field_state_source="sheet_state",
                    ))
        out = fit.fit_ladder(rooms, fit_rep="1")
        self.assertTrue(out["raw_non_monotone"])
        vals = [out["thresholds"][k] for k in fit.RISK_LEVELS]
        self.assertTrue(all(a >= b for a, b in zip(vals, vals[1:])))

    def test_out_of_range_level_reported_not_clamped(self) -> None:
        ladder = {"R1": 1.5, "R2": 0.4, "R3": 0.3, "R4": 0.2, "R5": 0.1}
        errors = fit.validate_for_gate(ladder)
        self.assertTrue(any("outside [0, 1]" in e for e in errors))
        # never silently fixed
        self.assertEqual(ladder["R1"], 1.5)
        ladder2 = {"R1": 0.1, "R2": 0.4, "R3": 0.3, "R4": 0.2, "R5": 0.1}
        self.assertTrue(any("not monotone" in e
                            for e in fit.validate_for_gate(ladder2)))

    def test_gate_json_is_single_provider(self) -> None:
        ladder = {k: 0.5 - i * 0.01 for i, k in enumerate(fit.RISK_LEVELS)}
        payload = fit.gate_json("ami-llm", ladder)
        self.assertEqual(list(payload), ["ami-llm"])
        self.assertEqual(list(payload["ami-llm"]), list(fit.RISK_LEVELS))
        # round-trips through the backend parser's rules
        self.assertEqual(fit.validate_for_gate(payload["ami-llm"]), [])


class CliTests(unittest.TestCase):
    def _write_turns(self, tmp: Path, records: list[dict]) -> Path:
        p = tmp / "turns.jsonl"
        with open(p, "w") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")
        return p

    def _record(self, ticker="AAPL", level=1, rep="1", variant=0):
        # Nets kept inside [0, 1] so the fitted ladder passes the backend's
        # range validation: one well/partial card apiece on eq, everything
        # else unsupported, no objections. variant cycles net over
        # {0.0, 0.5, 1.0}.
        grades = {0: ("unsupported", "unsupported"),
                  1: ("partial", "unsupported"),
                  2: ("well", "unsupported")}
        g0, g1 = grades[variant % 3]
        lines0 = [f"item=eq dir=support grade={g0} data=yes claim=x"] + [
            f"item={i} dir=support grade=unsupported data=yes claim=x"
            for i in ("vc", "vh", "bs", "moat")]
        lines1 = [f"item=eq dir=support grade={g1} data=yes claim=x"] + [
            f"item={i} dir=support grade=unsupported data=yes claim=x"
            for i in ("vc", "vh", "bs", "moat")]
        plain = [f"item={i} dir=support grade=unsupported data=yes claim=x"
                 for i in fit.ITEM_FIELD_REGISTRY]
        turns = [
            _turn("fundamentals_analyst", _claims(lines0)),
            _turn("bull_researcher", _claims(lines1)),
            _turn("bear_researcher", _claims(plain)),
            _turn("research_manager", _claims(plain)),
        ]
        return {
            "ticker": ticker, "rep": rep, "risk_score": level,
            "verdict": "APPROVE",
            "turns": turns,
        }

    def test_end_to_end_turns_file(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        records = [self._record(f"T{i:02d}", lvl, rep, variant=i)
                   for lvl in range(1, 6) for i in range(12)
                   for rep in ("1", "2")]
        turns = self._write_turns(tmp, records)
        out_dir = tmp / "out"
        argv = sys.argv
        try:
            sys.argv = ["evidence_gate_fit", "--provider", "test-model",
                        "--turns-file", str(turns), "--out-dir", str(out_dir)]
            fit.main()
        except SystemExit as exc:
            self.fail(f"main exited {exc.code}")
        finally:
            sys.argv = argv
        gate = json.loads((out_dir / "thresholds_test-model.json").read_text())
        self.assertEqual(list(gate), ["test-model"])
        vals = [gate["test-model"][k] for k in fit.RISK_LEVELS]
        self.assertTrue(all(0.0 <= v <= 1.0 for v in vals))
        self.assertTrue(all(a >= b for a, b in zip(vals, vals[1:])))
        report = json.loads(
            (out_dir / "fit_report_test-model.json").read_text())
        self.assertEqual(report["provider"], "test-model")
        self.assertIn("In-sample quantile fit", report["caveats"][0])
        self.assertEqual(report["tally"]["rooms_evidence_unavailable"], 0)
        self.assertEqual(report["gate_validation_errors"], [])
        # never-reuse-across-models caveat ships in the report
        self.assertTrue(any("provider-specific" in c
                            for c in report["caveats"]))

    def test_cli_refuses_without_provider(self) -> None:
        argv = sys.argv
        try:
            sys.argv = ["evidence_gate_fit", "--turns-file", "/nonexistent"]
            with self.assertRaises(SystemExit):
                fit.main()
        finally:
            sys.argv = argv


if __name__ == "__main__":
    unittest.main()
