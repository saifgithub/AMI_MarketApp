"""CR288 (ISS003) — figure provenance in shadow, the Risk Officer log-mode gap, the
zero-correction release invariant.

Covered:
  1. FABLE's 16 brief cases (ISS003 FABLE/prototype/test_brief_cases.py), ported to the
     productionised module, including the three `MISS` tests that pin what the design does
     not catch.
  2. The ledger built from a real-shaped assembled prompt: mandate cap, feed figure, a
     debate figure, a ladder figure; static instructions are not in it.
  3. Conditional figures are not `own`; the breaker; the event's fields.
  4. The Risk Officer under `ROOM_FACTCHECK_NOTES=log`: a sheet figure is promoted, an
     invented one and a debate-only one are not, and no tag is written; annotate mode is
     unchanged.
  5. Switch off means no event; switch on means a byte-identical Room; a shadow that throws
     does not break the Room and is logged at error level.
  6. `room_factcheck_finding` carries market and ticker.
  7. The release invariant: no shipped code path can say "the sheet's own figure is ...".
"""

from __future__ import annotations

import inspect
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import structlog

from app.core.config import Settings, settings
from app.schemas import AgentId, AgentMessage
from app.services import figure_provenance as fp
from app.services import numeric_quotation as nq
from app.services import room_bank
from app.services.coach_engine import hydrate_coach_mandate
from app.services.risk_officer import (
    _UNVERIFIABLE_MARK,
    _rung_derived_headline,
    render_officer_turns,
)
from app.services.room_prompts import build_risk_officer_messages, build_room_messages
from app.trading_math.option_ladder import build_option_ladder

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

_APP_DIR = _THIS_DIR.parent.parent / "app"


@pytest.fixture(autouse=True)
def _uncached_loggers(monkeypatch):
    """`cache_logger_on_first_use` freezes a module logger's processors the first time
    any earlier test makes it emit, which blinds `capture_logs`; a fresh proxy is not."""
    monkeypatch.setattr(fp, "logger", structlog.get_logger())
    monkeypatch.setattr(nq, "logger", structlog.get_logger())


# ── 1. FABLE's brief cases ────────────────────────────────────────────────────

SHEET = """\
P/E: 11.5x trailing, 11.1x forward (consensus)
market cap RM120,655M, FCF -RM15,433M (TTM), FCF yield -12.6%
Free cash flow history: FY2025 -RM16,023M, FY2024 RM27,986M, FY2023 RM873M, FY2022 RM8,257M
FCF conversion: FY2025 -152% of net income
Dividend: yield 6.11%, payout 86%
Ownership: insiders 0.0%, institutions 31.2%
ATR(14): RM0.145 (average true range, simple 14-session average)
52-week range: RM9.78–RM12.42
"""
MANDATE = "Single-name cap: 1.0% of portfolio. Max drawdown 30%."


def _brief_ledger() -> fp.Ledger:
    led = fp.Ledger()
    led.add_text("sheet", SHEET)
    led.add_text("prompt", MANDATE)
    return led


def own(text: str) -> list[str]:
    return fp.own_figures(text, _brief_ledger())


def test_r1_signed_figures_are_figures_of_record():
    assert own("FCF yield is -12.6% and TTM FCF is -RM15,433M.") == []


def test_r1_multiples_are_not_truncated():
    assert own("The stock trades at 11.5x trailing earnings.") == []


def test_r1_average_of_history_is_the_desks_own_figure():
    assert own("The 4-year average FCF of RM5,273M masks the TTM figure of -RM15,433M.") == ["RM5,273M"]


def test_r2_ratio_next_to_an_amount_label():
    assert own(
        "FCF conversion currently -152%, a 6.11% yield despite negative FCF, 0.0% insider ownership."
    ) == []


def test_r2_periods_and_list_markers_are_not_figures():
    assert own("FY2024 FCF was +RM27,986M. (1) FCF remains negative.") == []


