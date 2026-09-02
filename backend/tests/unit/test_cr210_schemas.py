"""CR210 — the three grammars, pinned against the contracts they encode.

A decoding grammar is a SECOND statement of a contract that is already stated in a
prompt. Two descriptions of one contract in two languages is exactly how DEF236
shipped — a length guide counting sentences beside a format asking for bullets —
so every schema here is asserted against its prompt, and the Trader regex is
asserted against the four production parsers that have to read it back.

The Trader round-trip is the load-bearing test in this file. CR196's `regex_S5`
passes the eval scorer and FAILS that round-trip: it emits a bare `R:R: 2.50`,
which `_extract_stated_rr` cannot read, so `_annotate_rr_against_levels` would
print "the proposal stated no R:R, so AMI rendered it" under "These are the figures
of record" — DEF288's false claim, manufactured by the grammar.
"""

from __future__ import annotations

import json
import re

import pytest

from app.schemas.agents import AgentId
from app.services.risk_officer import (
    RISK_CASE_MAX_CHARS,
    RISK_CONFIDENCE_ENUM,
    RISK_KEY_NUMBER_MAX_CHARS,
    _CONFIDENCE_VALUES,
    build_risk_officer_instruction,
    build_risk_officer_schema,
)
from app.services.room_prompts import (
    PM_NARRATION_MAX_CHARS,
    STANCE_HEADLINE_MAX_CHARS,
    _CHARS_PER_TOKEN_WORST_CASE,
    _PM_VERDICT_FORMAT,
    max_tokens_for,
    pm_verdict_schema,
    trader_block_regex,
)
from app.services.room_runner import (
    _annotate_rr_against_levels,
    _extract_stated_rr,
    _match_level,
    parse_stance_envelope,
)
from app.trading_math.option_ladder import build_option_ladder


def _ladder(trader_size: float = 3.0, backstop: float = 6.0):
    """The production chain: mandate risk tier -> reference size -> the rungs the
    officer is handed. Built through `build_option_ladder` rather than hand-rolled
    so the enum under test is the one production computes."""
    return build_option_ladder(
        reference_size_pct=trader_size,
        entry=100.0,
        stop=94.0,
        target=113.0,
        cap_pts=20.0,
        backstop_pct=backstop,
    )


# ── risk officer ──────────────────────────────────────────────────────────


def test_the_enum_is_exactly_the_sizes_the_instruction_prints():
    """Same `rows`, same module, a few lines apart — so the sizes the decoder
    enforces and the sizes the prompt names cannot come from different places."""
    rows = _ladder()
    schema = build_risk_officer_schema(rows)
    instruction = build_risk_officer_instruction(rows)

    enum = schema["properties"]["recommended"]["enum"]
    assert enum == sorted({round(r.size_pct, 1) for r in rows})
    # The instruction prints them as "1.5, 3.0, 4.5. Do not invent a size…", so
    # pull the numerals rather than splitting on a "." that also ends the sentence.
    printed = instruction.split("for these sizes and no others: ")[1]
    printed_sizes = sorted(
        {float(x) for x in re.findall(r"\d+\.\d", printed.split("Do not invent")[0])}
    )
    assert printed_sizes == enum
    # each POSITION is pinned to one rung, so the set is covered exactly once
    positions = [p["properties"]["size_pct"]["enum"]
                 for p in schema["properties"]["options"]["prefixItems"]]
    assert positions == [[v] for v in enum]


def test_the_enum_uses_the_rounded_value_the_renderers_key_on():
    """`_options_by_size` and `render_officer_turns` both look up
    `round(size_pct, 1)`. An enum of 2.6666 against a renderer looking up 2.7
    would make every option un-renderable while every structural check reported
    success."""
    rows = _ladder(2.6666)
    enum = build_risk_officer_schema(rows)["properties"]["recommended"]["enum"]
    assert all(round(v, 1) == v for v in enum)


