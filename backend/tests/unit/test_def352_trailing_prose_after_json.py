"""DEF352 — a complete JSON object followed by trailing prose must still parse.

`extract_json_object` trimmed surrounding prose only when the reply did NOT
start with `{`. A reply that opened with the object and then added a sentence
went to `json.loads` whole and was rejected, discarding a decision the model
had already made correctly.

Measured, not hypothesised: on the CR201 production assembly this shape
accounted for **42.6%** of Risk Officer replies (vs 1.5% on CR197's assembly),
every one of them the same tail — a disclaimer sentence after the object. A
controlled probe isolated the trigger to the simulated-portfolio block being
present in the prompt. In production each discard degrades the Room to a
ladder-only rendering, so this parser gap was worth ~2 convenes in 5.

The prompt already says "No prose outside it". P2: a prompt instruction is not
a control. This is the control.
"""
import pytest

from app.services.llm_json import extract_json_object

# The exact tail measured on the 2026-08-21 run.
_MEASURED_TAIL = "Worked example — classroom simulation, not financial advice."


def test_the_measured_shape_parses():
    raw = '{"action": "APPROVE", "size_pct": 2.5}\n\n' + _MEASURED_TAIL
    assert extract_json_object(raw) == {"action": "APPROVE", "size_pct": 2.5}


@pytest.mark.parametrize(
    "tail",
    ["\n\nNote: simulation only.", " — illustrative.", "\n```", "\n\n\n  trailing  "],
)
def test_any_trailing_tail_is_cut(tail):
    assert extract_json_object('{"a": 1}' + tail) == {"a": 1}


def test_nested_braces_keep_the_whole_object():
    raw = '{"outer": {"inner": [1, 2]}, "b": "}"}\n\nprose'
    assert extract_json_object(raw) == {"outer": {"inner": [1, 2]}, "b": "}"}


def test_shapes_that_must_still_be_REFUSED():
    # Not JSON at all.
    assert extract_json_object("no object here") is None
    # Opened and never closed — DEF258 owns repair, and only opt-in.
    assert extract_json_object('{"a": 1') is None
    # Genuinely malformed inside the braces is still malformed.
    assert extract_json_object("{'a': 1}\n\nprose") is None


def test_the_paths_that_already_worked_still_work():
    assert extract_json_object('{"a": 1}') == {"a": 1}
    assert extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json_object('Here you go: {"a": 1}') == {"a": 1}