def test_r2_forward_pe():
    assert own("At 11.1x forward P/E the multiple is undemanding.") == []


def test_r3_mandate_cap_is_a_figure_of_record():
    statuses = {p.fig.raw: p for p in fp.classify("The mandate caps a single name at 1.0%.", _brief_ledger())}
    assert statuses["1.0%"].status == "record" and statuses["1.0%"].sources == ("prompt",)


def test_r3_multiple_of_atr():
    # RM9.78 and RM0.145 are on the sheet; "1.0x" is the desk's own multiplier.
    assert own("The RM9.78 stop is exactly 1.0x ATR(14) (RM0.145) away.") == ["1.0x"]


def test_r3_sign_in_words_after_the_number():
    assert own("TTM free cash flow is RM15,433M negative.") == []


def test_invented_figure_is_listed():
    assert own("Trailing P/E of 14.2x looks cheap against ROIC of 19.4%.") == ["14.2x", "19.4%"]


def test_altered_figure_is_listed():
    assert own("FCF yield is -21.6% on TTM FCF of -RM15,343M.") == ["-21.6%", "-RM15,343M"]


def test_rounding_and_truncation_are_not_alterations():
    assert own("FCF of -RM15.4B (TTM); market cap RM120.6B; RM120.7 billion; RM15.4bil.") == []


def test_MISS_dropped_sign_is_not_caught():
    assert own("FCF yield is 12.6%.") == []


def test_MISS_right_number_wrong_label_is_not_caught():
    assert own("Trailing P/E is 11.1x.") == []  # 11.1x is the FORWARD multiple


def test_MISS_altered_figure_that_lands_on_another_sheet_figure():
    assert own("Dividend payout is 31.2%.") == []  # 31.2% is institutional ownership


def test_the_listed_figures_never_state_a_sheet_value():
    """FABLE's `provenance_note` is deliberately not productionised: the module has no
    function that makes user-visible text, and what it lists is only the desk's own words."""
    assert not hasattr(fp, "provenance_note")
    led = _brief_ledger()
    for text in ("P/E of 25x.", "FCF is RM5,273M.", "ATR is RM0.2.", "Yield 7%.", "Market cap RM99B."):
        listed = " ".join(fp.assess_turn(text, led).own)
        for value in ("11.5", "11.1", "15,433", "0.145", "6.11", "120,655"):
            assert value not in listed


# ── 2. The ledger from a real-shaped assembled prompt ─────────────────────────

_PROFILE = {
    "ticker": "AAPL",
    "field_state": {"news": "live", "pe": "live"},
    "pe": 38.2,
    "catalyst": "Board approved a $55M equity target for the CEO",
    "news_headlines": [],
}


def _transcript(text: str) -> list[AgentMessage]:
    return [AgentMessage(
        agent_id=AgentId.BULL_RESEARCHER, role="agent", content=text,
        timestamp=datetime.now(timezone.utc),
    )]


def _room_prompt(**kw):
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3, "single_name_cap_pct": 3.0})
    cap = fp.PromptCapture()
    sp, _ = build_room_messages(
        agent_id=AgentId.NEUTRAL_DEBATOR, mandate=mandate, user_id=None, ticker="AAPL",
        profile=_PROFILE, transcript=_transcript("Margins hit 17.4% on the call."),
        prompt_capture=cap, **kw,
    )
    return sp, cap


def _ledger_of(cap: fp.PromptCapture) -> fp.Ledger:
    return fp.build_ledger(cap.prompt, static=cap.static, sheet=cap.sheet, debate=cap.debate)


def test_ledger_mandate_cap_is_a_record():
    _sp, cap = _room_prompt()
    p = fp.classify("The single-name cap of 3.0% binds.", _ledger_of(cap))
    assert [(x.status, x.sources) for x in p if x.status != "not_a_figure"] == [("record", ("prompt",))]


