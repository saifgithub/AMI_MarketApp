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

CR219 R59-F2 — the one hole in the claim above. `key_number` and `decisive_number`
are the exception to "the model never emits a computed number": they are LLM free
strings, explicitly asked to be "a quotation from the fact sheet" (see
`build_risk_officer_instruction`), but nothing enforced that they actually are one.
Both are rendered verbatim and `decisive_number` is promoted into the comb headline
— the single most-read string on the risk hexes — so an officer that "quotes" a
figure it silently recomputed and got wrong would look exactly as authoritative as
the genuinely-computed rung figures beside it.

`_quotation_check()` closes that gap at render time, when the fact sheet
(`profile`) and the ladder (`rows`) are both already in hand: every numeral found in
`key_number`/`decisive_number` must appear, under the normalization rule below, in
either the sheet's own numeric fields or one of the ladder's own rung figures. A
string with no numerals at all (a pure-words key_number, e.g. "guidance was raised
last quarter") is not a miss — there is nothing to corroborate, so it renders as
asked.

**Normalization rule** (tolerates the formatting variance real replies use):
strip currency symbols (`$£€`) and thousands separators (`,`), strip a trailing
`%`, and resolve a trailing magnitude letter (`K`/`M`/`B`/`T`, case-insensitive) to
its multiplier (1e3/1e6/1e9/1e12) applied to the figure that precedes it — so
`"1,234.5"`, `"1234.50"`, `"$1.2B"`, `"4.06%"` and bare `"4.06"` all parse to a
single float. A claim is then corroborated against a sheet/ladder value by
ROUNDING the corroborating value to the same decimal precision the claim itself
stated (after undoing any magnitude suffix) and checking for an exact match —
`"$1.2B"` (1 decimal, ×1e9) corroborates a sheet `market_cap` of `1_234_000_000`
because `round(1_234_000_000 / 1e9, 1) == 1.2`, and `"4.06%"` corroborates a ladder
`share_of_cap_pct` of `4.0623` because `round(4.0623, 2) == 4.06`. This is
precision-of-the-claim rounding, not a fixed tolerance band, because a suffixed
figure is inherently a rounded human statement and a flat percentage tolerance
would be either too loose on small numbers or too tight on large ones.

**Failure posture (degrade loudly, never a silent pass into the headline).** The
checker never raises past its own call site — an internal error (a malformed
`rows`/`profile`, an unexpected type) is caught and treated as UNVERIFIED, the same
outcome as a genuine numeral mismatch: the body gets the `[AMI: unverifiable]`
annotation and the string is demoted from the headline slot. The alternative
(treat a checker error as untouched-and-trusted) is exactly the DEF059 "confident
fake" shape CLAUDE.md's degrade-loudly rule exists to forbid — a broken checker
must never look like a passed one.

**On by default — this is a fix, not an opt-in feature.** `render_risk_assessment`
and `render_officer_turns` run the check unconditionally; there is no flag that
turns it off. A default-off check would be exactly the CR040 shape this whole
audit is chasing: a control that exists, is fully built and tested, and never
actually runs on the path a real user reads — the registry in
`app.services.numeric_provenance` would keep recording `key_number`/
`decisive_number` as `LLM_UNVERIFIED` forever, a permanently-dark feature
indistinguishable from no fix at all. `profile` (the fact sheet) is an optional
argument — its caller inside `room_runner.py` does not thread `ctx.profile`
through yet, and omitting it still runs the check in ladder-only mode rather
than skipping it, because ladder-only corroboration is real coverage, not a
placeholder for coverage. The pre-existing CR197/CR201 fixtures that used to
quote unverifiable placeholder figures (`"RSI 43"`, `"RSI 58"`) were updated in
the same commit as this check to quote a real, corroborable figure instead —
per the module's own promise two paragraphs up, a string that is not a
quotation is exactly the thing this check exists to catch, including in a test
fixture.
"""

from __future__ import annotations

import re
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

    def _rung(size: float) -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["size_pct", "case_for", "case_against", "key_number"],
            "properties": {
                # Pinned to ONE value, per position — see the prefixItems note.
                "size_pct": {"type": "number", "enum": [size]},
                "case_for": dict(text),
                "case_against": dict(text),
                "key_number": dict(number),
            },
        }

    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["options", "recommended", "confidence", "decisive_number"],
        "properties": {
            "options": {
                "type": "array",
                "minItems": len(sizes),
                "maxItems": len(sizes),
                # `prefixItems` — one position per rung, each pinned to a single
                # size — rather than one shared `enum` across a 3-slot array.
                #
                # MEASURED, and it is the whole reason this is not the obvious
                # shape. The shared-enum version was run over the 69 held-out S6
                # prompts on 2026-08-27 and scored `one_per_size` **50/69 (72%)**
                # against an UNCONSTRAINED baseline of **69/69 (100%)**: the
                # grammar pinned the count and the vocabulary but nothing forbade
                # repeating a value, and the model emitted `[0.5, 1.5, 1.5]` in 19
                # of 69. Constraining the decoder had REMOVED an inductive bias
                # the model already had and given nothing back — a grammar that
                # made the surface worse.
                #
                # Per-position pinning makes one-entry-per-size structural rather
                # than requested, which is what `build_risk_officer_instruction`'s
                # "exactly one entry per size, for these sizes and no others" has
                # been asking for in prose all along.
                #
                # `prefixItems` (draft 2020-12) verified working on this build.
                # The draft-07 tuple form (`"items": [ … ]`) is NOT a fallback:
                # it returns HTTP 500 "EngineCore encountered an issue".
                "prefixItems": [_rung(s) for s in sizes],
            },
            "recommended": {"type": "number", "enum": sizes},
            "confidence": {"type": "string", "enum": list(RISK_CONFIDENCE_ENUM)},
            "decisive_number": dict(number),
        },
    }


# ── CR219 R59-F2: is a `key_number`/`decisive_number` really a quotation? ────
#
# See the module docstring for the normalization rule and the failure posture.
# This section is self-contained: no caller outside this module needs to know
# how a numeral is extracted or matched, only the yes/no `_quotation_check()`
# returns.

_UNVERIFIABLE_MARK = "[AMI: unverifiable]"

# One magnitude letter, directly after the digits (optionally through a
# trailing space) — "1.2B", "1.2 B". Case-insensitive: a model is as likely to
# write "b" as "B". Order matters (longest common prefix first is irrelevant
# here since each is one char), kept as a plain dict for a single lookup.
_MAGNITUDE_MULTIPLIER = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}

# A numeral: optional leading currency sign, digit groups with optional comma
# separators, an optional decimal part, an optional magnitude letter, an
# optional trailing percent. Every group is optional except the digits
# themselves, so this matches the bare "4.06" case too.
#
# The `int` group's alternation ORDER matters: the comma-grouped form
# (`\d{1,3}(?:,\d{3})+`) requires at least one actual `,ddd` group, so a plain
# digit run with no commas ("1234.50") always falls through to the second
# alternative and matches ALL of "1234" rather than the first branch grabbing
# only "123" and leaving "4.50" to be re-matched as a second, spurious
# numeral — verified against exactly that case in the module's tests.
_NUMERAL_RE = re.compile(
    r"[$£€]?"
    r"(?P<int>\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.(?P<frac>\d+))?"
    r"\s?(?P<mag>[kKmMbBtT])?"
    r"(?P<pct>%)?"
)


@dataclass(frozen=True)
class _Numeral:
    """One numeral found in free text, parsed to a comparable float.

    `value` is the fully-resolved figure (magnitude suffix applied) — this is
    what a corroborating value is compared to on the RAW scale (no suffix in
    the claim, e.g. plain "4.06"). `multiplier` is the magnitude scale the
    claim itself applied (1.0 when there was no suffix); `decimals` is how many
    digits after the point the ORIGINAL text stated, i.e. the precision the
    claim committed to IN ITS OWN UNIT — "1.2" in "$1.2B" is 1 decimal of
    BILLIONS, not of raw dollars. Comparison therefore divides the
    corroborating value by `multiplier` before rounding to `decimals`, never
    the other way around — see `_numeral_is_corroborated`.
    """

    raw: str
    value: float
    multiplier: float
    decimals: int


def _extract_numerals(text: str) -> list[_Numeral]:
    """Every numeral in `text`, parsed per the module's normalization rule.

    Returns [] for text with no numerals at all — the caller reads that as
    "nothing to corroborate", not as a miss (a pure-words key_number is fine)."""
    out: list[_Numeral] = []
    for m in _NUMERAL_RE.finditer(text):
        int_part = m.group("int")
        if int_part is None:
            continue
        frac_part = m.group("frac") or ""
        try:
            base = float(f"{int_part.replace(',', '')}.{frac_part or '0'}")
        except ValueError:
            continue
        mag = (m.group("mag") or "").lower()
        multiplier = _MAGNITUDE_MULTIPLIER.get(mag, 1.0)
        out.append(_Numeral(
            raw=m.group(0),
            value=base * multiplier,
            multiplier=multiplier,
            decimals=len(frac_part),
        ))
    return out


def _numeric_leaves(obj: Any, *, _depth: int = 0) -> list[float]:
    """Every `int`/`float` reachable inside `obj` (a dict, list, dataclass-ish
    object, or scalar), skipping `bool` (a `bool` is an `int` subclass in
    Python but is never the kind of figure a sheet quotation would cite).

    Depth-capped defensively — the profile dict is a flat structure with one
    nested `field_state` dict, never deep, but a checker that could recurse
    without bound on unexpected input is exactly the kind of internal error
    the module docstring's failure posture exists to catch, not to trigger."""
    if _depth > 6:
        return []
    if isinstance(obj, bool):
        return []
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, dict):
        leaves: list[float] = []
        for v in obj.values():
            leaves.extend(_numeric_leaves(v, _depth=_depth + 1))
        return leaves
    if isinstance(obj, (list, tuple)):
        leaves = []
        for v in obj:
            leaves.extend(_numeric_leaves(v, _depth=_depth + 1))
        return leaves
    return []