def test_a_collapsed_ladder_yields_a_deduped_enum_and_matching_item_count():
    """JSON Schema requires enum uniqueness, and the ladder DOES collapse when
    the trader size sits at the backstop. minItems/maxItems must follow the
    deduped count or the model is asked for a rung that does not exist."""
    rows = _ladder(6.0)  # reference at the backstop: press collapses onto it
    schema = build_risk_officer_schema(rows)
    enum = schema["properties"]["recommended"]["enum"]
    assert len(enum) == len(set(enum))
    assert schema["properties"]["options"]["minItems"] == len(enum)
    assert schema["properties"]["options"]["maxItems"] == len(enum)


def test_confidence_enum_cannot_drift_from_the_validator():
    """`_CONFIDENCE_VALUES` is what `render_officer_turns` accepts. If the schema
    permitted a fourth value the decoder would emit something the renderer then
    discards — a grammar guaranteeing a shape nothing downstream honours."""
    assert set(RISK_CONFIDENCE_ENUM) == set(_CONFIDENCE_VALUES)
    schema = build_risk_officer_schema(_ladder())
    assert schema["properties"]["confidence"]["enum"] == list(RISK_CONFIDENCE_ENUM)


def test_every_free_text_field_is_bounded_at_both_ends():
    """maxLength terminates generation (an unbounded string is a state the
    grammar can always extend). minLength stops the decoder satisfying the schema
    with "" — which would pass every structural check while removing the only
    content the field exists to carry."""
    props = build_risk_officer_schema(_ladder())["properties"]
    item = props["options"]["prefixItems"][0]["properties"]
    for field, bound in (
        (item["case_for"], RISK_CASE_MAX_CHARS),
        (item["case_against"], RISK_CASE_MAX_CHARS),
        (item["key_number"], RISK_KEY_NUMBER_MAX_CHARS),
        (props["decisive_number"], RISK_KEY_NUMBER_MAX_CHARS),
    ):
        assert field["maxLength"] == bound
        assert field["minLength"] == 1


# ── PM verdict ────────────────────────────────────────────────────────────


def test_the_action_enum_is_the_two_values_the_prompt_names():
    """CR156 B's user-visible defect — a card marked PASS whose narration opens
    "REJECT:" — and the four off-contract actions measured over 136 production
    convenes both become unrepresentable rather than coerced."""
    assert pm_verdict_schema()["properties"]["action"]["enum"] == ["APPROVE", "PASS"]
    assert '"action": "APPROVE" | "PASS"' in _PM_VERDICT_FORMAT
    for banned in ("MODIFY", "REJECT", "MODIFY-AND-APPROVE"):
        assert banned not in pm_verdict_schema()["properties"]["action"]["enum"]


def test_the_schema_and_the_prompt_name_the_same_keys():
    """Both directions. A key in the prompt the grammar forbids is a contract the
    model cannot satisfy; a key in the grammar the prompt never mentions is one
    it does not know to fill."""
    props = set(pm_verdict_schema()["properties"])
    named = {k for k in props if f'"{k}"' in _PM_VERDICT_FORMAT}
    assert named == props, props - named


def test_strict_mode_requires_every_property():
    """`strict: true` on the OpenAI json_schema wrapper is specified to want
    exactly that, and a schema this server will not compile comes back as an
    in-band error frame (DEF376), not a helpful message. The optional fields are
    nullable unions instead."""
    schema = pm_verdict_schema()
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["additionalProperties"] is False
    for key in ("size_pct", "entry", "stop", "target", "horizon_days"):
        assert "null" in schema["properties"][key]["type"], key


def test_structure_id_exists_only_when_a_menu_was_issued():
    """`_PM_STRUCTURE_FORMAT` is appended only then. On a run with no menu the
    key is not discouraged but unrepresentable; with one, the bounds make an id
    outside the issued set impossible — the first of `_resolve_pm_structure`'s
    three rejections, closed structurally."""
    assert "structure_id" not in pm_verdict_schema()["properties"]
    assert "structure_id" not in pm_verdict_schema([])["properties"]

    sid = pm_verdict_schema(["a", "b", "c"])["properties"]["structure_id"]
    assert sid["minimum"] == 0
    assert sid["maximum"] == 2


