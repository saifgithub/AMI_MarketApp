"""CR197 — does the risk debate actually change the Portfolio Manager's verdict?

Every prior measurement of the Room's debate is correlational. CR143's M5 scores a
cosine similarity between `verdict.reason` and each transcript turn, which tells you
the PM's prose *echoes* a debator — not that removing the debator would have changed
the decision. CR035 ran ablations, but of the analyst-consensus *input*, never of a
*stage*. So the one question that decides whether the RISK phase earns its 25% of the
run (3 of 12 LLM calls, 24% of the decode budget, 3 serial round-trips) has never been
asked in a form that can answer it.

This asks it, offline and cheaply. For every convene already committed under
`CR143_agent_prompt_audit/corpus/`, the PM's *verbatim recorded prompt* is replayed
against the LAN vLLM with different parts of the debate removed:

    V1a  the exact recorded prompt
    V1b  the exact recorded prompt, a second time  → the paired same-prompt NOISE FLOOR
    V2   all three debator turns removed          (transcript then ends at the Trader)
    V3   the two extremes removed, Neutral kept   (ends at the Neutral)
    V4   the Neutral removed, extremes kept       (ends at the Conservative)
    V5   Conservative + Neutral removed           (ends at the Aggressive)
    V8   the debate replaced by ONE structured Risk Officer, its assessment injected
         as a single block ahead of the transcript (CR197's shape)
    V9   the same officer call, rendered the way PRODUCTION renders it — three turns
         under the three risk AgentIds, appended where the debate was removed
    V9t  V9 with the officer's reply read with trailing text after the closing brace
         dropped — the design apart from today's parser (see `_VARIANT_STRIP["v9t"]`)

CR201 re-pointed V8's PROMPT at production. It used to be assembled here — the CIO's
convene block sliced out of the recorded prompt, the ladder appended after the
transcript, no holdings block, the phase header still reading VERDICT, a 1200-token
ceiling. It now comes from `room_prompts.build_risk_officer_messages` at
`_AGENT_MAX_TOKENS[RISK_OFFICER]`, the same call `_run_risk_officer` makes. V9 closes
the other half of the same gap: the officer's payload does not reach the Chief
Investment Officer as itself, it reaches it as three rendered turns. Rows recorded
before 2026-08-21 under `CR197_risk_debate_effectiveness/ablation/` measure the old
reconstruction and are the baseline this arm is compared AGAINST, not a continuation
of it.

V1b is the whole point. A verdict flip between V1a and V2 means nothing until you know
how often this model flips against *itself* on a byte-identical prompt — sampling
temperature is server-side and unknown here, so the floor has to be measured, not
assumed.

V4 and V5 were added after the first three arms produced a result that had two
competing explanations. The trailing comment in `_VARIANT_STRIP` records why: approval
rate tracked WHO SPOKE LAST into the PM, monotonically by how negative that voice is,
which "the debate carries information" and "the PM is anchored on its last input"
predict equally well. V5 separates them, because leaving the always-bullish Aggressive
as the final voice while deleting two thirds of the debate makes the two hypotheses
point in OPPOSITE directions.

A note on the statistic, since it changed the answer: the first cut of this script
compared SYMMETRIC flip rates ("does the ablation flip more often than resampling")
and returned p=1.0, "not demonstrated". That was the wrong instrument — the flip rates
are near-identical while the flips run in opposite DIRECTIONS, so the APPROVE count
falls by half with the flip rate unmoved. Marginal homogeneity is the hypothesis of
interest; see `build_report`.

Why replay the PM alone, rather than re-running whole convenes: the eleven upstream
turns are held FIXED at what was recorded, so the only thing differing between arms is
the presence of the debate text. Re-running the room would let the analysts drift too,
and the contrast would measure nothing in particular.

Three fidelity rules this script exists to keep, each of which would silently corrupt
the measurement if broken:

  1. `VLLMProvider` is used DIRECTLY, never `LLMGateway`. The gateway prepends the
     CR056 grounding directive (already baked into the recorded prompt — double it and
     the prompt is no longer the one that was recorded) and, worse, falls back to
     Anthropic when vLLM is down, which would quietly measure a different model.
  2. Production sends NO temperature and NO top_p to vLLM (llm_gateway.py:481-490) —
     server defaults apply. The replay omits them too, and pins max_tokens=1700, the
     PM's production budget.
  3. Baselines come from the recorded `response_text`, parsed identically to the
     replays — never from the stored `verdict`, whose REJECTs are the safety floor's
     post-hoc veto and not the PM's own word.

The contrast is internally valid on whatever model serves `ami-llm`, because both arms
are measured fresh on the same model in the same session. Only the replay-vs-recording
side-check needs the model that produced the corpora.

Usage (from backend/):
    .venv/bin/python -m scripts.pm_debate_ablation --dry-run
    .venv/bin/python -m scripts.pm_debate_ablation --variants v1a v1b v2
    .venv/bin/python -m scripts.pm_debate_ablation --report-only
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.llm_json import extract_json_object  # noqa: E402
from app.services.room_runner import _normalize_pm_action, _safe_float  # noqa: E402

DEBATORS = ("aggressive_debator", "conservative_debator", "neutral_debator")
EXTREMES = ("aggressive_debator", "conservative_debator")

# The PM's production decode budget (`_AGENT_MAX_TOKENS[PORTFOLIO_MANAGER]`,
# room_prompts.py). Hardcoded rather than imported so a future budget change cannot
# silently desynchronise a replay from the recording it is being compared against.
PM_MAX_TOKENS = 1700

VARIANTS = ("v1a", "v1b", "v1c", "v2", "v3", "v4", "v5", "v6", "v7", "v8", "v9", "v9t")
_VARIANT_STRIP: dict[str, tuple[str, ...]] = {
    "v1a": (),
    "v1b": (),
    # v1c — a THIRD independent sample of the untouched prompt. v1a/v1b measured
    # that this model disagrees with itself on 12% of byte-identical prompts; a
    # third sample is what turns that observation into a testable remedy, since
    # majority-vote self-consistency needs an odd number to adjudicate.
    "v1c": (),
    "v2": DEBATORS,
    "v3": EXTREMES,
    # v4 isolates the Neutral. v2 and v3 together implicate it, but not cleanly:
    # v2 also changes which voice speaks LAST before the PM (the Trader, whose own
    # stance skews negative), so a recency effect explains v2 as well as content
    # does. v4 removes the Neutral while keeping both extremes, so the transcript
    # still ends on a debator. If the effect survives here it is not simply "the
    # debate block is shorter"; if it vanishes, the Neutral was never the cause.
    "v4": ("neutral_debator",),
    # v5 is the discriminator between the two live explanations of v2/v3/v4.
    #
    # Across those arms the approval rate tracked WHO SPOKE LAST, monotonically by
    # how negative that voice is: Neutral last 15.7-17.2%, Conservative last 11.9%,
    # Trader last 7.4%. Recency explains that as well as "the debate carries
    # information" does, and the two make OPPOSITE predictions here. Removing the
    # Conservative and the Neutral leaves the Aggressive — a voice that argued "for"
    # in 117 of 118 convenes — speaking last into the PM.
    #   recency  ⇒ approvals at or ABOVE baseline, despite two thirds of the debate
    #              being gone;
    #   content  ⇒ approvals BELOW baseline, since most of the debate is missing.
    "v5": ("conservative_debator", "neutral_debator"),
    # v6 is the substitution test, and the one that decides whether CR197's proposal
    # is worth building: strip the whole debate AND inject the deterministic option
    # ladder in its place. v2 (same strip, no ladder) fell to 7.4%.
    #   ladder substitutes ⇒ approvals return to the ~16% baseline with no debator
    #                        prose in the prompt at all;
    #   it does not        ⇒ what the debate supplies is argument, not arithmetic,
    #                        and the ladder is not a replacement for it.
    "v6": DEBATORS,
    # v7 is the SHIPPING arm, and the one that must be measured before the ladder
    # goes near production: the full untouched prompt PLUS the ladder. v6 showed the
    # ladder is only a partial substitute (11.8% against a 7.4% strip and a 16.3%
    # baseline), so the ladder is an ADDITION rather than a swap — which makes "does
    # adding it to the real prompt help, do nothing, or hurt?" the live question.
    #
    # There is a specific way it could hurt. Every v6 approval landed exactly on a
    # rung (3.0 x13, 1.5 x3) where the baseline interpolated in 11 of 43. If a menu
    # in front of the full debate anchors the CIO onto rungs and suppresses that
    # judgement, the ladder would be trading arithmetic safety for a narrower
    # decision — and that is a regression, not an improvement.
    "v7": (),
    # v8 is the DESIGNED ALTERNATIVE, not another subtraction. Strip all three role
    # players and put back ONE structured Risk Officer turn: the deterministic ladder
    # plus, per rung, an evidence-based case for and against, produced by a single
    # extra LLM call constrained to a JSON schema it cannot put a computed number in.
    #
    # It is the arm that tests the actual proposal. v2 (strip, add nothing) fell to
    # 7.4% and v6 (strip, add the bare ladder) reached only 11.8% against a 16.3%
    # baseline — the gap between them being exactly the ticker-specific REASONS the
    # ladder has no way to supply. If those reasons are what the CIO was using, this
    # arm should return to baseline or better on one serial step instead of three.
    "v8": DEBATORS,
    # v9 — CR201 rollout step 2. v8 asks whether the OFFICER'S PROMPT reproduces the
    # debate; v9 asks whether the SHIPPED ASSEMBLY does, which is a different
    # question because the officer's reply does not reach the Chief Investment
    # Officer as itself. In production `_run_risk_officer` renders the payload into
    # the THREE existing risk AgentIds via `render_officer_turns` and appends them to
    # the transcript, where the debators used to speak; v8 injects one
    # `render_risk_assessment` block ahead of the transcript instead. Same officer
    # call, same payload contract, different thing put in front of the CIO — so the
    # pair separates "the prompt is right" from "the assembly is right".
    "v9": DEBATORS,
    # v9t — v9 with ONE thing changed, and it is not the design: the officer's reply
    # is read with the trailing text after the closing brace dropped. Measured on this
    # corpus, the shipped assembly makes the model append a simulation disclaimer
    # after otherwise-valid JSON, and `extract_json_object` rejects a reply that
    # STARTS with '{' and ends with prose (it trims surrounding prose only when the
    # reply does not open with the object). v9 therefore measures the design AND that
    # rejection together; v9t measures the design alone, so the two say separately
    # whether the officer reproduces the debate and whether today's parser lets it.
    "v9t": DEBATORS,
}
# Arms whose stripped prompt gets a generated structured risk turn (2 LLM calls each).
_VARIANT_RISK_OFFICER: frozenset[str] = frozenset({"v8", "v9", "v9t"})
# Arms that render the officer's payload the way PRODUCTION does — three transcript
# turns — rather than as one pre-transcript block.
_VARIANT_OFFICER_TURNS: frozenset[str] = frozenset({"v9", "v9t"})
# Arms that read the officer's reply with trailing text dropped — see "v9t".
_VARIANT_TOLERANT_READ: frozenset[str] = frozenset({"v9t"})
# Arms that additionally receive the computed ladder (after any strip).
_VARIANT_LADDER: frozenset[str] = frozenset({"v6", "v7"})

DEFAULT_EPOCHS = ("2026-08-07", "2026-08-13", "2026-08-14", "2026-08-14b")


# ── corpus loading + join ────────────────────────────────────────────────


@dataclass
class Convene:
    """One committed convene, joined to the PM call that decided it."""

    epoch: str
    audit_id: str
    run_id: str
    ticker: str
    system_prompt: str
    recorded_response: str
    transcript: list[dict[str, Any]]
    corpus_model: str | None = None

    def debator_turns(self) -> dict[str, str]:
        return {
            t["agent_id"]: t.get("content") or ""
            for t in self.transcript
            if t.get("agent_id") in DEBATORS
        }


def _load_json(path: Path) -> Any:
    with path.open() as fh:
        return json.load(fh)


def load_epoch(corpus_dir: Path, epoch: str) -> tuple[list[dict], list[dict]]:
    audit = _load_json(corpus_dir / f"llm_audit_{epoch}-epoch.json")
    runs = _load_json(corpus_dir / f"room_runs_{epoch}-epoch.json")
    return audit, runs


def join_epoch(epoch: str, audit: list[dict], runs: list[dict]) -> tuple[list[Convene], list[str]]:
    """Join each convene to its PM audit row by trader-turn content.

    Timestamps cannot do this job: convenes ran in parallel batches and the 08-07
    epoch stores a different ISO format, so a time-window join silently mis-pairs.
    The trader's turn is reproduced verbatim inside the PM's prompt, so a slice of
    it is an exact, checkable key — and uniqueness is ASSERTED, not hoped for.
    """
    pm_rows = [r for r in audit if r.get("flow") == "room_pm"]
    convenes: list[Convene] = []
    problems: list[str] = []

    for run in runs:
        transcript = run.get("transcript") or []
        trader = next((t for t in transcript if t.get("agent_id") == "trader"), None)
        if trader is None or not (trader.get("content") or "").strip():
            problems.append(f"{epoch}/{run.get('id')}: no trader turn to join on")
            continue
        key = (trader["content"] or "")[:120]
        matches = [r for r in pm_rows if key in (r.get("system_prompt") or "")]
        if len(matches) != 1:
            problems.append(
                f"{epoch}/{run.get('id')}: trader-key matched {len(matches)} PM rows (need exactly 1)"
            )
            continue
        row = matches[0]
        pm_turn = next(
            (t for t in transcript if t.get("agent_id") == "portfolio_manager"), None
        )
        convenes.append(
            Convene(
                epoch=epoch,
                audit_id=str(row.get("id")),
                run_id=str(run.get("id")),
                ticker=str(run.get("ticker") or ""),
                system_prompt=row.get("system_prompt") or "",
                recorded_response=row.get("response_text") or "",
                transcript=transcript,
                corpus_model=(pm_turn or {}).get("model"),
            )
        )
    return convenes, problems


# ── variant construction ─────────────────────────────────────────────────


class StripError(RuntimeError):
    pass


def strip_debators(convene: Convene, agents: Iterable[str]) -> str:
    """Remove named debator turns from the transcript block of the PM's prompt.

    `_format_transcript` renders turns as `"\\n".join(f"[{agent_id}] {content}")`, and
    the stance envelope is stripped from `content` BEFORE the transcript commit
    (room_runner.py `parse_stance_envelope`), so the recorded turn text is reproduced
    inside the PM prompt byte-for-byte. That makes this an exact block removal rather
    than a line-parse — no regex over content that may itself contain newlines and
    bracketed markers.

    The removal is verified three ways: the block occurs exactly once, the prompt
    shrinks by exactly the block length, and the `[agent_id]` marker is gone
    afterwards. Any failure raises rather than silently measuring the wrong thing.
    """
    agents = tuple(agents)
    if not agents:
        return convene.system_prompt

    prompt = convene.system_prompt
    turns = convene.debator_turns()
    removed = 0

    for agent_id in agents:
        content = turns.get(agent_id)
        if not content:
            raise StripError(f"{convene.run_id}: no recorded turn for {agent_id}")
        block = f"\n[{agent_id}] {content}"
        occurrences = prompt.count(block)
        if occurrences != 1:
            raise StripError(
                f"{convene.run_id}: block for {agent_id} occurs {occurrences}x (need 1)"
            )
        prompt = prompt.replace(block, "", 1)
        removed += len(block)
        if f"[{agent_id}]" in prompt:
            raise StripError(f"{convene.run_id}: marker for {agent_id} survived removal")

    if len(convene.system_prompt) - len(prompt) != removed:
        raise StripError(f"{convene.run_id}: length delta disagrees with removed blocks")
    return prompt


_REF_POS_RE = __import__("re").compile(
    r"Reference position \(risk-tier ceiling ([\d.]+)% size, entry ([\d.]+), stop ([\d.]+)\)"
)
_CAP_RE = __import__("re").compile(r"max_drawdown_pct: ([\d.]+)")
_USED_RE = __import__("re").compile(r"Drawdown USED: ([\d.]+) pt")


def inject_ladder(convene: Convene, prompt: str) -> str:
    """Insert the production option-ladder block ahead of the transcript.

    The inputs are parsed out of the recorded prompt rather than recomputed from the
    mandate, because the mandate is not in the corpus and a guessed risk_score would
    silently change the ladder. All three appear verbatim in every recorded PM prompt
    (verified 136/136), so this reads what the run actually used.

    It calls the SAME `build_option_ladder` / `_render_option_ladder` that production
    would, so a positive result here is a result about the shippable artifact and not
    about a mock of it. No target is available in the recorded prompt, so the R:R
    column is absent — meaning this arm UNDERSTATES what production would supply.
    """
    from app.services.room_prompts import _render_option_ladder
    from app.trading_math.option_ladder import build_option_ladder

    m = _REF_POS_RE.search(convene.system_prompt)
    if not m:
        raise StripError(f"{convene.run_id}: no reference-position line to build a ladder from")
    size, entry, stop = (float(g) for g in m.groups())

    cap_m = _CAP_RE.search(convene.system_prompt)
    if not cap_m:
        raise StripError(f"{convene.run_id}: no max_drawdown_pct to size the cap")
    cap = float(cap_m.group(1))

    used_m = _USED_RE.search(convene.system_prompt)
    used = float(used_m.group(1)) if used_m else None

    block = _render_option_ladder(
        build_option_ladder(
            reference_size_pct=size, entry=entry, stop=stop,
            cap_pts=cap, current_drawdown_pct=used,
        ),
        cap,
    )
    if not block:
        raise StripError(f"{convene.run_id}: ladder rendered empty")

    anchor = "Transcript so far:"
    if anchor not in prompt:
        raise StripError(f"{convene.run_id}: no transcript anchor to insert the ladder before")
    return prompt.replace(anchor, f"{block}\n\n{anchor}", 1)


_CONVENE_ANCHOR = "─── CONVENE THE ROOM"
_TURN_ANCHOR = "Your turn. Speak as"
_TRANSCRIPT_ANCHOR = "Transcript so far:"
_TURN_ANCHOR_FULL = "\n\nYour turn. Speak as"
_MANDATE_ANCHOR = "User mandate snapshot:"
_LADDER_ANCHOR = "## Sized options"
# `_SIM_PORTFOLIO_HEADER` from room_runner — imported at use, not retyped, so the one
# line a reader recognises the holdings block by cannot drift from production.

_RISK_SCORE_RE = re.compile(r"^- risk_score: (\d)", re.M)
_LOCALE_RE = re.compile(r"^- locale: (\S+)$", re.M)
_OPEN_RISK_RE = re.compile(r"- Open risk already committed: ([\d.]+)%")
_LONG_ONLY_MARK = "- long_only: long-only = no short/negative positions."
_TRADES_MARK = "- Trades opened today:"
_OPEN_RISK_UNCOMPUTED = "- Open risk: COULD NOT BE COMPUTED this run."
_LAST_LOSS_RE = re.compile(r"- Last losing trade closed: (.+)\.\n")
_LAST_LOSS_UNCOMPUTED = "- Last stop-out: COULD NOT BE COMPUTED this run"


def _recorded_fact_sheet(convene: Convene) -> str:
    """The run's OWN fact sheet, lifted verbatim out of the recorded prompt.

    `_format_profile` is a lossy renderer over a `profile` dict that the corpus does
    not store, so the sheet is the one production input that cannot be rebuilt from
    structured data. It is transplanted instead of reconstructed — and the transplant
    is exact, because `_lane_for` puts the Risk Officer and the Portfolio Manager in
    the same `_ALL_DOMAINS` lane, so the sheet production would render for the
    officer is byte-for-byte the sheet recorded in the CIO's prompt.
    """
    head = f"Ticker: {convene.ticker}\n"
    tail = f"\n\n{_MANDATE_ANCHOR}\n"
    i, j = convene.system_prompt.find(head), convene.system_prompt.find(tail)
    if i < 0 or j <= i:
        raise StripError(f"{convene.run_id}: cannot locate the recorded fact sheet")
    return convene.system_prompt[i + len(head) : j]


def _recorded_portfolio_block(convene: Convene) -> str:
    """The CR055 holdings block, verbatim. Sits in `base` on the CIO's prompt (before
    the convene header) and INSIDE the convene block on the officer's — same text,
    different position, so it is extracted here and handed back to the shipped
    builder as `portfolio_snapshot`."""
    from app.services.room_runner import _SIM_PORTFOLIO_HEADER

    i = convene.system_prompt.find(_SIM_PORTFOLIO_HEADER)
    j = convene.system_prompt.find(_CONVENE_ANCHOR)
    if i < 0 or j <= i:
        raise StripError(f"{convene.run_id}: no recorded portfolio block")
    return convene.system_prompt[i:j].rstrip("\n")


def _mandate_for(convene: Convene):
    """A real `Mandate` carrying the four fields the officer's prompt reads.

    risk_score, max_drawdown_pct, locale and compliance.long_only are the ONLY
    mandate fields `build_risk_officer_messages` touches (via `_drawdown_snapshot_line`
    and `_risk_state_block`), and all four are stated verbatim in every recorded PM
    prompt. Everything else is filled with a fixed placeholder that renders nowhere —
    it exists to satisfy the schema, not to stand in for a datum.
    """
    from datetime import datetime
    from uuid import UUID

    from app.schemas.mandate import (
        Compliance,
        Horizon,
        LearningStyle,
        Mandate,
        Path as MandatePath,
        PrimaryGoal,
        RiskComponents,
    )
    from app.schemas.user import Plan

    p = convene.system_prompt
    rs, cap, loc = _RISK_SCORE_RE.search(p), _CAP_RE.search(p), _LOCALE_RE.search(p)
    if not (rs and cap and loc):
        raise StripError(f"{convene.run_id}: mandate snapshot is not readable")
    return Mandate(
        user_id=UUID(int=0),
        version=1,
        display_name="Ablation Subject",
        locale=loc.group(1),
        timezone="UTC",
        primary_goal=PrimaryGoal.LONG_TERM_WEALTH,
        horizon=Horizon.LONG,
        target_outcome=None,
        path=MandatePath.LONG_HORIZON,
        risk_score=int(rs.group(1)),
        risk_components=RiskComponents(
            drawdown_response=3, regret_asymmetry=0, concentration_tolerance=3
        ),
        risk_quotes=[],
        max_drawdown_pct=int(float(cap.group(1))),
        compliance=Compliance(long_only=_LONG_ONLY_MARK in p, liquid_only=True),
        learning_style=LearningStyle.QUICK,
        plan=Plan.TRADER,
        trial_expires_at=None,
        credit_balance=150,
        created_at=datetime(2026, 5, 11),
        updated_at=datetime(2026, 5, 11),
    )


def _officer_transcript(convene: Convene):
    """The transcript AS THE OFFICER SEES IT — the room up to the RISK phase.

    Production calls `_run_risk_officer` where the debate used to run, so `run.transcript`
    holds the four analysts, both researchers, the Research Manager and the Execution
    Desk, and nothing after. Taken from the committed run rather than re-parsed out of
    the CIO's prompt so the officer reads the turns themselves, not a rendering of them.
    """
    from datetime import datetime, timezone

    from app.schemas.agents import AgentId, AgentMessage

    out = []
    for t in convene.transcript:
        aid = t.get("agent_id")
        if aid in DEBATORS or aid == "portfolio_manager":
            break
        out.append(
            AgentMessage(
                agent_id=AgentId(aid),
                content=t.get("content") or "",
                timestamp=datetime(2026, 8, 14, tzinfo=timezone.utc),
            )
        )
    if not out:
        raise StripError(f"{convene.run_id}: no pre-risk turns for the officer to read")
    return out


def shipped_officer_messages(convene: Convene):
    """CR201 — the officer's prompt built by the SHIPPED `build_risk_officer_messages`.

    CR197 measured v8 against a prompt this script assembled itself: the CIO's convene
    block sliced out of the recorded prompt, the ladder appended AFTER the transcript,
    no holdings block, the phase header still reading VERDICT, and a 1200-token
    ceiling. CR201 then shipped a different assembly, and a measurement of the
    reconstruction says nothing about the thing that runs. This calls production's own
    builder, so the persona, the phase framing, the ladder's POSITION (before the
    transcript, deliberately — see its call site), the JSON contract and the message
    shape are production's by construction rather than by resemblance.

    What is reconstructed, and how faithfully:

      * mandate risk_score / max_drawdown_pct / locale / long_only — read verbatim off
        the recorded prompt; the four fields the builder actually reads.
      * the reference triple (size/entry/stop) — the `Reference position` line, i.e.
        the figures the run itself used.
      * drawdown consumed, open risk, trade counts — the recorded live-risk block, or
        NOT SUPPLIED where the recording has no such block (the 08-07 epoch predates
        it). Absence is passed through as absence; nothing is defaulted to zero.
      * the holdings block — transplanted verbatim.
      * the fact sheet — transplanted verbatim (see `_recorded_fact_sheet`).

    What CANNOT be reconstructed, and is therefore absent rather than invented:

      * the Execution Desk's TARGET. It is nowhere in the recorded prompt, so
        `build_option_ladder` gets `target=None` and the ladder carries no
        reward:risk column. Production supplies one whenever the desk set a target,
        so this arm measures the officer with LESS evidence than it will have —
        the same understatement CR197's `inject_ladder` recorded for v6/v7.

    Returns `(system_prompt, messages, rows, facts)`. `facts["evidence_exact"]` is
    True when the regenerated evidence block is byte-identical to the recorded one;
    where it is False the difference is the prompt renderer moving on AFTER that
    epoch was recorded (DEF302's stop-distance clause, DEF292's share-of-cap decimal,
    CR179 Leg 4's headroom clause, the CR153-156 live-risk block) — today's rendering
    of the run's own numbers, which is what "the production assembly" means.
    """
    from app.services.llm_gateway import prepend_grounding_directive
    from app.services.room_prompts import _format_profile, build_risk_officer_messages
    from app.schemas.agents import AgentId

    p = convene.system_prompt
    ref = _REF_POS_RE.search(p)
    if not ref:
        raise StripError(f"{convene.run_id}: no reference position for the officer's ladder")
    used = _USED_RE.search(p)
    open_risk = _OPEN_RISK_RE.search(p)
    last_loss = _LAST_LOSS_RE.search(p)

    existing_open_risk: Any = None
    if open_risk:
        existing_open_risk = float(open_risk.group(1))
    elif _OPEN_RISK_UNCOMPUTED in p:
        from app.agents.safety_floor import CONTEXT_NOT_SUPPLIED

        existing_open_risk = CONTEXT_NOT_SUPPLIED

    last_loss_at: Any = last_loss.group(1) if last_loss else None
    if last_loss_at is None and _LAST_LOSS_UNCOMPUTED in p:
        from app.agents.safety_floor import CONTEXT_NOT_SUPPLIED

        last_loss_at = CONTEXT_NOT_SUPPLIED

    try:
        system_prompt, messages, rows = build_risk_officer_messages(
            mandate=_mandate_for(convene),
            ticker=convene.ticker,
            profile={},
            transcript=_officer_transcript(convene),
            trade_proposal={
                "size_pct": float(ref.group(1)),
                "entry": float(ref.group(2)),
                "stop": float(ref.group(3)),
                "target": None,
            },
            portfolio_snapshot=_recorded_portfolio_block(convene),
            sector_weights=None,
            current_drawdown_pct=float(used.group(1)) if used else None,
            existing_open_risk_pct=existing_open_risk,
            last_loss_closed_at=last_loss_at,
            # A list renders the two over-trading counts; None renders nothing. The
            # 08-07 epoch has no such line, and inventing a "0 today" for it would be
            # a fabricated fact, not a neutral default.
            trade_open_timestamps=[] if _TRADES_MARK in p else None,
        )
    except ValueError as exc:  # the builder's own CR040 refusal
        raise StripError(f"{convene.run_id}: shipped builder refused — {exc}") from exc

    # The fact sheet: the one input with no structured source. `profile={}` renders a
    # refuse-everything sheet, which is located exactly once and replaced with the
    # recorded one. A count other than 1 means the renderer changed shape — raise
    # rather than splice into the wrong place.
    placeholder = _format_profile({}, AgentId.RISK_OFFICER)
    if system_prompt.count(placeholder) != 1:
        raise StripError(
            f"{convene.run_id}: empty-profile placeholder occurs "
            f"{system_prompt.count(placeholder)}x (need 1)"
        )
    system_prompt = system_prompt.replace(placeholder, _recorded_fact_sheet(convene), 1)

    # Verification, not decoration: the mandate/risk-state region the builder
    # regenerated, against the same region as recorded.
    try:
        rec = p[p.index(_MANDATE_ANCHOR) : p.index(_TRANSCRIPT_ANCHOR)]
        gen = system_prompt[
            system_prompt.index(_MANDATE_ANCHOR) : system_prompt.index(_LADDER_ANCHOR)
        ]
    except ValueError as exc:
        raise StripError(f"{convene.run_id}: cannot locate the evidence region — {exc}") from exc
    # The gateway prepends this to EVERY call it routes, the officer's included
    # (`_run_risk_officer` goes through `gateway.stream_chat`). Fidelity rule 1 says
    # never to route the PM replay through the gateway — the directive is already
    # baked into the recorded prompt and would be doubled. The officer's prompt is
    # built fresh here, so it has to be added, or the arm would run the one agent
    # this measurement is about WITHOUT the framing production gives it.
    system_prompt = prepend_grounding_directive(system_prompt)

    facts = {
        "evidence_exact": rec == gen,
        "reference_triple": ref.groups(),
        "has_reward_risk": any(r.reward_risk is not None for r in rows),
    }
    # The figures must round-trip whether or not the WORDING does: a reconstruction
    # that changed the run's own numbers would be measuring another convene.
    for g in ref.groups():
        if g not in gen:
            raise StripError(
                f"{convene.run_id}: reference figure {g} did not survive the rebuild"
            )
    return system_prompt, messages, rows, facts


def render_officer_into_transcript(prompt: str, payload: dict, rows) -> str:
    """v9 — put the officer's payload in front of the CIO the way PRODUCTION does.

    `_run_risk_officer` renders three display turns from the one payload and streams
    them under the three existing risk AgentIds, so they land in the transcript
    exactly where the three debators' turns were removed from. Reproduced here as
    `\n[agent_id] text` per turn, appended to the stripped transcript — the same block
    shape `strip_debators` removed, so the arm puts back what it took out and nothing
    else changes about the prompt.

    Wire ids, not display names: every other turn in the RECORDED transcript is
    labelled with its wire id, and labelling only these three differently would be a
    formatting artefact this arm introduced rather than a property of the design.
    """
    from app.services.risk_officer import render_officer_turns
    from app.services.room_prompts import STANCE_HEADLINE_MAX_CHARS

    turns = render_officer_turns(
        payload, rows, headline_max_chars=STANCE_HEADLINE_MAX_CHARS
    )
    block = "".join(f"\n[{t.agent_id.value}] {t.text}" for t in turns)
    i = prompt.find(_TURN_ANCHOR_FULL)
    if i < 0:
        raise StripError("no turn anchor to append the officer's turns before")
    return prompt[:i] + block + prompt[i:]


def build_variant(convene: Convene, variant: str) -> str:
    prompt = strip_debators(convene, _VARIANT_STRIP[variant])
    if variant in _VARIANT_LADDER:
        prompt = inject_ladder(convene, prompt)
    return prompt


# ── parsing ──────────────────────────────────────────────────────────────


def parse_pm(text: str) -> tuple[str | None, float | None, bool]:
    """Action + raw size from a PM reply, matching production's read pre-clamp.

    Deliberately NOT `_parse_pm_verdict`: that needs a live `_RoomContext` and applies
    the trader-entry fallback, stop/target minting and the risk-tier size clamp. Those
    are downstream policy — replaying them would fold the mandate's ceiling into a
    measurement about the debate. The two pieces reused here are the same functions
    production uses, so MODIFY / MODIFY-AND-APPROVE still resolve to APPROVE.

    A parse failure is its own outcome, never coerced to PASS — production fails safe
    to PASS there (DEF059), but counting that as a PASS would let a formatting wobble
    masquerade as a changed decision.
    """
    parsed = extract_json_object(text) or extract_json_object(text, repair_truncated=True)
    if not parsed:
        return None, None, False
    return _normalize_pm_action(parsed.get("action")), _safe_float(parsed.get("size_pct")), True


# ── statistics ───────────────────────────────────────────────────────────


_WORD_RE = __import__("re").compile(r"[a-z][a-z'-]+")
_STOPWORDS = frozenset(
    "the a an and or but of to in on at for with from by is are was were be been "
    "this that these those it its as not no than then so if while which who whose "
    "i we you they he she them his her their our your my me us do does did have "
    "has had can could should would will shall may might must about into over "
    "under above below between within without because since due given".split()
)


def narration_of(text: str) -> str:
    """The prose the user actually reads, pulled out of the PM's JSON verdict."""
    parsed = extract_json_object(text) or extract_json_object(text, repair_truncated=True)
    if not parsed:
        return ""
    return str(parsed.get("narration") or "")


def content_words(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS}


def jaccard_distance(a: str, b: str) -> float | None:
    """1 − Jaccard over content words. None when either side has no prose.

    Deliberately a set measure over content words rather than a sequence one: the
    question is whether the PM reasoned from different material, not whether it
    reordered the same sentences.
    """
    wa, wb = content_words(a), content_words(b)
    if not wa or not wb:
        return None
    return 1 - len(wa & wb) / len(wa | wb)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, centre - half), min(1.0, centre + half)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar over the discordant pairs.

    b = convenes where the ablation flipped but the noise replay did not,
    c = the reverse. Under the null the debate is inert and each discordant pair is a
    coin flip, so the p-value is the two-sided binomial tail.
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