def _corroborating_values(profile: dict[str, Any] | None, rows: list[LadderOption]) -> list[float]:
    """Every figure the officer is entitled to quote: the sheet's own numeric
    fields plus every rung's own computed numerics. `profile` is optional
    (callers that have not threaded the fact sheet through yet still get
    ladder-only verification, never a crash for a missing argument)."""
    values = list(_numeric_leaves(profile)) if profile else []
    for r in rows:
        values.extend(_numeric_leaves({
            "size_pct": r.size_pct,
            "contribution_pts": r.contribution_pts,
            "share_of_cap_pct": r.share_of_cap_pct,
            "headroom_after_pts": r.headroom_after_pts,
            "reward_risk": r.reward_risk,
        }))
    return values


def _numeral_is_corroborated(numeral: _Numeral, corpus: list[float]) -> bool:
    """Does some sheet/ladder figure, rounded to the CLAIM's own precision IN
    THE CLAIM'S OWN UNIT, equal the claim? See the module docstring for why
    this is precision-of-the-claim rounding rather than a fixed tolerance
    band, and `_Numeral`'s docstring for why both sides divide by the claim's
    magnitude multiplier before rounding — `"$1.2B"` is 1 decimal of BILLIONS,
    so a raw `market_cap` of 1_234_000_000 is rounded in billions
    (`1_234_000_000 / 1e9 = 1.234` → `1.2`) before the compare, not rounded on
    the raw dollar scale where a billion-scale figure has no fractional part
    to round away at all."""
    decimals = min(numeral.decimals, 6)  # defensive cap, not a real-world case
    target = round(numeral.value / numeral.multiplier, decimals)
    return any(round(v / numeral.multiplier, decimals) == target for v in corpus)