def test_narration_cannot_be_empty():
    n = pm_verdict_schema()["properties"]["narration"]
    assert n["minLength"] == 1
    assert n["maxLength"] == PM_NARRATION_MAX_CHARS


# ── the bounds fit the decode budget ──────────────────────────────────────


def _worst_case_chars(schema: dict) -> int:
    """Longest document this schema admits, ignoring key names and punctuation
    (added back as a flat allowance by the caller)."""
    total = 0
    for name, prop in schema["properties"].items():
        total += len(name) + 8
        if prop.get("type") == "string":
            total += prop.get("maxLength", 0)
        elif prop.get("type") == "array":
            # prefixItems: one schema per position, so sum them rather than
            # multiplying a shared `items` by maxItems.
            for item in prop.get("prefixItems") or [prop.get("items", {})]:
                total += sum(
                    len(k) + 8
                    + (v.get("maxLength", 24) if v.get("type") == "string" else 24)
                    for k, v in item.get("properties", {}).items()
                )
        else:
            total += 24
    return total


@pytest.mark.parametrize("agent, schema", [
    (AgentId.PORTFOLIO_MANAGER, pm_verdict_schema(["a", "b", "c"])),
    (AgentId.RISK_OFFICER, build_risk_officer_schema(_ladder())),
])
def test_the_grammar_terminates_before_the_decode_budget_does(agent, schema):
    """The property the bounds exist for. If the longest document a schema admits
    needs more tokens than the agent is given, the grammar guarantees a shape the
    budget makes unreachable — and the reply comes back unparseable rather than
    merely short (recorded as `constraint_status='truncated'`).

    Reuses `_CHARS_PER_TOKEN_WORST_CASE`, the same constant DEF125's budgets were
    derived from, so a future edit that raises a bound past the budget OR lowers
    a budget below the bounds fails here rather than in production.
    """
    ceiling = max_tokens_for(agent) * _CHARS_PER_TOKEN_WORST_CASE
    assert _worst_case_chars(schema) < ceiling


# ── the Trader regex ──────────────────────────────────────────────────────


BUY = """[STANCE: for | CONVICTION: high | HEADLINE: Buy NVDA on strength]
Instrument:     NVDA
Side:           BUY
Size:           2.80% of portfolio
Entry:          $178.42
Target:         $210.00
Stop:           $165.00
Time horizon:   3-6 months
R:R:            2.10:1
AI capex remains intact and earnings momentum supports the multiple."""

WAIT = """[STANCE: neutral | CONVICTION: low | HEADLINE: No setup yet]
Instrument:     NVDA
Side:           WAIT
Size:           0.00% of portfolio
Time horizon:   2 weeks
Waiting for a pullback to the 50-day before committing capital."""


def test_the_grammar_accepts_a_conforming_buy_and_wait():
    rx = trader_block_regex(ticker="NVDA")
    assert re.fullmatch(rx, BUY)
    assert re.fullmatch(rx, WAIT)
    # `Entry: market` matches content/agents/trader.md verbatim.
    assert re.fullmatch(rx, BUY.replace("$178.42", "market"))


def test_the_production_parsers_read_the_grammar_back():
    """The round-trip CR196's `regex_S5` fails. A grammar that satisfies the eval
    scorer but not the parsers that consume it in the Room would buy a green
    number and ship a defect."""
    body, env = parse_stance_envelope(BUY)
    assert (env.stance, env.conviction) == ("for", "high")
    assert env.headline == "Buy NVDA on strength"
    assert "[STANCE" not in body

    assert _match_level(body, "entry") == 178.42
    assert _match_level(body, "stop") == 165.00
    assert _match_level(body, "target") == 210.00

    # THE assertion. A bare `R:R: 2.10` returns None here, and the annotator then
    # claims "the proposal stated no R:R, so AMI rendered it" — DEF288.
    assert _extract_stated_rr(body) == 2.1
    annotated, _ = _annotate_rr_against_levels(body, 178.42, 165.00, 210.00, 2.8)
    assert "2.4:1" in annotated
    assert "stated no R:R" not in annotated