def test_ledger_feed_figure_is_a_record():
    _sp, cap = _room_prompt()
    p = fp.classify("The $55M equity target looks rich.", _ledger_of(cap))
    assert [x.status for x in p if x.status != "not_a_figure"] == ["record"]


def test_ledger_debate_figure_is_source_debate_and_counted_apart():
    _sp, cap = _room_prompt()
    led = _ledger_of(cap)
    p = fp.classify("The Bull's 17.4% margin claim does not survive.", led)
    assert [(x.status, x.sources) for x in p if x.status != "not_a_figure"] == [("record", ("debate",))]
    assert fp.assess_turn("The Bull's 17.4% margin claim does not survive.", led).record_debate_only == 1


def test_ledger_invented_figure_is_own():
    _sp, cap = _room_prompt()
    assert fp.own_figures("P/E 38.2x against an invented 91.7x.", _ledger_of(cap)) == ["91.7x"]


def test_ledger_excludes_the_static_instructions():
    """A numeral in a static segment is not a figure the desk was shown."""
    led = fp.build_ledger(
        "Persona: aim for a 77.7% hit rate.\nSheet says P/E 12.3x.",
        static=["Persona: aim for a 77.7% hit rate."],
    )
    assert fp.own_figures("The hit rate is 77.7% and the P/E 12.3x.", led) == ["77.7%"]


def test_ledger_capture_changes_nothing_in_the_prompt():
    sp_with, _cap = _room_prompt()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3, "single_name_cap_pct": 3.0})
    sp_without, _ = build_room_messages(
        agent_id=AgentId.NEUTRAL_DEBATOR, mandate=mandate, user_id=None, ticker="AAPL",
        profile=_PROFILE, transcript=_transcript("Margins hit 17.4% on the call."),
    )
    assert sp_with == sp_without


def test_capture_static_segments_are_really_in_the_prompt():
    sp, cap = _room_prompt()
    assert len(cap.static) == 2 and all(seg in sp for seg in cap.static)
    assert cap.sheet in sp and cap.debate in sp


def test_risk_officer_prompt_ledger_carries_the_ladder():
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3, "single_name_cap_pct": 3.0})
    cap = fp.PromptCapture()
    _sp, _msgs, rows = build_risk_officer_messages(
        mandate=mandate, ticker="AAPL", profile=_PROFILE,
        transcript=_transcript("Margins hit 17.4% on the call."),
        trade_proposal={"size_pct": 3.0, "entry": 100.0, "stop": 94.0, "target": 113.0},
        prompt_capture=cap,
    )
    assert cap.filled and len(cap.static) == 2
    led = _ledger_of(cap)
    drawdown = f"{rows[1].contribution_pts:.2f} pt"
    assert fp.own_figures(f"The reference rung costs {drawdown} of drawdown.", led) == []
    assert fp.own_figures("The reference rung costs 9.87 pt of drawdown.", led) == ["9.87 pt"]


# ── 3. Conditionals, the breaker, the event ───────────────────────────────────


def test_a_figure_inside_an_explicit_conditional_is_not_own():
    led = _brief_ledger()
    text = "The thesis changes if FCF conversion recovers above 60%."
    assert fp.own_figures(text, led) == []
    assert fp.assess_turn(text, led).counts["conditional"] == 1


def test_a_figure_outside_a_conditional_is_still_own():
    led = _brief_ledger()
    assert fp.own_figures("FCF conversion is heading to 60%. If it stalls, we exit.", led) == ["60%"]


def test_derived_figure_is_not_own():
    led = fp.Ledger()
    led.add_text("sheet", "Price $120.00. Median price $100.00.")
    assert fp.own_figures("A 20% premium: $120.00 against $100.00.", led) == []


def test_execution_desk_entry_stop_target_are_decisions_not_claims():
    led = _brief_ledger()
    text = "Entry: $212.40\nStop: $201.10\nTarget: $240.00\nThe thesis rests on 99.9% certainty."
    result = fp.assess_turn(text, led)
    assert result.counts["decision"] == 3 and result.own == ["99.9%"]