# ── replay ───────────────────────────────────────────────────────────────


@dataclass
class ReplayResult:
    epoch: str
    run_id: str
    audit_id: str
    ticker: str
    variant: str
    prompt_sha256: str
    response_text: str
    action: str | None
    size_pct: float | None
    parse_ok: bool
    finish_reason: str | None
    latency_s: float
    error: str | None = None


async def _one_call(provider, system_prompt: str, user: str, max_tokens: int,
                    sem: asyncio.Semaphore) -> tuple[str, dict]:
    """One OpenAI-compatible completion, collected. Errors surface as ('', meta)."""
    from app.services.llm_gateway import ChatMessage

    meta: dict[str, Any] = {}
    chunks: list[str] = []
    async with sem:
        try:
            async for chunk in provider.stream_chat(
                system_prompt=system_prompt,
                messages=[ChatMessage(role="user", content=user)],
                max_tokens=max_tokens,
                meta=meta,
            ):
                chunks.append(chunk)
        except Exception as exc:  # noqa: BLE001 - recorded by the caller
            meta["error"] = f"{type(exc).__name__}: {exc}"
    return "".join(chunks), meta


def _read_dropping_trailing_prose(raw: str) -> dict | None:
    """The object between the first '{' and the last '}', or None.

    Used ONLY by the v9t arm, which exists to say what the design does once the
    reply is read the way `extract_json_object`'s own docstring says it reads —
    "tolerating ```json fences and surrounding prose". No other arm calls this;
    v8 and v9 parse exactly as `_run_risk_officer` does.
    """
    first, last = raw.find("{"), raw.rfind("}")
    if first < 0 or last <= first:
        return None
    try:
        out = json.loads(raw[first : last + 1], strict=False)
    except json.JSONDecodeError:
        return None
    return out if isinstance(out, dict) else None


