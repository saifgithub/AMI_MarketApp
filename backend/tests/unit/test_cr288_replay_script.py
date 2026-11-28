"""CR288 step 2 — the pure helpers of `scripts/cr288_replay.py` (no DB, no network).

Pins: the prompt is cut at the markers the builders wrote; the Risk Officer's JSON contract
is its tail; an audit row is chosen by text before time; percentiles are nearest-rank; the
nearest-ledger-entry list carries where each figure sits in the prompt; the script cannot
write inside the repo and cannot issue anything but one SELECT.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.services import figure_provenance as fp
from scripts import cr288_replay as r

PROMPT = (
    "PERSONA keep it to 5 sentences.\n\n"
    "─── CONVENE THE ROOM — EXECUTION PHASE ───\n"
    "Ticker: AAPL\n"
    "P/E 38.2x, price $358.54\n"
    "\nUser mandate snapshot:\n- risk_score: 3\n"
    "Transcript so far:\nBull said revenue grew 12.5%.\n"
    "\nYour turn. Speak as the Trader. Write 3 sentences."
)


def test_slice_prompt_room_cuts_tail_sheet_and_debate():
    parts = r.slice_prompt(PROMPT, "AAPL", risk_officer=False)
    assert parts.tail.startswith("\nYour turn. Speak as the Trader")
    assert parts.sheet.strip() == "P/E 38.2x, price $358.54"
    assert parts.debate.strip() == "Bull said revenue grew 12.5%."
    assert parts.tail_found


def test_slice_prompt_risk_officer_tail_is_the_json_contract():
    prompt = (
        "Ticker: KO\nP/E 24.1x\n\nUser mandate snapshot:\nTranscript so far:\nx 7.5%\n"
        "\n\nYour ENTIRE reply must be one JSON object — sizes 1.0, 2.0"
    )
    parts = r.slice_prompt(prompt, "KO", risk_officer=True)
    assert parts.tail.startswith("\n\nYour ENTIRE reply")
    assert "7.5%" in parts.debate and "1.0" not in parts.debate
    assert parts.sheet.strip() == "P/E 24.1x"


def test_slice_prompt_missing_markers_remove_nothing():
    parts = r.slice_prompt("no markers 12.5%", "AAPL", risk_officer=False)
    assert (parts.tail, parts.sheet, parts.debate) == ("", "", "")
    assert not parts.tail_found


def test_production_ledger_from_sliced_prompt_excludes_instruction_numbers():
    parts = r.slice_prompt(PROMPT, "AAPL", risk_officer=False)
    ledger = fp.build_ledger(
        PROMPT, static=["PERSONA keep it to 5 sentences.", parts.tail], sheet=parts.sheet, debate=parts.debate
    )
    values = {round(e.value, 2) for e in ledger.entries}
    assert {38.2, 358.54, 12.5, 3.0} <= values
    assert 5.0 not in values


def test_percentile_nearest_rank_and_empty():
    assert r.percentile([], 0.9) == 0
    assert r.percentile(list(range(1, 11)), 0.9) == 9
    assert r.distribution([0, 0, 1, 4, 10]) == {"n": 5, "median": 1.0, "p90": 10.0, "max": 10.0}
    assert r.distribution([])["max"] == 0.0


def _row(created: str, text: str) -> dict:
    return {"created_at": created, "response_text": text}


def test_pick_audit_single_text_then_time_then_none():
    a = _row("2026-11-28T10:00:00+00:00", "alpha " * 30)
    b = _row("2026-11-28T10:01:00+00:00", "beta " * 30)
    assert r.pick_audit([a], "anything", None) == (a, "single")
    assert r.pick_audit([a, b], "alpha " * 30, None) == (a, "text")
    ts = datetime(2026, 11, 28, 10, 0, 30, tzinfo=timezone.utc)
    assert r.pick_audit([a, b], "unrelated", ts) == (a, "time")
    assert r.pick_audit([a, b], "unrelated", None) == (None, "none")
    assert r.pick_audit([], "x", None) == (None, "none")


def test_nearest_entries_orders_by_closeness_and_reports_where():
    text = "gross debt $133,931M and capex $135,921M and cash $64,509M"
    ledger = fp.Ledger()
    ledger.add_text("sheet", text)
    claim = fp.extract("$145B")[0]
    near = r.nearest_entries(ledger, claim, r.prompt_snippets(text), k=2)
    assert [round(n["value"] / 1e6) for n in near] == [135921, 133931]
    assert "capex $135,921M" in near[0]["where"][0]


def test_static_hits_finds_the_value_in_removed_text():
    pct = fp.extract("20%")[0]
    assert r.static_hits(pct, ["never exceed 20% of the book"])
    assert not r.static_hits(pct, ["nothing here"])


def test_sentence_around_returns_the_figures_sentence():
    text = "First sentence. Revenue grew 12.5% on volume. Third."
    assert r.sentence_around(text, text.index("12.5")) == "Revenue grew 12.5% on volume."


def test_db_refuses_anything_but_one_select():
    db = r.Db()
    for bad in ("delete from room_runs", "select 1; drop table x", "update x set y=1", "insert into x values (1)"):
        with pytest.raises(ValueError):
            db.rows(bad)


def test_main_refuses_an_out_dir_inside_the_repo():
    repo = Path(r.__file__).resolve().parents[2]
    assert r.main(["--market", "US", "--out-dir", str(repo / "backend" / "x")]) == 2