def _quotation_check(
    text: Any,
    profile: dict[str, Any] | None,
    rows: list[LadderOption],
) -> bool:
    """True when every numeral in `text` is corroborated (including the
    vacuously-true case of no numerals at all). False on a genuine miss OR on
    any internal error — the two cases the module docstring says must render
    identically, because a checker that fails open is a checker that isn't
    one."""
    try:
        s = str(text or "").strip()
        if not s:
            return True
        numerals = _extract_numerals(s)
        if not numerals:
            return True
        corpus = _corroborating_values(profile, rows)
        return all(_numeral_is_corroborated(n, corpus) for n in numerals)
    except Exception:  # noqa: BLE001 — degrade to UNVERIFIED, never crash a render
        return False


def _annotated_if_unverified(
    text: Any,
    profile: dict[str, Any] | None,
    rows: list[LadderOption],
) -> tuple[str, bool]:
    """`(rendered_body_text, verified)`. Runs unconditionally — see the module
    docstring's "on by default" section. Empty text is vacuously verified (no
    quotation to check). A miss earns the `_annotate_rr_against_levels`-style
    loud mark in the body and a False that tells the caller to demote the
    string from any headline/decisive-call slot."""
    s = str(text or "").strip()
    if not s:
        return s, True
    if _quotation_check(s, profile, rows):
        return s, True
    return f"{s} {_UNVERIFIABLE_MARK}", False


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