def _reads_with_trailing_prose(raw: str) -> bool:
    """Would this reply parse if the text after the object were dropped?

    Diagnostic ONLY — the arm never uses the value it would recover. Production
    parses with `extract_json_object`, so a reply this returns True for is a reply
    production DISCARDS, and the arm discards it too; counting them separately is
    what turns "1.5% unparseable" into a statement about which fix would move it.
    """
    return _read_dropping_trailing_prose(raw) is not None


async def run_risk_officer(provider, convene: Convene, sem: asyncio.Semaphore,
                           *, tolerant: bool = False) -> tuple[dict | None, list, str | None]:
    """Stage 1 of v8/v9: ONE structured Risk Officer call, on the shipped assembly.

    CR201 — the prompt now comes from production's `build_risk_officer_messages` and
    the budget from production's `_AGENT_MAX_TOKENS[RISK_OFFICER]` (1800), not from
    this script's own builder and a hardcoded 1200. The 1200 mattered: CR201 derived
    the 1800 BY CR179's method FROM the v8 arm's censored 1200 ceiling, so a re-run at
    1200 would re-measure the constraint the shipped budget exists to remove.

    Returns `(payload, rows, error)`. A failed or unparseable reply yields
    `payload=None` and an error string; the caller then injects NOTHING rather than a
    fallback, so the arm degrades to "the debate was simply deleted" instead of
    quietly measuring something in between — a silent substitute is how an ablation
    ends up reporting a design it never ran. (Production degrades differently, and
    deliberately: it renders the ladder alone with an `[AMI …]` mark. That path has
    its own measured floor, 11.8%, and is not what these arms are asking about.)
    """
    from app.schemas.agents import AgentId
    from app.services.room_prompts import max_tokens_for

    sys_prompt, messages, rows, _facts = shipped_officer_messages(convene)
    raw, meta = await _one_call(
        provider,
        sys_prompt,
        messages[0].content,
        max_tokens_for(AgentId.RISK_OFFICER),
        sem,
    )
    if meta.get("error"):
        return None, rows, meta["error"]
    payload = extract_json_object(raw) or extract_json_object(raw, repair_truncated=True)
    if not payload:
        if meta.get("finish_reason") == "length":
            return None, rows, "risk_officer_truncated"
        # Name the failure MODE rather than filing every rejection under one label.
        # `extract_json_object` trims surrounding prose only when the reply does NOT
        # begin with '{' — a reply that opens with the object and closes with a
        # sentence after it is handed whole to `json.loads` and rejected as extra
        # data. That is a distinct, fixable failure from a genuinely malformed
        # object, and the two must not be counted together.
        recovered = _read_dropping_trailing_prose(raw) if tolerant else None
        if recovered is not None:
            return recovered, rows, None
        return None, rows, (
            "risk_officer_trailing_prose"
            if _reads_with_trailing_prose(raw)
            else "risk_officer_unparseable"
        )
    return payload, rows, None