def test_non_figures_are_excluded():
    led = fp.Ledger()
    assert fp.own_figures("In FY2024 and 2025, ATR(14) and the 52-week range, item 3, 5 days.", led) == []


def test_ami_marks_are_not_the_desks_figures():
    led = fp.Ledger()
    text = "A plain read.\n[AMI: the reward-to-risk is 2.4, not 3.1]"
    assert fp.own_figures(text, led) == [] and fp.assess_turn(text, led).own == []


def test_the_breaker_trips_above_six_own_figures_and_not_at_six():
    led = fp.Ledger()
    six = "Levels 101.1x, 102.2x, 103.3x, 104.4x, 105.5x, 106.6x."
    seven = six[:-1] + ", 107.7x."
    assert fp.assess_turn(six, led).breaker is False
    assert fp.assess_turn(seven, led).breaker is True


def _capture_of(prompt: str, **kw) -> fp.PromptCapture:
    cap = fp.PromptCapture()
    cap.fill(prompt, static=kw.get("static", ()), sheet=kw.get("sheet", ""), debate=kw.get("debate", ""))
    return cap


def _events(logs):
    return [e for e in logs if e.get("event") == "room_figure_provenance"]


def test_the_event_carries_every_field_once():
    cap = _capture_of("Sheet: P/E 12.3x, cap 3.0%.", sheet="Sheet: P/E 12.3x, cap 3.0%.")
    run_id = uuid4()
    with structlog.testing.capture_logs() as logs:
        fp.log_turn_provenance(
            capture=cap, text="P/E 12.3x, cap 3.0%, my own 45.6x.", run_id=run_id,
            agent_id=AgentId.BEAR_RESEARCHER, market="US", ticker="AAPL",
        )
    (e,) = _events(logs)
    assert e["run_id"] == str(run_id)
    assert e["agent_id"] == "bear_researcher"
    assert e["market"] == "US" and e["ticker"] == "AAPL"
    assert e["counts"] == {"record": 2, "derived": 0, "own": 1, "conditional": 0, "decision": 0}
    assert e["own_figures"] == ["45.6x"]
    assert e["ledger_size"] == 2 and e["breaker"] is False and e["log_level"] == "info"


def test_the_breaker_event_is_a_warning():
    cap = _capture_of("nothing numeric here")
    text = "Levels " + ", ".join(f"{100 + i}.{i}x" for i in range(1, 9)) + "."
    with structlog.testing.capture_logs() as logs:
        fp.log_turn_provenance(capture=cap, text=text, agent_id=AgentId.TRADER, market="US", ticker="AAPL")
    (e,) = _events(logs)
    assert e["breaker"] is True and e["log_level"] == "warning" and e["own_total"] == 8
    assert len(e["own_figures"]) == 8


def test_a_shadow_failure_is_loud_and_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("ledger exploded")

    monkeypatch.setattr(fp, "build_ledger", boom)
    with structlog.testing.capture_logs() as logs:
        out = fp.log_turn_provenance(capture=_capture_of("x 1.5%"), text="y 2.5%", agent_id=AgentId.TRADER)
    assert out is None
    (err,) = [e for e in logs if e["event"] == "room_figure_provenance_error"]
    assert err["log_level"] == "error" and "ledger exploded" in err["error"]


def test_an_unfilled_capture_is_logged_as_an_error_not_skipped():
    with structlog.testing.capture_logs() as logs:
        assert fp.log_turn_provenance(capture=fp.PromptCapture(), text="a 1.5%") is None
    (err,) = [e for e in logs if e["event"] == "room_figure_provenance_error"]
    assert err["log_level"] == "error" and err["stage"] == "no_prompt_capture"