def test_a_bare_ratio_is_unrepresentable():
    """Anti-vacuity for the test above: the `:1` is doing work, not decoration."""
    rx = trader_block_regex(ticker="NVDA")
    assert _extract_stated_rr("R:R:            2.10") is None
    assert not re.fullmatch(rx, BUY.replace("2.10:1", "2.10"))


def test_a_no_position_side_is_never_forced_to_state_levels():
    """CR196's single branch makes Size/Entry/Target/Stop/R:R mandatory, so a Desk
    that wants to WAIT must state a price triple it does not believe in — the
    grammar manufacturing a fabrication. Nothing needs them: the run's levels are
    seeded deterministically before the Desk speaks and never parsed back out."""
    rx = trader_block_regex(ticker="NVDA")
    assert re.fullmatch(rx, WAIT)
    assert re.fullmatch(rx, WAIT.replace("WAIT", "HOLD"))
    body, _ = parse_stance_envelope(WAIT)
    assert [_match_level(body, k) for k in ("entry", "stop", "target")] == [None] * 3


def test_the_headline_bound_is_read_from_the_constant():
    """At CR196's 90 the grammar would legalise headlines the envelope parser then
    nulls, manufacturing gutter entries. Read from the constant so a change to it
    fails here rather than silently widening the grammar."""
    rx = trader_block_regex(ticker="NVDA")
    assert f"{{1,{STANCE_HEADLINE_MAX_CHARS}}}" in rx
    too_long = BUY.replace("Buy NVDA on strength", "x" * (STANCE_HEADLINE_MAX_CHARS + 1))
    assert not re.fullmatch(rx, too_long)


def test_every_stance_the_prompt_offers_is_representable():
    """`_build_stance_format` offers for/against/neutral, plus 'none' when the
    role is not to take a side. CR196 allowed two, which would force the model to
    claim a side on turns where it genuinely has none."""
    rx = trader_block_regex(ticker="NVDA")
    for stance in ("for", "against", "neutral", "none"):
        assert re.fullmatch(rx, BUY.replace("STANCE: for", f"STANCE: {stance}")), stance


def test_the_instrument_is_pinned_to_this_runs_ticker():
    assert not re.fullmatch(trader_block_regex(ticker="AAPL"), BUY)
    # BRK.B has a dot; an unescaped one would match BRKXB.
    assert r"BRK\.B" in trader_block_regex(ticker="BRK.B")


def test_the_grammar_agrees_with_the_role_profile():
    """The money block's shape lives in `content/agents/trader.md`, so this regex
    is a second source of truth for it. Reads the markdown and asserts agreement,
    including the direction rule: deleting `market` from the profile turns this
    red until the grammar follows."""
    from pathlib import Path

    repo = Path(__file__).resolve().parents[3]
    profile = (repo / "content" / "agents" / "trader.md").read_text()
    block = profile.split("## Output structure")[1].split("```")[1]

    # A label is what precedes the alignment padding — splitting on the first ":"
    # would cut "R:R" in half.
    labels = [re.match(r"(.+?):\s{2,}", ln).group(1) for ln in block.strip().splitlines()]
    assert labels == ["Instrument", "Side", "Size", "Entry", "Target", "Stop",
                      "Time horizon", "R:R"]

    rx = trader_block_regex(ticker="NVDA")
    # same labels, same order, in the grammar
    positions = [rx.find(f"{lbl}: +") for lbl in labels]
    assert all(p >= 0 for p in positions), dict(zip(labels, positions))
    assert positions == sorted(positions)

    # the Side vocabulary is the profile's, not a narrower one
    sides = {s.strip() for s in block.split("Side:")[1].split("\n")[0].split("|")}
    for side in sides:
        assert side in rx, side

    # and `market` is accepted iff the profile still offers it
    assert ('"market"' in block) == ("|market)" in rx)