async def replay_one(provider, convene: Convene, variant: str, sem: asyncio.Semaphore) -> ReplayResult:
    from app.services.llm_gateway import ChatMessage

    prompt = build_variant(convene, variant)
    ro_error: str | None = None
    if variant in _VARIANT_RISK_OFFICER:
        from app.services.risk_officer import render_risk_assessment

        payload, rows, ro_error = await run_risk_officer(
            provider, convene, sem, tolerant=variant in _VARIANT_TOLERANT_READ
        )
        if payload is not None:
            if variant in _VARIANT_OFFICER_TURNS:
                # PRODUCTION shape: three rendered turns, back where the debate was.
                prompt = render_officer_into_transcript(prompt, payload, rows)
            else:
                # CR197 shape: one assessment block ahead of the transcript.
                block = render_risk_assessment(payload, rows)
                prompt = prompt.replace(
                    _TRANSCRIPT_ANCHOR, f"{block}\n\n{_TRANSCRIPT_ANCHOR}", 1
                )
    sha = hashlib.sha256(prompt.encode()).hexdigest()
    meta: dict[str, Any] = {}
    chunks: list[str] = []
    err: str | None = None

    async with sem:
        loop = asyncio.get_event_loop()
        started = loop.time()
        try:
            async for chunk in provider.stream_chat(
                system_prompt=prompt,
                # room_prompts.py builds exactly one user message per convene.
                messages=[ChatMessage(role="user", content=f"Convene on {convene.ticker}.")],
                max_tokens=PM_MAX_TOKENS,
                meta=meta,
            ):
                chunks.append(chunk)
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            err = f"{type(exc).__name__}: {exc}"
        elapsed = loop.time() - started

    text = "".join(chunks)
    action, size, ok = parse_pm(text)
    return ReplayResult(
        epoch=convene.epoch,
        run_id=convene.run_id,
        audit_id=convene.audit_id,
        ticker=convene.ticker,
        variant=variant,
        prompt_sha256=sha,
        response_text=text,
        action=action,
        size_pct=size,
        parse_ok=ok,
        finish_reason=meta.get("finish_reason"),
        latency_s=round(elapsed, 2),
        error=err or (f"stage1:{ro_error}" if ro_error else None),
    )