# ── 4. Risk Officer: the log-mode gap ─────────────────────────────────────────

_SHEET = {"pe": 60.0, "ticker": "AAPL"}
_ROWS = build_option_ladder(
    reference_size_pct=3.0, entry=100.0, stop=94.0, target=113.0,
    cap_pts=30.0, current_drawdown_pct=0.0,
)


@pytest.fixture
def mode(monkeypatch):
    def _set(value: str) -> None:
        monkeypatch.setattr(settings, "room_factcheck_notes", value)
    return _set


def _payload(press_key: str, decisive: str = "0.18") -> dict:
    return {
        "options": [
            {"size_pct": s, "case_for": "f", "case_against": "a",
             "key_number": press_key if s == 5.0 else f"kn-{s}"}
            for s in (1.5, 3.0, 5.0)
        ],
        "recommended": 3.0,
        "confidence": "medium",
        "decisive_number": decisive,
    }


def _press(payload, profile=_SHEET):
    turns = render_officer_turns(payload, _ROWS, headline_max_chars=80, profile=profile)
    return next(t for t in turns if t.agent_id is AgentId.AGGRESSIVE_DEBATOR)


@pytest.mark.parametrize("notes", ["log", "annotate"])
def test_ro_a_sheet_figure_is_promoted_in_both_modes(mode, notes):
    mode(notes)
    press = _press(_payload("trailing P/E 60.0"))
    assert press.headline == "trailing P/E 60.0"
    assert _UNVERIFIABLE_MARK not in press.text


def test_ro_log_mode_an_invented_figure_is_not_promoted_and_gets_no_tag(mode):
    mode("log")
    press = _press(_payload("an invented 987.6"))
    assert press.headline == _rung_derived_headline(_ROWS[2])
    assert _UNVERIFIABLE_MARK not in press.text
    assert "Key figure: an invented 987.6" in press.text  # text byte-for-byte as the officer wrote it


def test_ro_log_mode_a_figure_found_only_in_the_debate_is_not_promoted(mode):
    """The Bull said 17.4% earlier in the Room. The officer quoting it as a key figure is
    quoting a desk, not the sheet or the ladder: it does not become the headline."""
    mode("log")
    debate_only = "the Bull's 17.4% margin"
    assert "17.4" not in str(_SHEET)
    press = _press(_payload(debate_only))
    assert press.headline == _rung_derived_headline(_ROWS[2])
    assert _UNVERIFIABLE_MARK not in press.text


def test_ro_log_mode_decisive_number_is_demoted_the_same_way(mode):
    mode("log")
    turns = render_officer_turns(
        _payload("kn", decisive="an invented 555.5"), _ROWS, headline_max_chars=80, profile=_SHEET,
    )
    neu = next(t for t in turns if t.agent_id is AgentId.NEUTRAL_DEBATOR)
    assert neu.headline != "an invented 555.5"
    assert _UNVERIFIABLE_MARK not in neu.text and "decided by an invented 555.5" in neu.text


def test_ro_annotate_mode_is_todays_behaviour(mode):
    mode("annotate")
    press = _press(_payload("an invented 987.6"))
    assert _UNVERIFIABLE_MARK in press.text
    assert press.headline == _rung_derived_headline(_ROWS[2])


def test_ro_the_two_modes_pick_the_same_headline(mode):
    heads = {}
    for m in ("log", "annotate"):
        mode(m)
        heads[m] = _press(_payload("an invented 987.6")).headline
    assert heads["log"] == heads["annotate"]


# ── 5. The Room, end to end: switch off, switch on, shadow throws ─────────────


