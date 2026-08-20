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

from typing import Any

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


def render_risk_assessment(payload: dict[str, Any], rows: list[LadderOption]) -> str:
    """The officer's structured output, as the block the CIO reads.

    Rendered from the parsed object rather than passed through as JSON so the CIO
    reads it the way it reads every other contribution, and so a malformed or partial
    reply degrades to fewer rows rather than to a wall of braces.

    Sizes come from `rows`, never from the payload: a model that echoed back a size we
    did not offer would otherwise smuggle an unpriced option onto the menu.
    """
    by_size = {}
    for opt in payload.get("options") or []:
        try:
            by_size[round(float(opt.get("size_pct")), 1)] = opt
        except (TypeError, ValueError):
            continue

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
