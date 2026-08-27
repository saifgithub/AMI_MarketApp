"""CR197 — one Risk Officer that emits structured options, replacing three that argue.

What the three-officer debate actually sells the Chief Investment Officer, measured
over 136 replayed convenes, is three separable things:

  1. a menu of sized options — deterministic, and `trading_math.option_ladder`
     already computes it;
  2. ticker-specific reasons attached to those sizes — real work, and the half the
     bare ladder did NOT recover (ladder alone 11.8% vs a 16.3% baseline);
  3. three named voices on screen — the comb, the personas, a populated room.

The design fault is that (3) is being paid for with inference. Three models each
write ~800 tokens of assigned advocacy so the UI can render three hexagons, at three
sequential LLM calls, and their stances are role constants that carry ~0 bits about
the ticker (Aggressive argued "for" in 117 of 118 convenes, Conservative "against" in
117 of 118).

This module keeps (1) and (2) and demotes (3) to a presentation layer. One officer
receives the computed ladder and fills in evidence per rung — `case_for`,
`case_against`, `key_number` — as JSON rather than prose. The UI can still render
three voices from one object: `case_for` is the aggressive hexagon, `case_against`
the conservative one, `recommended` + `confidence` the balanced call.

Three properties this buys that the debate cannot:

  * **The model never emits a computed number.** Sizes and drawdown figures come from
    the ladder; the officer may only cite them, and `key_number` is explicitly a
    quotation from the fact sheet. That closes the DEF066 → DEF235 → DEF241 →
    CR166-Tier-D arithmetic class STRUCTURALLY rather than by instruction —
    `failure_patterns` P2 is explicit that asking nicely measures ~30%.
  * **Disagreement becomes real.** Sampling this agent N times produces variance the
    model actually has (measured: 19.7% of convenes split across byte-identical
    prompts) instead of variance assigned by role.
  * **One serial step instead of three.** The officers never needed to read each other
    — the Aggressive speaks first and provably cannot rebut anyone (CR153 F3, 0/18).

Nothing here decides anything. The CIO still chooses, the risk-tier clamp still
bounds the choice, and `enforce_safety_floor` remains the only vetoer (DEF059).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.schemas.agents import AgentId
from app.trading_math.option_ladder import LadderOption

RISK_OFFICER_PERSONA = (
    "You are the Risk Officer on the user's analyst team. You do not decide whether "
    "the trade happens — the Chief Investment Officer does. Your job is to hand them "
    "a decision-ready set of sized options, each with the strongest honest case for "
    "and against it, drawn from the evidence above.\n\n"
    "You are one officer, not an advocate for a position. Do not argue a house view. "
    "For each size, make the best case a bull would make and the best case a bear "
    "would make, and then say which size YOU would take and how strongly you hold "
    "that."
)


def build_risk_officer_instruction(rows: list[LadderOption]) -> str:
    """The JSON contract, with the candidate sizes fixed by the caller.

    The sizes are NOT the model's to choose: they are `risk_debator_sizes`, the same
    spread the three officers were handed to argue. Fixing them in the contract is
    what makes the arithmetic unfalsifiable — there is no size in the output that the
    model invented, so there is no drawdown figure it can get wrong.
    """
    sizes = ", ".join(f"{r.size_pct:.1f}" for r in rows)
    return (
        "\n\nYour ENTIRE reply must be one JSON object — begin with '{' and end with "
        "'}'. No prose outside it.\n"
        '{"options": [\n'
        '   {"size_pct": <one of the sizes below, unchanged>,\n'
        '    "case_for": "<the strongest evidence-based reason to take THIS size, one '
        'sentence>",\n'
        '    "case_against": "<the strongest evidence-based reason not to, one '
        'sentence>",\n'
        '    "key_number": "<the single figure from the evidence above that decides '
        'it — quote it, do not compute anything new>"}\n'
        "  ],\n"
        ' "recommended": <one of the sizes below>,\n'
        ' "confidence": "low" | "medium" | "high",\n'
        ' "decisive_number": "<the one figure that most moved you, quoted>"}\n\n'
        f"Provide exactly one entry per size, for these sizes and no others: {sizes}. "
        "Do not invent a size, and do not restate a drawdown or cap figure of your "
        "own — those are computed for you above and quoting them is the only correct "
        "use.\n"
        "`confidence` is how clearly the evidence separates these options: high when "
        "one plainly wins, low when the data genuinely does not adjudicate. A "
        "confident call and an uncertain one are different findings and must not read "
        "the same."
    )


# CR210 — bounds for every free-text field in the officer schema.
#
# maxLength is LOAD-BEARING, not tidiness. An unbounded string is a state the
# grammar can always extend, so the model can write prose inside `case_for`
# forever and never emit the closing quote — measured on the CR196 kit, 3 of the
# first 11 rows ran to the token cap mid-sentence inside that field, and RAISING
# the cap did not fix it. Bounding every free-text field is what terminates
# generation.
#
# Sized to the ASK, generously. `case_for` is "one sentence"; 400 chars is about
# two. The floor matters as much as the ceiling: a hit chops MID-WORD on this
# backend (verified 2026-08-25), so a bound near the observed length would
# guillotine real answers. Worst case here is
# 3 x (400 + 400 + 60) + 60 + scaffolding ~= 3,040 chars, comfortably inside the
# officer's 1800-token budget at `_CHARS_PER_TOKEN_WORST_CASE` — the grammar
# terminates before the budget does, which is the whole point.
RISK_CASE_MAX_CHARS = 400
RISK_KEY_NUMBER_MAX_CHARS = 60

# The `confidence` enum, in semantic rather than alphabetical order so the
# grammar offers the model a ladder rather than a shuffled set. Kept as its own
# constant and pinned against `_CONFIDENCE_VALUES` by
# `test_cr210_risk_officer_schema_matches_the_ladder`, so the schema and the
# validator below cannot drift apart.
RISK_CONFIDENCE_ENUM = ("low", "medium", "high")


def build_risk_officer_schema(rows: list[LadderOption]) -> dict[str, Any]:
    """CR210 — the grammar half of `build_risk_officer_instruction(rows)`.

    Same argument, same module, a few lines apart, so the enum the decoder
    enforces and the sizes the instruction prints cannot come from different
    places. That instruction says "for these sizes and no others"; this makes it
    true rather than requested — `failure_patterns` P2 measures "asking nicely"
    at ~30%, and CR196 measured this exact check at 57% on an untuned model.

    The enum is `round(r.size_pct, 1)` — the value `_options_by_size` and
    `render_officer_turns` both key on — never the raw float. An enum of
    2.6666 against a renderer looking up 2.7 would make every option
    un-renderable while every structural check reported success.

    Deduped, because JSON Schema requires enum uniqueness and the ladder CAN
    collapse (a trader size at the backstop makes press == reference).
    `minItems`/`maxItems` follow the DEDUPED count, so the model is never asked
    for a rung that does not exist.

    `additionalProperties: false` plus a full `required` list is what
    `strict: true` on the OpenAI json_schema wrapper is specified to want, and a
    schema this server will not compile comes back as an in-band error frame
    (DEF376), not a helpful message.
    """
    sizes = sorted({round(r.size_pct, 1) for r in rows})
    text = {"type": "string", "minLength": 1, "maxLength": RISK_CASE_MAX_CHARS}
    number = {"type": "string", "minLength": 1, "maxLength": RISK_KEY_NUMBER_MAX_CHARS}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["options", "recommended", "confidence", "decisive_number"],
        "properties": {
            "options": {
                "type": "array",
                "minItems": len(sizes),
                "maxItems": len(sizes),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["size_pct", "case_for", "case_against", "key_number"],
                    "properties": {
                        "size_pct": {"type": "number", "enum": sizes},
                        "case_for": dict(text),
                        "case_against": dict(text),
                        "key_number": dict(number),
                    },
                },
            },
            "recommended": {"type": "number", "enum": sizes},
            "confidence": {"type": "string", "enum": list(RISK_CONFIDENCE_ENUM)},
            "decisive_number": dict(number),
        },
    }


def _options_by_size(payload: dict[str, Any]) -> dict[float, dict[str, Any]]:
    """The payload's options keyed by their claimed size, one decimal.

    Only sizes that parse as numbers get a key at all; everything else is
    ignored here and — because every renderer iterates the LADDER's rows, never
    this dict — an invented or garbled size can never reach a reader.
    """
    by_size: dict[float, dict[str, Any]] = {}
    for opt in payload.get("options") or []:
        try:
            by_size[round(float(opt.get("size_pct")), 1)] = opt
        except (TypeError, ValueError):
            continue
    return by_size


def render_risk_assessment(payload: dict[str, Any], rows: list[LadderOption]) -> str:
    """The officer's structured output, as the block the CIO reads.

    Rendered from the parsed object rather than passed through as JSON so the CIO
    reads it the way it reads every other contribution, and so a malformed or partial
    reply degrades to fewer rows rather than to a wall of braces.

    Sizes come from `rows`, never from the payload: a model that echoed back a size we
    did not offer would otherwise smuggle an unpriced option onto the menu.
    """
    by_size = _options_by_size(payload)

    lines = ["## Risk assessment — sized options with the case each way", ""]
    for r in rows:
        opt = by_size.get(round(r.size_pct, 1))
        head = f"- **{r.size_pct:.1f}%**"
        if r.contribution_pts is not None:
            head += f" (≈ {r.contribution_pts:.2f} pt of drawdown"
            if r.headroom_after_pts is not None:
                head += f", {r.headroom_after_pts:.2f} pt of cap left"
            head += ")"
        lines.append(head)
        if not opt:
            lines.append("  - the Risk Officer did not assess this size")
            continue
        for label, key in (("For", "case_for"), ("Against", "case_against")):
            val = str(opt.get(key) or "").strip()
            if val:
                lines.append(f"  - {label}: {val}")
        kn = str(opt.get("key_number") or "").strip()
        if kn:
            lines.append(f"  - Key figure: {kn}")

    rec, conf = payload.get("recommended"), str(payload.get("confidence") or "").strip()
    if rec is not None or conf:
        tail = "\nRisk Officer's call:"
        if rec is not None:
            try:
                tail += f" **{float(rec):.1f}%**"
            except (TypeError, ValueError):
                pass
        if conf:
            tail += f" · confidence {conf}"
        dn = str(payload.get("decisive_number") or "").strip()
        if dn:
            tail += f" · decided by {dn}"
        lines.append(tail)

    lines.append(
        "\nThese are options, not instructions. You may land between them if the "
        "evidence puts you there, and the mandate's ceilings and the safety floor "
        "still bind whatever you choose."
    )
    return "\n".join(lines)


# ── CR201: the three display voices, rendered from the one structured reply ──
#
# Which rung each voice presents. The mapping preserves what each AgentId has
# always meant on screen — the Aggressive presents the largest size, the
# Conservative the smallest, the Balanced the reference — so the comb, the SSE
# stream and the Journal replay keep their three risk voices while the LLM makes
# exactly one call. Keyed on the ladder's own labels so a change to the ladder's
# shape fails loudly here instead of rendering a voice from the wrong rung.
_VOICE_FOR_RUNG_LABEL: dict[str, AgentId] = {
    "press": AgentId.AGGRESSIVE_DEBATOR,
    "trim": AgentId.CONSERVATIVE_DEBATOR,
    "reference": AgentId.NEUTRAL_DEBATOR,
}

# Emission order — the same order the RISK phase has always spoken in
# (`room_runner.PHASES`), so clients see an unchanged stream shape.
RISK_TURN_ORDER: tuple[AgentId, ...] = (
    AgentId.AGGRESSIVE_DEBATOR,
    AgentId.CONSERVATIVE_DEBATOR,
    AgentId.NEUTRAL_DEBATOR,
)

_CONFIDENCE_VALUES = frozenset({"low", "medium", "high"})


@dataclass(frozen=True)
class RenderedRiskTurn:
    """One display turn built in code from the officer's payload + the ladder.

    `stance`/`conviction`/`headline`/`argued_size_pct` are the same channels the
    parsed stance envelope used to fill — derived now, not parsed, which is what
    makes the DEF247/DEF251/DEF257 class unreachable on this path.
    """

    agent_id: AgentId
    text: str
    stance: str | None
    conviction: str | None
    headline: str | None
    argued_size_pct: float | None


def _rung_head(r: LadderOption) -> str:
    """The rung's computed figures, in `render_risk_assessment`'s exact shape —
    ladder values only, so no formatter exists that could render a payload
    number."""
    head = f"**{r.size_pct:.1f}%** of portfolio"
    if r.contribution_pts is not None:
        head += f" (≈ {r.contribution_pts:.2f} pt of drawdown"
        if r.headroom_after_pts is not None:
            head += f", {r.headroom_after_pts:.2f} pt of cap left"
        head += ")"
    return head


def _capped_headline(candidate: Any, max_chars: int) -> str | None:
    """Nulled when over, never truncated — the same rule the envelope path
    applies (`STANCE_HEADLINE_MAX_CHARS`): a cut assertion can invert itself."""
    text = str(candidate or "").strip()
    if not text or len(text) > max_chars:
        return None
    return text


def render_officer_turns(
    payload: dict[str, Any] | None,
    rows: list[LadderOption],
    *,
    headline_max_chars: int,
    fallback_reason: str | None = None,
) -> list[RenderedRiskTurn]:
    """The three risk-phase display turns, rendered with no LLM involved.

    Every figure comes from `rows` — the same ladder the officer's prompt fixed
    — never from the payload: a size the model invented has no rung and is
    dropped, a rung it skipped renders as "did not assess" rather than
    vanishing, and the recommended size only renders when it matches a rung.

    Interim stance mapping (CR201 §2.3, the measured-as-built schema — the
    per-option `lean` is deliberately NOT shipped): the voice whose rung equals
    `recommended` carries the officer's endorsement ("for"), the other assessed
    voices carry "neutral", a skipped rung carries None (the comb's gutter —
    None never means neutral), and conviction on assessed voices comes from
    `confidence`.

    `fallback_reason` set means the officer call failed or did not parse: the
    turns render the computed ladder alone — the measured 11.8% floor, vs 7.4%
    for nothing — and each carries an `[AMI …]` mark saying so (CR040: a
    fallback that fires silently teaches the user the debate happened).
    """
    by_size = _options_by_size(payload or {})
    confidence = str((payload or {}).get("confidence") or "").strip().lower()
    if confidence not in _CONFIDENCE_VALUES:
        confidence = ""
    recommended_rung: LadderOption | None = None
    try:
        rec = round(float((payload or {}).get("recommended")), 1)
        recommended_rung = next(
            (r for r in rows if round(r.size_pct, 1) == rec), None
        )
    except (TypeError, ValueError):
        recommended_rung = None

    turns: dict[AgentId, RenderedRiskTurn] = {}
    for r in rows:
        voice = _VOICE_FOR_RUNG_LABEL[r.label]
        head = _rung_head(r)

        if fallback_reason is not None:
            text = (
                f"[AMI: the Risk Officer's structured assessment was unavailable "
                f"({fallback_reason}). This sized option is AMI's computed ladder, "
                f"shown without the officer's reasoning.]\n"
                f"The {r.label} option: {head}."
            )
            turns[voice] = RenderedRiskTurn(voice, text, None, None, None, None)
            continue

        opt = by_size.get(round(r.size_pct, 1))
        if not opt:
            text = (
                f"From the Risk Officer's structured assessment — the {r.label} "
                f"option, {head}:\n- the Risk Officer did not assess this size."
            )
            turns[voice] = RenderedRiskTurn(voice, text, None, None, None, None)
            continue

        lines = [
            f"From the Risk Officer's structured assessment — the {r.label} "
            f"option, {head}:"
        ]
        for label, key in (("Case for", "case_for"), ("Case against", "case_against")):
            val = str(opt.get(key) or "").strip()
            if val:
                lines.append(f"- {label}: {val}")
        kn = str(opt.get("key_number") or "").strip()
        if kn:
            lines.append(f"- Key figure: {kn}")

        is_recommended = recommended_rung is not None and r.label == recommended_rung.label
        headline_source: Any = opt.get("key_number")
        if is_recommended:
            headline_source = (payload or {}).get("decisive_number") or headline_source
        if voice is AgentId.NEUTRAL_DEBATOR:
            call = ""
            if recommended_rung is not None:
                call = f"\nRisk Officer's call: **{recommended_rung.size_pct:.1f}%**"
                if confidence:
                    call += f" · confidence {confidence}"
                dn = str((payload or {}).get("decisive_number") or "").strip()
                if dn:
                    call += f" · decided by {dn}"
            lines.append(
                f"{call}\nThese are options, not instructions. The Chief "
                f"Investment Officer may land between them if the evidence puts "
                f"them there, and the mandate's ceilings and the safety floor "
                f"still bind whatever they choose."
            )

        turns[voice] = RenderedRiskTurn(
            agent_id=voice,
            text="\n".join(lines),
            stance="for" if is_recommended else "neutral",
            conviction=confidence or None,
            headline=_capped_headline(headline_source, headline_max_chars),
            argued_size_pct=r.size_pct,
        )

    missing = [v.value for v in RISK_TURN_ORDER if v not in turns]
    if missing:
        # Degrade loudly (CR040): a ladder that stopped producing all three
        # labelled rungs is a programming error, not a runtime case to render
        # around — two voices where clients expect three is DEF084's shape.
        raise ValueError(f"option ladder did not produce every voice: {missing}")
    return [turns[v] for v in RISK_TURN_ORDER]