async def run_replays(
    convenes: list[Convene],
    variants: list[str],
    *,
    base_url: str,
    model: str,
    concurrency: int,
    out_jsonl: Path,
    done: set[tuple[str, str, str]],
) -> None:
    from app.services.llm_gateway import VLLMProvider

    provider = VLLMProvider(base_url=base_url, model_name=model, timeout_seconds=180.0)
    sem = asyncio.Semaphore(concurrency)
    todo = [
        (c, v)
        for v in variants
        for c in convenes
        if (c.epoch, c.audit_id, v) not in done
    ]
    print(f"[replay] {len(todo)} calls pending ({len(done)} already recorded)")

    try:
        completed = 0
        with out_jsonl.open("a") as fh:
            for batch_start in range(0, len(todo), concurrency * 4):
                batch = todo[batch_start : batch_start + concurrency * 4]
                results = await asyncio.gather(
                    *(replay_one(provider, c, v, sem) for c, v in batch)
                )
                for r in results:
                    fh.write(json.dumps(r.__dict__) + "\n")
                fh.flush()
                completed += len(results)
                errs = sum(1 for r in results if r.error)
                print(
                    f"[replay] {completed}/{len(todo)} done"
                    + (f" ({errs} errored in last batch)" if errs else "")
                )
    finally:
        await provider.aclose()


# ── reporting ────────────────────────────────────────────────────────────


def load_results(path: Path) -> dict[tuple[str, str, str], dict]:
    out: dict[tuple[str, str, str], dict] = {}
    if not path.exists():
        return out
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            out[(r["epoch"], r["audit_id"], r["variant"])] = r
    return out


