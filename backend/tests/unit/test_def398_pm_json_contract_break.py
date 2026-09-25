"""DEF398 — a brace inside the trailing prose must not defeat the DEF352 recovery.

DEF352 taught `extract_json_object` to cut prose that follows a complete object,
by trimming back to the LAST `}`. That works while the tail is brace-free. It is
not, when the Chief Investment Officer breaks its JSON-only contract by appending
a `DATA I LACKED:` section — because the section QUOTES the contract it is
breaking, verbatim: *begin with '{' and end with '}'*. `rfind` then lands on the
quoted brace, the trimmed candidate is malformed, and the verdict is discarded.

Measured on the CR219 six-arm mandate-variation run (`qwen3.8-flash-next`):
2 of 6 arms — `h_short` (1278 trailing chars, verdict APPROVE) and `g_learning`
(1473, PASS) — each with exactly one stray brace in the tail, each recovered
cleanly by `raw_decode` and lost outright by the shipped extractor. h_short's
APPROVE is the concrete harm: extraction returns None, `_parse_pm_verdict` yields
no verdict, and the caller fails safe to PASS (DEF059).

P2 again: the contract sentence is already in the prompt, and the model quotes it
while violating it. The parser is the control. The structural control is CR210's
`pm_verdict_schema()` grammar, still gated OFF pending its acceptance-3 re-run.
"""
import json
from pathlib import Path

from app.services.llm_json import ConflictingDecision, extract_json_object

# The tail measured on arms h_short / g_learning, reduced to its defeating
# feature: the model quoting the JSON-only rule back at us.
_QUOTED_CONTRACT_TAIL = (
    "\n\nDATA I LACKED:\n"
    "* (a) Implied volatility for the FOMC event in 14 days.\n\n"
    "PROMPT CONTRADICTIONS:\n"
    "* The system prompt states: \"Your ENTIRE reply must be one single JSON "
    "object — begin with '{' and end with '}'. Do not write any prose outside "
    "the JSON.\" I placed these sections after it regardless."
)


def test_the_measured_shape_parses():
    raw = '{"action": "APPROVE", "size_pct": 2.5}' + _QUOTED_CONTRACT_TAIL
    assert extract_json_object(raw) == {"action": "APPROVE", "size_pct": 2.5}


def test_an_APPROVE_is_not_silently_downgraded():
    """The harm DEF059 turns a lost extraction into: a real APPROVE reads PASS."""
    raw = '{"action": "APPROVE", "size_pct": 1.0}' + _QUOTED_CONTRACT_TAIL
    verdict = extract_json_object(raw)
    assert verdict is not None, "lost verdict would fail safe to PASS"
    assert verdict["action"] == "APPROVE"


def test_many_braces_in_the_tail_still_recover():
    tail = "\n\nExample: {} and {\"nested\": {\"deep\": 1}} and a stray }"
    assert extract_json_object('{"a": 1}' + tail) == {"a": 1}


def test_the_first_object_wins_when_the_pair_is_not_a_decision_conflict():
    """Two objects, neither shaped like a verdict: the first still wins — this
    is the general DEF398 "first complete object" rule, unrelated to the
    MINOR-2 carve-out below (which keys specifically on a conflicting
    `action`)."""
    raw = '{"note": "draft"}\n\nFor contrast: {"note": "final"}'
    assert extract_json_object(raw) == {"note": "draft"}


def test_two_conflicting_decisions_fail_safe_not_first_wins():
    """RETRO-PM-FLOOR round 1 (auditor U68, MINOR-2). This used to pin
    "first object wins" even across a genuine retraction — a draft
    `{"action":"APPROVE"}` followed by a different final `{"action":"REJECT"}`
    read as APPROVE. Two conflicting decisions in one reply is an uncertain
    decision, and DEF059's direction for those is to fail safe (unparseable),
    never to silently pick the first.

    RETRO-PM-FLOOR round 3 (MINOR-2 residual 1): round 2 returned bare
    `None` here, indistinguishable to the caller from "genuinely
    unparseable" — which let `room_runner.py`'s DEF058 reformat retry
    re-ask the model, and DEF067 lets that retry recover an APPROVE but
    never downgrade one, so the conflict could still resolve to APPROVE.
    Round 3 returns a distinguishable `ConflictingDecision` sentinel so the
    caller can fail straight to PASS instead of re-asking — this test pins
    only that it is NOT a real parsed dict (still "not the decision"); the
    caller-side PASS-without-reformat behaviour is pinned in
    room_runner.py's own test."""
    raw = '{"action": "APPROVE"}\n\nFor contrast: {"action": "REJECT"}'
    result = extract_json_object(raw)
    assert isinstance(result, ConflictingDecision)
    assert result.first == {"action": "APPROVE"}
    assert result.second == {"action": "REJECT"}


def test_two_objects_with_the_SAME_action_are_not_a_conflict():
    """A repeated/echoed decision (same `action` twice) is not the ambiguous
    case MINOR-2 targets — only a DIFFERING second `action` fails safe."""
    raw = '{"action": "APPROVE", "size_pct": 3.0}\n\nConfirmed: {"action": "APPROVE"}'
    assert extract_json_object(raw) == {"action": "APPROVE", "size_pct": 3.0}


def test_DEF352_and_DEF256_paths_are_untouched():
    assert extract_json_object('{"a": 1}\n\nWorked example — simulation.') == {"a": 1}
    assert extract_json_object('{"outer": {"inner": [1, 2]}, "b": "}"}\n\nprose') == {
        "outer": {"inner": [1, 2]},
        "b": "}",
    }
    # DEF256: a raw newline inside a string value stays tolerated.
    assert extract_json_object('{"n": "line\none"}\n\nprose') == {"n": "line\none"}


def test_shapes_that_must_still_be_REFUSED():
    assert extract_json_object("no object here") is None
    assert extract_json_object('{"a": 1') is None
    assert extract_json_object("{'a': 1}\n\nprose") is None


def test_against_the_recorded_arms():
    """The two real replies, replayed end to end.

    The corpus path derives from this file's own location (the evidence/
    scripts' convention): a CWD-relative path resolved only when pytest ran
    from backend/, and failed the promotion suite gate, which does not.
    """
    base = (
        Path(__file__).resolve().parents[3]
        / "docs/forward_planning/CR219_room_prompt_contradictions/evidence/arms"
    )
    for arm, action in (("h_short", "APPROVE"), ("g_learning", "PASS")):
        with open(base / arm / "convene.json") as fh:
            turns = json.load(fh)["turns"]
        reply = [t for t in turns if t["agent"] == "portfolio_manager"][0]["answer"]
        got = extract_json_object(reply)
        assert got is not None, f"{arm}: verdict still lost"
        assert got["action"] == action
