"""CR253 — the D26 gate in the repair era: flow-aware totals + operative-turn stance audit.

The post-fold-in V arm surfaced two findings that are measurement-harness
artifacts, not room defects:

  * UNEXPECTED_CALL_COUNT on 19 rows — TOTAL_CALLS_RANGE=(16,18) predates
    the repair flows. A room with a trader geometry repair
    (room_trader_repair) + envelope repairs (room_envelope_repair)
    legitimately exceeds 18 total rows. The gate is now flow-aware: base
    flows ('room', 'room_pm') keep the 16..18 bound; repair/recovery flows
    are counted separately against MAX_REPAIR_FLOW_CALLS with per-flow
    detail.

  * MISSING_STANCE on an agent whose base turn had no envelope but whose
    envelope repair SUCCEEDED — the gate read the base call (flow=='room',
    nth=0) while the operative turn, the text that actually entered the
    transcript, is the repair row. The stance check now audits the NEWEST
    of the agent's base + repair rows, falling back to older operative rows
    only when the newest yields no decision token (a failed repair leaves
    the base turn in the transcript).

Pinned here with duck-typed audit modules, the injection seam scoring.py
is built on. `test_cr109_scoring_pass.py` is the CR109 GAMES scoring pass —
unrelated; these are the first gate_report tests in the suite.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_TOOLS_DIR = (
    Path(__file__).resolve().parents[3] / "docs" / "tools" / "room_investigation_V2"
)
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from library import scoring  # noqa: E402

PROSE = scoring.EXPECTED_PROSE_AGENTS
_PM = scoring.PM_AGENT


class _NoRowsError(Exception):
    pass


def _envelope(agent: str, stance: str = "for") -> str:
    return f"[STANCE: {stance} | CONVICTION: high | HEADLINE: {agent} view]\nThe {agent} case."


_PM_JSON = json.dumps({
    "action": "APPROVE", "size_pct": 2.0, "entry": 150.0, "stop": 141.0,
    "target": 172.0, "horizon_days": 90, "narration": "PM: take it.",
})


class _Audit:
    """Duck-typed audit module: list_calls rows carry agent_id/flow/
    created_at; get_field serves response_text by (agent, nth) with nth
    0-indexed in created_at order, matching audit_db."""

    def __init__(self, rows: list[dict]):
        # rows: list of dicts {agent, flow, text, at} — `at` orders the convene.
        self._rows = sorted(rows, key=lambda r: r["at"])
        self.NoRowsError = _NoRowsError

    def list_calls(self, user_id, **kw):
        return [
            SimpleNamespace(agent_id=r["agent"], flow=r.get("flow"), created_at=r["at"])
            for r in self._rows
        ]

    def get_field(self, user_id, agent_id, field, *, nth=None, **kw):
        texts = [r["text"] for r in self._rows if r["agent"] == agent_id]
        if not texts:
            raise _NoRowsError(agent_id)
        if nth is None:
            if len(texts) > 1:
                raise AssertionError("test must pin nth for multi-row agents")
            nth = 0
        try:
            return texts[nth]
        except IndexError as exc:
            raise _NoRowsError(f"{agent_id} nth={nth}") from exc


def _base_convene() -> list[dict]:
    """A clean 16-row convene: 11 enveloped prose turns + 5 PM draws."""
    rows = [
        {"agent": a, "flow": "room", "text": _envelope(a), "at": i}
        for i, a in enumerate(PROSE)
    ]
    rows += [
        {"agent": _PM, "flow": "room_pm", "text": _PM_JSON, "at": 100 + i}
        for i in range(scoring.MIN_PM_DRAWS)
    ]
    return rows


def _gate(rows):
    return scoring.gate_report("u", audit_module=_Audit(rows))


class TestFlowAwareTotals:
    def test_a_clean_convene_gates_ok(self):
        report = _gate(_base_convene())
        assert report.ok, report.findings
        assert report.stances["trader"] == "for|high"

    def test_repair_era_convene_gates_ok(self):
        """The V-arm shape: 16 base rows + a trader geometry repair + two
        envelope repairs = 19 rows, and every check passes."""
        rows = _base_convene()
        # The trader's base turn was implausible; the repair re-places it.
        # Two analysts skipped the envelope; their repairs supplied it.
        rows.append({"agent": "trader", "flow": "room_trader_repair",
                     "text": _envelope("trader"), "at": 200})
        rows.append({"agent": "news_analyst", "flow": "room_envelope_repair",
                     "text": _envelope("news_analyst"), "at": 201})
        rows.append({"agent": "research_manager", "flow": "room_envelope_repair",
                     "text": _envelope("research_manager"), "at": 202})
        report = _gate(rows)
        assert report.ok, report.findings
        assert len(report.findings) == 0

    def test_repair_rows_over_the_cap_flag_with_per_flow_detail(self):
        rows = _base_convene()
        for i in range(scoring.MAX_REPAIR_FLOW_CALLS + 1):
            rows.append({"agent": "trader", "flow": "room_trader_repair",
                         "text": _envelope("trader"), "at": 200 + i})
        report = _gate(rows)
        kinds = [f.kind for f in report.findings]
        assert "UNEXPECTED_CALL_COUNT" in kinds
        finding = next(f for f in report.findings if f.kind == "UNEXPECTED_CALL_COUNT"
                       and "repair" in f.detail)
        assert "room_trader_repair=7" in finding.detail
        assert f"cap of {scoring.MAX_REPAIR_FLOW_CALLS}" in finding.detail

    def test_base_total_off_range_still_flags(self):
        rows = _base_convene()[:15]  # drop one prose agent's row
        report = _gate(rows)
        finding = next(f for f in report.findings
                       if f.kind == "UNEXPECTED_CALL_COUNT" and f.agent_id == "*")
        assert "base-flow" in finding.detail
        assert "15" in finding.detail

    def test_legacy_rows_without_flow_stay_in_the_base_bucket(self):
        """Pre-flow audit rows (no flow attribute) default to 'room' — a
        17-row legacy convene (16 + a 6th PM recovery draw) gates exactly as
        the old TOTAL_CALLS_RANGE allowed."""
        rows = _base_convene()
        rows.append({"agent": _PM, "flow": None, "text": _PM_JSON, "at": 300})
        for r in rows:
            r.pop("flow")
        report = _gate(rows)
        assert report.ok, report.findings


class TestOperativeTurnStance:
    def test_base_without_envelope_plus_successful_repair_does_not_flag(self):
        """The exact V-arm artifact: the base turn parsed no envelope, the
        room re-asked once, the repair carried it. The operative text is the
        repair row; MISSING_STANCE would punish the room for doing the right
        thing."""
        rows = _base_convene()
        bare = next(r for r in rows if r["agent"] == "news_analyst")
        bare["text"] = "No envelope on this turn at all."
        rows.append({"agent": "news_analyst", "flow": "room_envelope_repair",
                     "text": _envelope("news_analyst"), "at": 200})
        report = _gate(rows)
        assert report.ok, report.findings
        assert report.stances["news_analyst"] == "for|high"

    def test_base_without_envelope_and_no_repair_still_flags(self):
        rows = _base_convene()
        bare = next(r for r in rows if r["agent"] == "research_manager")
        bare["text"] = "No envelope, and the room let it stand."
        report = _gate(rows)
        kinds = {(f.agent_id, f.kind) for f in report.findings}
        assert ("research_manager", "MISSING_STANCE") in kinds
        assert not report.ok

    def test_failed_repair_falls_back_to_the_base_turn(self):
        """Newest operative row (the failed repair) yields no token; the base
        turn is what entered the transcript. If the base parses (e.g. a Side:
        token), no finding; if it too parses nothing, MISSING_STANCE names
        both attempts."""
        rows = _base_convene()
        bare = next(r for r in rows if r["agent"] == "bear_researcher")
        bare["text"] = "Side: WAIT on valuation."
        rows.append({"agent": "bear_researcher", "flow": "room_envelope_repair",
                     "text": "still no envelope here", "at": 200})
        report = _gate(rows)
        assert report.ok, report.findings
        assert report.stances["bear_researcher"] == "WAIT"

        rows2 = _base_convene()
        bare2 = next(r for r in rows2 if r["agent"] == "bear_researcher")
        bare2["text"] = "nothing parseable anywhere"
        rows2.append({"agent": "bear_researcher", "flow": "room_envelope_repair",
                      "text": "still no envelope here", "at": 200})
        report2 = _gate(rows2)
        finding = next(f for f in report2.findings if f.agent_id == "bear_researcher")
        assert finding.kind == "MISSING_STANCE"
        assert "2 base/repair turn(s)" in finding.detail

    def test_trader_geometry_repair_is_the_operative_trader_turn(self):
        """The trader's repair replaces the base turn (CR249) — the gate
        audits the repair's stance, not the base's."""
        rows = _base_convene()
        base = next(r for r in rows if r["agent"] == "trader")
        base["text"] = "[STANCE: for | CONVICTION: high | HEADLINE: wide stop]\nTake it: stop $50."
        rows.append({"agent": "trader", "flow": "room_trader_repair",
                     "text": _envelope("trader", "for"), "at": 200})
        report = _gate(rows)
        assert report.ok, report.findings
        assert report.stances["trader"] == "for|high"