def _room(monkeypatch, *, shadow: bool, notes: str = "log"):
    import test_cr201_risk_officer_room as R201

    monkeypatch.setattr(settings, "room_figure_provenance_shadow", shadow)
    monkeypatch.setattr(settings, "room_factcheck_notes", notes)
    with structlog.testing.capture_logs() as logs:
        events, runner = R201._run_room(R201._Gateway(), monkeypatch)
    run = runner.get_run(events[0].run_id)
    stream = [
        (e.kind, e.phase, e.agent_id, e.text, e.stance, e.conviction, e.headline,
         e.argued_size_pct, e.scripted,
         None if e.verdict is None else e.verdict.model_dump(mode="json", exclude={"run_id"}))
        for e in events
    ]
    transcript = [
        (m.agent_id, m.role, m.content, m.stance, m.conviction, m.headline, m.argued_size_pct,
         m.scripted, m.envelope_parsed, m.data_gaps)
        for m in run.transcript
    ]
    return stream, transcript, logs


def _normalise(stream):
    out = []
    for row in stream:
        verdict = row[-1]
        if isinstance(verdict, dict):
            verdict = {k: v for k, v in verdict.items() if k not in ("id", "created_at", "run_id", "timestamp")}
        out.append(row[:-1] + (verdict,))
    return out


def test_switch_off_no_event_and_no_error(monkeypatch):
    _stream, _transcript, logs = _room(monkeypatch, shadow=False)
    assert not [e for e in logs if str(e.get("event", "")).startswith("room_figure_provenance")]


@pytest.mark.parametrize("notes", ["log", "annotate"])
def test_switch_on_the_room_is_byte_identical_and_events_are_emitted(monkeypatch, notes):
    off_stream, off_transcript, _ = _room(monkeypatch, shadow=False, notes=notes)
    on_stream, on_transcript, logs = _room(monkeypatch, shadow=True, notes=notes)
    assert _normalise(on_stream) == _normalise(off_stream)
    assert on_transcript == off_transcript
    events = _events(logs)
    agents = [e["agent_id"] for e in events]
    # eight live prose desks plus the Risk Officer; the CIO's JSON verdict is not a prose turn
    assert sorted(agents) == sorted([
        "fundamentals_analyst", "market_analyst", "news_analyst", "social_media_analyst",
        "bull_researcher", "bear_researcher", "research_manager", "trader", "risk_officer",
    ])
    assert len(set(agents)) == len(agents)  # exactly one event per desk turn
    assert {e["market"] for e in events} == {"US"} and {e["ticker"] for e in events} == {"AAPL"}
    assert not [e for e in logs if e["event"] == "room_figure_provenance_error"]


def test_a_shadow_that_throws_does_not_break_the_room_and_is_logged_at_error(monkeypatch):
    off_stream, off_transcript, _ = _room(monkeypatch, shadow=False)

    def boom(*a, **k):
        raise RuntimeError("ledger exploded")

    monkeypatch.setattr(fp, "build_ledger", boom)
    on_stream, on_transcript, logs = _room(monkeypatch, shadow=True)
    assert _normalise(on_stream) == _normalise(off_stream)
    assert on_transcript == off_transcript
    assert not _events(logs)
    errors = [e for e in logs if e["event"] == "room_figure_provenance_error"]
    assert len(errors) == 9 and all(e["log_level"] == "error" for e in errors)


# ── 6. Telemetry: market and ticker on room_factcheck_finding ─────────────────


def test_factcheck_finding_carries_market_and_ticker(mode):
    mode("log")
    with structlog.testing.capture_logs() as logs:
        nq.annotate_sheet_mismatches(
            "The trailing P/E of 25 looks cheap.", {"pe": 60.0, "ticker": "AAPL"}, run_id=uuid4(),
        )
        nq.annotate_sheet_mismatches(
            "The trailing P/E of 25 looks cheap.",
            {"pe": 60.0, "ticker": "1155.KL", "market": "MY"}, run_id=uuid4(),
        )
    found = [e for e in logs if e["event"] == "room_factcheck_finding"]
    assert [(e["market"], e["ticker"]) for e in found] == [("US", "AAPL"), ("MY", "1155.KL")]