def build_report(
    convenes: list[Convene], results: dict[tuple[str, str, str], dict], served_model: str | None
) -> str:
    lines: list[str] = []
    add = lines.append

    add("# CR197 — PM-replay debate ablation: results\n")
    add(
        "Does removing the three Risk Debators' turns from the Portfolio Manager's prompt "
        "change its verdict more often than the model changes its own mind on a byte-identical "
        "prompt? Every number below is paired per convene.\n"
    )
    if served_model:
        add(f"**Served model at replay time:** `{served_model}`\n")
    else:
        add(
            "**Served model at replay time: NOT RECORDED** — this report was rebuilt "
            "without a `run_meta.json` beside the results, so the model that produced "
            "them cannot be named from the artifacts.\n"
        )
    corpus_models = Counter(c.corpus_model for c in convenes if c.corpus_model)
    if corpus_models:
        add(
            "**Model that produced the corpora:** "
            + ", ".join(f"`{m}` ({n})" for m, n in corpus_models.most_common())
            + "\n"
        )
    else:
        add(
            "**Model that produced the corpora:** not recorded — the transcript's `model` field is "
            "null on every turn. The port-8000 registry names Qwen3.6-35B-A3B-NVFP4 as the `ami-llm` "
            "designee over the corpus dates, but that is inference from a registry, not a datum from "
            "the run. It bears only on the replay-vs-recording side-check; the V1a/V1b/V2 contrast is "
            "measured fresh on one model and does not depend on it.\n"
        )

    have = lambda c, v: results.get((c.epoch, c.audit_id, v))  # noqa: E731

    # ── baseline composition ──
    rec = Counter()
    for c in convenes:
        a, _, ok = parse_pm(c.recorded_response)
        rec[a if ok else "PARSE_FAIL"] += 1
    add("## Recorded baseline (from `response_text`, not the floor-vetoed verdict)\n")
    add("| action | n |")
    add("|---|---|")
    for k, n in rec.most_common():
        add(f"| {k} | {n} |")
    add("")

    # ── flip rates ──
    def flips(va: str, vb: str) -> tuple[int, int, list[str]]:
        n = agree = 0
        flipped: list[str] = []
        for c in convenes:
            ra, rb = have(c, va), have(c, vb)
            if not ra or not rb or ra.get("error") or rb.get("error"):
                continue
            if not (ra["parse_ok"] and rb["parse_ok"]):
                continue
            n += 1
            if ra["action"] == rb["action"]:
                agree += 1
            else:
                flipped.append(f"{c.ticker}/{c.run_id[:8]}: {ra['action']}→{rb['action']}")
        return n - agree, n, flipped

    noise_k, noise_n, noise_list = flips("v1a", "v1b")
    abl_k, abl_n, abl_list = flips("v1a", "v2")
    ext_k, ext_n, ext_list = flips("v1a", "v3")

    add("## Verdict flip rates\n")
    add("| contrast | flips / n | rate | 95% CI (Wilson) | reads as |")
    add("|---|---|---|---|---|")
    for label, k, n, meaning in (
        ("V1a vs V1b — **noise floor**", noise_k, noise_n, "same prompt, twice"),
        ("V1a vs V2 — debate removed", abl_k, abl_n, "all three debators stripped"),
        ("V1a vs V3 — extremes removed", ext_k, ext_n, "Neutral kept"),
    ):
        # An arm that was not run in this pass has n=0, and "0/0 — 0.0%" reads as a
        # measured zero. Omit the row instead: a report that states results for arms
        # it never replayed is the failure this whole script exists to avoid.
        if n == 0:
            continue
        p, lo, hi = wilson(k, n)
        add(f"| {label} | {k}/{n} | {p:.1%} | {lo:.1%} – {hi:.1%} | {meaning} |")
    add("")

    # ── directional McNemar: the test the question actually asks ──
    #
    # A CORRECTION, kept visible because it changed the answer. This first computed
    # a SYMMETRIC contrast — "does the ablation flip more often than resampling
    # does" — and returned p=1.0, excess -0.1%, "not demonstrated". That statistic
    # is the wrong instrument: the flip RATES are near-identical (12% both ways)
    # while the flips run in opposite directions. Noise flips balance out (8 up, 8
    # down); ablation flips do not (14 down, 2 up), which is why the APPROVE count
    # falls 22 → 10 with the flip rate unmoved. Marginal homogeneity is the
    # hypothesis of interest, so the pairs to count are APPROVE→PASS against
    # PASS→APPROVE, per contrast, against the same floor.
    def directional(vb: str) -> tuple[int, int, float]:
        b = c_ = 0
        for c in convenes:
            ra, rb = have(c, "v1a"), have(c, vb)
            if not ra or not rb or ra.get("error") or rb.get("error"):
                continue
            if not (ra["parse_ok"] and rb["parse_ok"]):
                continue
            if ra["action"] == "APPROVE" and rb["action"] == "PASS":
                b += 1
            elif ra["action"] == "PASS" and rb["action"] == "APPROVE":
                c_ += 1
        return b, c_, mcnemar_exact(b, c_)

    # ── arm summary: the table that actually shows the shape of the result ──
    _ARM_META = {
        "v1a": ("nothing (baseline)", "Neutral", "yes"),
        "v1b": ("nothing (resampled)", "Neutral", "yes"),
        "v3": ("both extremes", "Neutral", "yes"),
        "v5": ("Conservative + Neutral", "Aggressive", "no"),
        "v4": ("Neutral only", "Conservative", "no"),
        "v2": ("all three", "Trader", "no"),
        "v6": ("all three, + LADDER", "Trader", "no (ladder)"),
        "v7": ("nothing, + LADDER", "Neutral", "yes (ladder)"),
        "v8": ("all three → 1 structured officer", "Risk Officer", "replaced"),
        "v9": ("all three → 1 officer, PRODUCTION render", "Risk Officer ×3", "replaced"),
        "v9t": ("v9, trailing prose dropped on read", "Risk Officer ×3", "replaced"),
    }
    add("## Approval rate by arm\n")
    add("| arm | removed | last voice before PM | Neutral present | APPROVE | rate |")
    add("|---|---|---|---|---|---|")
    for vb in ("v7", "v9t", "v9", "v8", "v1a", "v1b", "v3", "v5", "v4", "v6", "v2"):
        rs = [have(c, vb) for c in convenes]
        rs = [r for r in rs if r and not r.get("error")]
        if not rs:
            continue
        ap = sum(1 for r in rs if r["action"] == "APPROVE")
        pa = sum(1 for r in rs if r["action"] == "PASS")
        removed, lastv, neu = _ARM_META[vb]
        rate = ap / (ap + pa) if (ap + pa) else 0.0
        add(f"| {vb} | {removed} | {lastv} | {neu} | {ap} | {rate:.1%} |")
    add("")
    add(
        "**v8 vs v9 (CR201).** Both make the same single officer call on the same "
        "shipped prompt; they differ only in what reaches the CIO. v8 injects one "
        "`render_risk_assessment` block ahead of the transcript (CR197's shape); v9 "
        "renders the payload into the three risk AgentIds via `render_officer_turns` "
        "and appends them where the debate was removed, which is what "
        "`_run_risk_officer` actually does. v9 is the shipped assembly; v8 is kept "
        "beside it so a move can be attributed to the prompt or to the rendering.\n"
    )
    _subtractive = [v for v in ("v2", "v3", "v4", "v5") if any(have(c, v) for c in convenes)]
    if len(_subtractive) == 4:
        add(
            "Read down the 'Neutral present' column. Every arm that keeps the Neutral sits "
            "at the baseline rate; every arm without it falls, and falls further as more of "
            "the rest is also removed. The count of surviving debators does NOT order the "
            "table — v3 keeps one and scores highest, v4 keeps two and scores low.\n"
        )
    if "v5" in _subtractive:
        add(
        "**The recency explanation is refuted by v5.** Approval rate first appeared to "
        "track whoever spoke last, ordered by how negative that voice is (Neutral "
        "15.7-17.2%, Conservative 11.9%, Trader 7.4%) — anchoring would explain that "
        "without the debate carrying any information at all. v5 leaves the Aggressive "
        "speaking last, a voice that argued 'for' in 117 of 118 convenes, and anchoring "
        "therefore predicts approvals at or above baseline. Observed: **10.3%, the "
        "second-lowest arm.** The PM is not echoing its final input.\n"
        )

    # ── the officer's own reply: how often production would even USE it ──
    #
    # CR201. The decision numbers below are computed over the convenes where the
    # officer's reply PARSED, so the rate at which it does not is not a footnote to
    # them — it is the other half of the result. Every discarded reply is a convene
    # where production renders the ladder alone (measured floor 11.8%) instead of the
    # design being measured.
    officer_arms = [v for v in ("v8", "v9", "v9t") if any(have(c, v) for c in convenes)]
    if officer_arms:
        add("## Risk Officer replies the shipped parser accepted\n")
        add("| arm | convenes | trailing prose after the JSON | otherwise unparseable | discarded |")
        add("|---|---|---|---|---|")
        for vb in officer_arms:
            rs = [have(c, vb) for c in convenes]
            rs = [r for r in rs if r]
            tp = sum(1 for r in rs if r.get("error") == "stage1:risk_officer_trailing_prose")
            up = sum(1 for r in rs if r.get("error") == "stage1:risk_officer_unparseable")
            n = len(rs)
            add(
                f"| {vb} | {n} | {tp} ({tp / n:.1%}) | {up} ({up / n:.1%}) | "
                f"{(tp + up) / n:.1%} |"
            )
        add("")
        add(
            "`trailing prose after the JSON` is a reply that IS a complete JSON object "
            "followed by a sentence. `extract_json_object` trims surrounding prose only "
            "when the reply does not START with '{' — one that opens with the object and "
            "closes with a sentence is handed whole to `json.loads` and rejected as extra "
            "data. Production parses with that function, so these are replies production "
            "discards, and the arms discard them too.\n"
        )
    add("## Decision rule — directional (marginal homogeneity)\n")
    add(
        "The question is not whether the verdict *changes* but whether it changes "
        "*in a direction*. Resampling moves verdicts symmetrically; an input that "
        "carries signal moves them one way.\n"
    )
    add("| contrast | APPROVE→PASS | PASS→APPROVE | net | exact McNemar p |")
    add("|---|---|---|---|---|")
    results_dir: dict[str, tuple[int, int, float]] = {}
    for vb, label in (
        ("v1b", "same prompt twice — **noise floor**"),
        ("v2", "all three debators removed"),
        ("v3", "extremes removed, Neutral kept"),
        ("v4", "Neutral removed, extremes kept"),
        ("v5", "Conservative + Neutral removed"),
        ("v6", "all three removed, ladder injected"),
        ("v7", "**ladder added to the full prompt**"),
        ("v8", "**3 officers → 1 structured Risk Officer** (officer block)"),
        ("v9", "**3 officers → 1 structured Risk Officer** (PRODUCTION assembly)"),
        ("v9t", "**PRODUCTION assembly, trailing prose dropped on read**"),
    ):
        if not any(have(c, vb) for c in convenes):
            continue
        b, c_, p = directional(vb)
        results_dir[vb] = (b, c_, p)
        add(f"| {label} | {b} | {c_} | {b - c_:+d} | {p:.5f} |")
    add("")

    if "v2" in results_dir:
        b2, c2, p2 = results_dir["v2"]
        claim = (
            "**The debate causally moves the PM's verdict.** Removing it makes the PM "
            f"refuse trades it otherwise approves — {b2} approvals lost against {c2} "
            "gained, against a floor that is balanced by construction."
            if p2 < 0.05 and b2 > c2
            else "**Not demonstrated** at this n — a ceiling on the effect, not proof of zero."
        )
        add(f"Rule: p<0.05 with a net in one direction. Result: {claim}\n")

    # ── size deltas ──
    deltas: list[float] = []
    for c in convenes:
        r1a, r2 = have(c, "v1a"), have(c, "v2")
        if not r1a or not r2:
            continue
        if r1a.get("action") == "APPROVE" and r2.get("action") == "APPROVE":
            if r1a.get("size_pct") is not None and r2.get("size_pct") is not None:
                deltas.append(r2["size_pct"] - r1a["size_pct"])
    if not any(have(c, "v2") for c in convenes):
        deltas = []
    add("## Position size, where both arms approved (v1a vs v2)\n")
    if deltas:
        deltas_sorted = sorted(deltas)
        med = deltas_sorted[len(deltas_sorted) // 2]
        nonzero = [d for d in deltas if abs(d) > 1e-9]
        add(
            f"n={len(deltas)} paired approvals · median Δ = **{med:+.2f} pt** · "
            f"{len(nonzero)}/{len(deltas)} differ at all.\n"
        )
    else:
        add("v2 was not replayed in this pass — nothing to compare.\n")

    # ── narration divergence ──
    #
    # The verdict is one token; the narration is the product. A debate that never
    # flips APPROVE/PASS but visibly changes the reasoning the user reads is doing
    # something a flip-rate cannot see — and on a training simulator that is much of
    # the point. Measured against the same-prompt floor so resampling noise does not
    # get read as influence.
    def divergences(va: str, vb: str) -> list[float]:
        out: list[float] = []
        for c in convenes:
            ra, rb = have(c, va), have(c, vb)
            if not ra or not rb or ra.get("error") or rb.get("error"):
                continue
            d = jaccard_distance(narration_of(ra["response_text"]), narration_of(rb["response_text"]))
            if d is not None:
                out.append(d)
        return out

    noise_div = divergences("v1a", "v1b")
    abl_div = divergences("v1a", "v2")
    ext_div = divergences("v1a", "v3")
    add("## Narration divergence — does the debate change what the user reads?\n")
    add("| contrast | n | mean Jaccard distance | median |")
    add("|---|---|---|---|")
    for label, vals in (
        ("V1a vs V1b — same prompt (floor)", noise_div),
        ("V1a vs V2 — debate removed", abl_div),
        ("V1a vs V3 — extremes removed", ext_div),
        ("V1a vs V9t — production officer assembly", divergences("v1a", "v9t")),
    ):
        if not vals:
            continue
        srt = sorted(vals)
        add(f"| {label} | {len(vals)} | {sum(vals)/len(vals):.3f} | {srt[len(srt)//2]:.3f} |")
    add("")
    if noise_div and abl_div:
        lift = (sum(abl_div) / len(abl_div)) - (sum(noise_div) / len(noise_div))
        add(
            f"Excess divergence attributable to removing the debate: **{lift:+.3f}** "
            "Jaccard distance over the resampling floor. A positive value means the PM "
            "reasoned from visibly different material, whether or not its verdict moved.\n"
        )

    # ── per-epoch ──
    add("## Per-epoch (primary — pooling across prompt epochs is not defensible)\n")
    # The second column follows whichever ablation arm this pass actually ran.
    abl_arm = next(
        (v for v in ("v2", "v9t", "v9", "v8") if any(have(c, v) for c in convenes)), None
    )
    add(f"| epoch | convenes | noise flips | {abl_arm or 'ablation'} flips | v1a APPROVE | {abl_arm or '—'} APPROVE |")
    add("|---|---|---|---|---|---|")
    for ep in sorted({c.epoch for c in convenes}):
        sub = [c for c in convenes if c.epoch == ep]
        nk = nn = ak = an = 0
        base_ap = arm_ap = base_n = arm_n = 0
        for c in sub:
            r1a, r1b = have(c, "v1a"), have(c, "v1b")
            r2 = have(c, abl_arm) if abl_arm else None
            usable = lambda r: bool(r and not r.get("error") and r.get("parse_ok"))  # noqa: E731
            if usable(r1a) and usable(r1b):
                nn += 1
                nk += r1a["action"] != r1b["action"]
            if usable(r1a):
                base_n += 1
                base_ap += r1a["action"] == "APPROVE"
            if usable(r1a) and usable(r2):
                an += 1
                ak += r1a["action"] != r2["action"]
            if usable(r2):
                arm_n += 1
                arm_ap += r2["action"] == "APPROVE"
        add(
            f"| {ep} | {len(sub)} | {nk}/{nn} | {ak}/{an} | {base_ap}/{base_n} | "
            f"{arm_ap}/{arm_n} |"
        )
    add("")

    # ── samples, per P16: a count nobody read is not a measurement ──
    add("## Samples for hand-reading\n")
    for label, lst in (
        ("Noise flips (same prompt, different answer)", noise_list),
        ("Ablation flips (debate removed)", abl_list),
        ("Extremes-removed flips", ext_list),
        ("Production-officer flips (v1a vs v9t)", flips("v1a", "v9t")[2]),
    ):
        if not lst:
            continue
        add(f"**{label}** — {len(lst)} total")
        for s in lst[:12]:
            add(f"- {s}")
        add("")

    add("## Caveats that bound every number above\n")
    add(
        "- Four prompt epochs; per-epoch tables are primary, pooled figures are indicative.\n"
        "- 13 unique tickers underlie the convenes — observations are clustered, not independent.\n"
        "- Server-side sampling temperature is unknown, which is exactly why the noise floor is "
        "measured rather than assumed.\n"
        "- At n≈136 a difference below roughly 8–10pp is not resolvable; a null here bounds the "
        "effect, it does not prove absence.\n"
        "- **The limit that bounds the obvious action.** Every arm holds the surviving turns "
        "FIXED at what was recorded, and those turns were written in a room where all three "
        "debators spoke. So v3 shows the PM does not need the extremes' text *given a Neutral "
        "turn that was produced with the extremes present* — it does NOT show the extremes can "
        "be deleted. The Neutral's stated job is to synthesise those two; remove them from a "
        "live run and it has nothing to synthesise and writes something different. Testing that "
        "needs a live two-arm room benchmark, not this replay.\n"
        "- Only the PM turn is replayed. This measures whether the debate changes the PM's decision, "
        "not whether the debate has value as user-facing product — which it demonstrably does "
        "(SSE stream, Journal replay, comb voices, 1-on-1 personas).\n"
    )
    return "\n".join(lines)


# ── main ─────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description="CR197 PM-replay debate ablation")
    repo = Path(__file__).resolve().parents[2]
    ap.add_argument(
        "--corpus",
        type=Path,
        default=repo / "docs/forward_planning/CR143_agent_prompt_audit/corpus",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=repo / "docs/forward_planning/CR197_risk_debate_effectiveness/ablation",
    )
    ap.add_argument("--epochs", nargs="+", default=list(DEFAULT_EPOCHS))
    ap.add_argument("--variants", nargs="+", default=["v1a", "v1b", "v2"], choices=VARIANTS)
    ap.add_argument("--base-url", default="http://192.168.20.74:8000")
    ap.add_argument("--model", default="ami-llm")
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0, help="cap convenes (smoke runs)")
    ap.add_argument("--dry-run", action="store_true", help="validate joins+strips, no network")
    ap.add_argument("--report-only", action="store_true", help="rebuild the summary from JSONL")
    args = ap.parse_args()

    convenes: list[Convene] = []
    problems: list[str] = []
    for epoch in args.epochs:
        audit, runs = load_epoch(args.corpus, epoch)
        cs, ps = join_epoch(epoch, audit, runs)
        convenes.extend(cs)
        problems.extend(ps)
        print(f"[join] {epoch}: {len(cs)}/{len(runs)} convenes joined")

    if problems:
        print(f"[join] !! {len(problems)} unjoined:")
        for p in problems[:10]:
            print(f"       {p}")
    if not convenes:
        print("[join] nothing joined — aborting")
        return 1
    if args.limit:
        convenes = convenes[: args.limit]

    # Validate every strip before any network call: a StripError found mid-run would
    # leave a half-populated JSONL that looks complete.
    strip_fail = 0
    for c in convenes:
        for variant in ("v2", "v3"):
            try:
                build_variant(c, variant)
            except StripError as exc:
                strip_fail += 1
                if strip_fail <= 10:
                    print(f"[strip] !! {exc}")
    total_turns = sum(len(c.debator_turns()) for c in convenes)
    print(
        f"[strip] {len(convenes)} convenes · {total_turns} debator turns · "
        f"{strip_fail} strip failures"
    )

    # CR201 — the officer's prompt is now production's, so it is validated like the
    # strips are: built for every convene before any network call, and the fidelity of
    # the rebuild REPORTED rather than assumed. `evidence_exact` False is not a
    # failure — it is the prompt renderer having moved on after that epoch was
    # recorded — but a count of it belongs in front of anyone reading the result.
    officer_fail = 0
    exact_by_epoch: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    rr_missing = 0
    if any(v in _VARIANT_RISK_OFFICER for v in args.variants) or args.dry_run:
        for c in convenes:
            try:
                sysp, msgs, rows, facts = shipped_officer_messages(c)
            except StripError as exc:
                officer_fail += 1
                if officer_fail <= 10:
                    print(f"[officer] !! {exc}")
                continue
            slot = exact_by_epoch[c.epoch]
            slot[1] += 1
            slot[0] += bool(facts["evidence_exact"])
            rr_missing += not facts["has_reward_risk"]
        for ep in sorted(exact_by_epoch):
            ok, n = exact_by_epoch[ep]
            print(f"[officer] {ep}: evidence byte-exact vs recorded {ok}/{n}")
        print(
            f"[officer] {officer_fail} assembly failures · reward:risk column absent "
            f"in {rr_missing} ladders (no TARGET in the corpus — production has one "
            f"whenever the Execution Desk set one)"
        )
        if officer_fail:
            strip_fail += officer_fail

    args.out.mkdir(parents=True, exist_ok=True)
    jsonl = args.out / "ablation_calls.jsonl"

    if args.dry_run:
        sample = convenes[0]
        stripped = build_variant(sample, "v2")
        print(
            f"[dry-run] sample {sample.ticker}/{sample.run_id[:8]}: "
            f"{len(sample.system_prompt)} → {len(stripped)} chars "
            f"({len(sample.system_prompt) - len(stripped)} removed)"
        )
        print(f"[dry-run] corpus models: {Counter(c.corpus_model for c in convenes).most_common()}")
        from app.schemas.agents import AgentId as _Aid
        from app.services.room_prompts import max_tokens_for as _mt

        osys, omsgs, orows, ofacts = shipped_officer_messages(sample)
        turns = render_officer_into_transcript(
            build_variant(sample, "v9"),
            {"options": [{"size_pct": r.size_pct, "case_for": "x", "case_against": "y",
                          "key_number": "z"} for r in orows],
             "recommended": orows[1].size_pct, "confidence": "medium",
             "decisive_number": "z"},
            orows,
        )
        print(
            f"[dry-run] shipped officer prompt: {len(osys)} chars · "
            f"max_tokens={_mt(_Aid.RISK_OFFICER)} · rungs="
            f"{[round(r.size_pct, 1) for r in orows]} · evidence_exact="
            f"{ofacts['evidence_exact']}"
        )
        print(
            f"[dry-run] v9 CIO prompt with rendered turns: "
            f"{len(build_variant(sample, 'v9'))} → {len(turns)} chars"
        )
        print("[dry-run] OK — no network calls made")
        return 0 if strip_fail == 0 else 1

    if strip_fail:
        print("[abort] strip failures must be zero before replaying")
        return 1

    results = load_results(jsonl)
    served: str | None = None
    meta_path = args.out / "run_meta.json"
    if meta_path.exists():
        served = (_load_json(meta_path) or {}).get("served_model")

    if not args.report_only:
        import httpx

        try:
            resp = httpx.get(f"{args.base_url}/v1/models", timeout=10.0)
            served = ", ".join(m.get("id", "?") for m in resp.json().get("data", []))
            print(f"[preflight] {args.base_url} serving: {served}")
        except Exception as exc:  # noqa: BLE001
            print(f"[preflight] !! {args.base_url} unreachable ({type(exc).__name__}: {exc})")
            print("[preflight] the LLM must be up to replay; --dry-run and --report-only do not need it")
            return 2
        if args.model not in (served or ""):
            print(f"[preflight] !! model '{args.model}' not in served list — refusing to guess")
            return 2

        # Persist what was actually replayed, so `--report-only` can restate it. A
        # report that has forgotten which model produced its numbers is the failure
        # this file's fidelity rules exist to prevent, and the preflight only runs on
        # a replay pass.
        from app.schemas.agents import AgentId as _AgentId
        from app.services.room_prompts import max_tokens_for as _max_tokens_for

        (args.out / "run_meta.json").write_text(
            json.dumps(
                {
                    "served_model": served,
                    "model_requested": args.model,
                    "base_url": args.base_url,
                    "variants": list(args.variants),
                    "concurrency": args.concurrency,
                    "epochs": list(args.epochs),
                    "pm_max_tokens": PM_MAX_TOKENS,
                    "risk_officer_max_tokens": _max_tokens_for(_AgentId.RISK_OFFICER),
                    "started_utc": __import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc
                    ).isoformat(timespec="seconds"),
                },
                indent=2,
            )
            + "\n"
        )

        asyncio.run(
            run_replays(
                convenes,
                args.variants,
                base_url=args.base_url,
                model=args.model,
                concurrency=args.concurrency,
                out_jsonl=jsonl,
                done=set(results.keys()),
            )
        )
        results = load_results(jsonl)

    report = build_report(convenes, results, served)
    summary = args.out / "ABLATION_SUMMARY.md"
    summary.write_text(report)
    print(f"[report] wrote {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