def render_risk_assessment(
    payload: dict[str, Any],
    rows: list[LadderOption],
    *,
    profile: dict[str, Any] | None = None,
) -> str:
    """The officer's structured output, as the block the CIO reads.

    Rendered from the parsed object rather than passed through as JSON so the CIO
    reads it the way it reads every other contribution, and so a malformed or partial
    reply degrades to fewer rows rather than to a wall of braces.

    Sizes come from `rows`, never from the payload: a model that echoed back a size we
    did not offer would otherwise smuggle an unpriced option onto the menu.

    CR219 R59-F2: `key_number` and `decisive_number` are quotation claims, not
    computed figures (see the module docstring), and are checked UNCONDITIONALLY
    via `_annotated_if_unverified` before they render — a figure the sheet/ladder
    cannot corroborate carries `[AMI: unverifiable]` in the body rather than
    standing unmarked. `profile` is optional — omitting it still gets ladder-only
    verification, never a crash for a missing argument, and never a skipped check.
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
        kn, _ = _annotated_if_unverified(opt.get("key_number"), profile, rows)
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
        dn, _ = _annotated_if_unverified(payload.get("decisive_number"), profile, rows)
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
    number.

    CR219 R59-§13(a): `dollar_risk_usd` renders beside `contribution_pts` when
    (and only when) `build_option_ladder` computed it — a rung built from a
    missing/zero `portfolio_value` carries `None` there, per that function's own
    discipline, and this renders NOTHING for it rather than a fabricated `$0`
    (the `headroom_after_pts` guard just below is the working precedent). Byte-
    identical output on every rung built without a portfolio value, so this is
    additive, not a reformat.
    """
    head = f"**{r.size_pct:.1f}%** of portfolio"
    if r.contribution_pts is not None:
        head += f" (≈ {r.contribution_pts:.2f} pt of drawdown"
        if r.dollar_risk_usd is not None:
            from app.services.room_prompts import _money  # lazy: avoids a cycle

            head += f", {_money(r.dollar_risk_usd)} at risk"
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


def _rung_derived_headline(r: LadderOption) -> str | None:
    """CR219 R59-F2's demotion target: a headline built ONLY from the ladder's
    own computed figures — never a quotation, so it cannot fail verification.
    This is what the comb shows in place of a `key_number`/`decisive_number`
    that missed the check; `None` when the ladder itself carries nothing to
    build one from (a bare size with no priced drawdown), same as any other
    nulled headline."""
    if r.contribution_pts is None:
        return None
    return f"{r.size_pct:.1f}% · {r.contribution_pts:.2f} pt of drawdown"


def render_officer_turns(
    payload: dict[str, Any] | None,
    rows: list[LadderOption],
    *,
    headline_max_chars: int,
    fallback_reason: str | None = None,
    profile: dict[str, Any] | None = None,
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

    CR219 R59-F2: `key_number`/`decisive_number` are checked UNCONDITIONALLY
    (see the module docstring's "on by default") against `profile` (the fact
    sheet, optional — omit it for ladder-only verification) and `rows` before
    they render. A miss gets `[AMI: unverifiable]` in the body and is demoted
    from the `headline` slot in favour of `_rung_derived_headline` — a
    headline built only from the ladder's own computed figures, which cannot
    fail this check because nothing in it was quoted.
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
        kn, kn_verified = _annotated_if_unverified(opt.get("key_number"), profile, rows)
        if kn:
            lines.append(f"- Key figure: {kn}")

        is_recommended = recommended_rung is not None and r.label == recommended_rung.label
        # The candidate for the headline slot, and whether IT (not `kn` above,
        # which may already have been swapped for `decisive_number`) verifies.
        headline_source: Any = opt.get("key_number")
        headline_verified = kn_verified
        if is_recommended:
            dn_candidate = (payload or {}).get("decisive_number")
            if dn_candidate:
                headline_source = dn_candidate
                headline_verified = _quotation_check(dn_candidate, profile, rows)
        if not headline_verified:
            # Demoted: the LLM's quotation missed the check, so the headline
            # slot falls back to a figure nothing ever quoted — see
            # `_rung_derived_headline`'s docstring.
            headline_source = _rung_derived_headline(r)

        if voice is AgentId.NEUTRAL_DEBATOR:
            call = ""
            if recommended_rung is not None:
                call = f"\nRisk Officer's call: **{recommended_rung.size_pct:.1f}%**"
                if confidence:
                    call += f" · confidence {confidence}"
                dn, _ = _annotated_if_unverified(
                    (payload or {}).get("decisive_number"), profile, rows
                )
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