def test_risk_officer_finding_carries_market_and_ticker(mode):
    mode("log")
    with structlog.testing.capture_logs() as logs:
        _press(_payload("an invented 987.6"), profile={"pe": 60.0, "ticker": "AAPL"})
    found = [e for e in logs if e["event"] == "room_factcheck_finding"]
    assert found and all(e["market"] == "US" and e["ticker"] == "AAPL" for e in found)


# ── 7. Release invariant: no shipped path can say "the sheet's own figure is ..." ──

_FRAGMENTS = ("the sheet's own figure is", "ami checked")
# (file, line text must contain). The first is the annotate-mode note, reachable only past the
# `ROOM_FACTCHECK_NOTES == "log"` return (asserted below). The second is the price-direction
# check on the Trader's instruction, which judges a direction against the price, not a figure
# against the sheet.
_ALLOWED = {
    ("services/numeric_quotation.py", "AMI checked “"),
    ("services/numeric_quotation.py", "the sheet's own figure is"),
    ("services/room_runner.py", "AMI checked this instruction against the price"),
}


def _is_code_line(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#")


def test_no_unlisted_code_path_can_emit_a_correction_sentence():
    offenders = []
    for path in sorted(_APP_DIR.rglob("*.py")):
        rel = path.relative_to(_APP_DIR).as_posix()
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not _is_code_line(line) or not any(f in line.lower() for f in _FRAGMENTS):
                continue
            if not any(rel == f and frag in line for f, frag in _ALLOWED):
                offenders.append(f"{rel}:{no}: {line.strip()}")
    assert not offenders, "a new correction sentence ships outside the gated code:\n" + "\n".join(offenders)


def test_the_annotate_note_is_built_only_after_the_log_mode_return():
    src = inspect.getsource(nq.annotate_sheet_mismatches)
    gate = src.index('factcheck_notes_mode() == "log"')
    assert gate < src.index("the sheet's own figure is") and gate < src.index("AMI checked")


def test_log_mode_the_alpha_default_no_surface_renders_a_correction(mode):
    mode("log")
    wrong = "The trailing P/E of 25 looks cheap."
    sheet = {"pe": 60.0, "ticker": "AAPL"}
    rendered = [
        nq.annotate_sheet_mismatches(wrong, sheet, surface="agent_text"),
        nq.annotate_sheet_mismatches(wrong, sheet, surface="kill_criterion"),
        _press(_payload("an invented 987.6")).text,
        "\n".join(t.text for t in render_officer_turns(
            _payload("kn", decisive="an invented 555.5"), _ROWS, headline_max_chars=80, profile=sheet,
        )),
    ]
    assert not nq.headline_conflicts_with_sheet("P/E at 25, cheap", sheet)
    for text in rendered:
        assert not any(f in text.lower() for f in _FRAGMENTS)
    assert rendered[0] == wrong and rendered[1] == wrong


def test_the_full_room_in_log_mode_renders_no_correction_sentence(monkeypatch):
    _stream, transcript, _logs = _room(monkeypatch, shadow=True, notes="log")
    for row in transcript:
        assert not any(f in row[2].lower() for f in _FRAGMENTS)


# ── 8. The switch ─────────────────────────────────────────────────────────────


def test_the_switch_defaults_off_and_is_not_a_room_key_setting():
    assert Settings.model_fields["room_figure_provenance_shadow"].default is False
    assert "room_figure_provenance_shadow" in room_bank.ROOM_SETTINGS_NOT_KEYED
    assert "room_figure_provenance_shadow" not in room_bank.ROOM_POLICY_SETTINGS


def test_the_module_exposes_no_user_visible_text_builder():
    public = [n for n, v in vars(fp).items() if inspect.isfunction(v) and v.__module__ == fp.__name__ and not n.startswith("_")]
    assert sorted(public) == [
        "assess_turn", "build_ledger", "classify", "extract", "log_turn_provenance", "own_figures",
    ]
