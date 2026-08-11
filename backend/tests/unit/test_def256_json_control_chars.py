"""DEF256 — a real line break inside `narration` discarded the whole verdict.

`extract_json_object` parsed with `json.loads`' default `strict=True`, which
rejects raw control characters inside string values. A model that writes

    "narration": "Approving at reduced size.
    - Valuation supports it: **P/E 18.2**"

instead of escaping the break as the two characters `\\n` therefore produced no
object at all — and for the PM that is not a degraded read but a DISCARDED
DECISION: `_parse_pm_verdict` returns `llm_verdict=None` and the caller fails
safe to PASS (DEF059). A real APPROVE, with the PM's own levels attached, lost
over a whitespace character.

Latent until DEF236, which made it reachable by design: the PM's narration ask
went from "3–4 sentences" to a decision sentence plus up to 6 short bullets, and
bullets are what a model writes with line breaks. The contract now also asks for
`\\n` explicitly — but `failure_patterns` P2 is that a prompt instruction is not
a control, so the parser is the control and this is its test.

`strict=False` relaxes control characters INSIDE strings and nothing else, which
is the second half of what these tests assert: malformed JSON must still be
rejected, or the fix would trade a lost APPROVE for a fabricated one.
"""

from __future__ import annotations

from app.schemas.mandate import Mandate
from app.schemas.room import VerdictAction
from app.services.coach_engine import hydrate_coach_mandate
from app.services.llm_json import extract_json_object
from app.services.room_runner import _RoomContext, _parse_pm_verdict


def _ctx(mandate: Mandate | None = None) -> _RoomContext:
    return _RoomContext(
        ticker="GRAB",
        mandate=mandate or hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        halal_universe=None,
        classification_universe=None,
        locale_allowed_universe=None,
    )


# The shape DEF236's narration ask invites: a decision sentence, then bullets,
# separated by REAL newlines rather than the escaped two-character form.
_APPROVE_WITH_RAW_NEWLINES = (
    '{"action": "APPROVE", "size_pct": 3.0, "entry": 3.67, "stop": 3.45, '
    '"target": 4.15, "horizon_days": 42, "narration": "Approving at reduced '
    'size.\n- Valuation supports it: **P/E 18.2** against a sector 24.1\n'
    "- The Conservative's tail case is already in the price\n"
    '- Stop sits below the 50-day, not at a round number"}'
)


def test_a_raw_newline_inside_narration_no_longer_kills_the_object():
    """RED before: `extract_json_object` returned None for this exact string."""
    parsed = extract_json_object(_APPROVE_WITH_RAW_NEWLINES)
    assert parsed is not None, "a line break inside a string is not a malformed object"
    assert parsed["action"] == "APPROVE"
    assert "\n- Valuation supports it" in parsed["narration"]


def test_the_verdict_survives_rather_than_failing_safe_to_pass():
    """The half that matters to the user: this is an APPROVE the Room had already
    decided, at the PM's own levels. Before the fix it reached the Verdict Board
    as a PASS."""
    display, verdict = _parse_pm_verdict(_APPROVE_WITH_RAW_NEWLINES, _ctx())
    assert verdict is not None, "a real decision was discarded over whitespace"
    assert verdict.action == VerdictAction.APPROVE
    assert verdict.entry == 3.67
    assert verdict.stop == 3.45
    assert display.startswith("Approving at reduced size.")


def test_the_escaped_form_still_parses_identically():
    """The contract asks for `\\n`. A PM that obeys must not be penalised for it —
    and the two spellings must produce the SAME narration, or the fix would make
    the rendered verdict depend on which form the model happened to pick."""
    escaped = _APPROVE_WITH_RAW_NEWLINES.replace("\n", "\\n")
    raw_parsed = extract_json_object(_APPROVE_WITH_RAW_NEWLINES)
    escaped_parsed = extract_json_object(escaped)
    assert escaped_parsed is not None
    assert escaped_parsed["narration"] == raw_parsed["narration"]


def test_genuinely_malformed_json_is_still_rejected():
    """`strict=False` must not become "accept anything". Each of these is a real
    malformation, not a whitespace question, and a fabricated verdict is a worse
    failure than a lost one — DEF059 fails safe to PASS on purpose."""
    for bad in (
        '{"action": "APPROVE", "size_pct": 3.0,}',          # trailing comma
        "{'action': 'APPROVE', 'size_pct': 3.0}",            # single quotes
        '{action: "APPROVE", "size_pct": 3.0}',              # unquoted key
        '{"action": "APPROVE", "size_pct": }',               # missing value
        "not json at all, just prose about a trade",
    ):
        assert extract_json_object(bad) is None, f"accepted malformed input: {bad!r}"


def test_a_tab_inside_narration_is_tolerated_too():
    """The same control-character class, and the one a model reaches for when it
    lays narration out as a list. Asserted so the fix is not read as
    newline-specific."""
    parsed = extract_json_object('{"action": "PASS", "narration": "No trade.\tSize was never the issue."}')
    assert parsed is not None
    assert "\t" in parsed["narration"]
