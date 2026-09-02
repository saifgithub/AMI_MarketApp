"""Deterministic scorers for a harness run. No judge model, anywhere.

Every score below is computable from the transcript plus the prompt the agent
was actually sent. That is the point: a judge model would put a second,
unvalidated LLM between the change and the number, and the whole complaint this
CR rests on is that we could not tell instruction-following from model mood. A
regex can be wrong, but it is wrong the SAME way on every arm, which is what a
before/after needs.

Each scorer's `proves` string travels with the number into the scored JSON, so a
later reader cannot pick up the figure without the caveat. `README.md` carries
the long form, including what none of these prove.

Scorers
-------
schema_validity        PM verdict parses + is a legal action, and the 5-way vote
                       produced a verdict at all.
envelope_parse_rate    Fraction of stance-carrying turns whose envelope parses
                       through the PRODUCTION parser.
numbers_match_sheet    Fraction of $/%/x numbers in an answer that also appear in
                       that agent's own prompt (sheet + transcript).
mandate_echo           Does the turn honour the mandate's horizon/goal without
                       contradicting the mandate block it was handed.
live_citation_rate     Fraction of the agent's LIVE fact-sheet fields the turn
                       actually names. R29: a SUPPRESSION proxy, not a quality
                       measure.
"""
import re
from typing import Any

from app.schemas.agents import AgentId
from app.services.room_runner import parse_stance_envelope

# ── which agents are asked for a stance envelope ─────────────────────────────
# The PM answers in JSON and is never asked for one; every prose agent is.
_ENVELOPE_AGENTS = frozenset(
    a.value for a in AgentId
    if a not in (AgentId.PORTFOLIO_MANAGER,)
)

_LEGAL_ACTIONS = {"APPROVE", "REJECT", "MODIFY", "PASS", "NO_VERDICT"}

# A number a reader would treat as a claim: money, percent, multiple, or a bare
# decimal with 2+ significant digits. Bare small integers are excluded — "3
# reasons", "Q3" and a list index are not claims about the company.
_NUMBER_RE = re.compile(
    r"(?<![\w.])"
    r"\$?\d{1,3}(?:,\d{3})+(?:\.\d+)?"     # 1,234,567
    r"|(?<![\w.])\$\d+(?:\.\d+)?"          # $271.83
    r"|(?<![\w.])\d+\.\d+"                 # 48.77
    r"|(?<![\w.])\d{2,}(?=%|x|bps|\b)"     # 23%, 19x, 1234bps
)

# `(LIVE)` fields are labelled per line in the rendered sheet; the label is what
# WP01's fixes are about, so the citation scorer keys off the same label.
_LIVE_LINE_RE = re.compile(r"^([^\n:]{2,60})\s*\(LIVE[^)]*\)\s*:", re.MULTILINE)


def _normalise_numbers(text: str) -> set[str]:
    """Numbers as comparable strings: commas and $ dropped, trailing zeros kept.

    Deliberately NOT rounded. `48.77` vs `48.8` is a different claim, and a
    scorer that treats them as equal cannot see a fabricated precision.
    """
    out = set()
    for m in _NUMBER_RE.finditer(text):
        s = m.group(0).lstrip("$").replace(",", "")
        if s:
            out.add(s)
    return out


def _live_field_labels(prompt: str) -> list[str]:
    """The `(LIVE)` line labels in the prompt this agent was actually sent."""
    return [m.group(1).strip() for m in _LIVE_LINE_RE.finditer(prompt)]


# Keywords that stand for each LIVE line, so "Margin trend, YoY (LIVE)" counts
# as cited when the turn says "margin trend" or "margins expanded YoY". Derived
# from the label itself — no hand-maintained list to rot.
def _label_tokens(label: str) -> list[str]:
    words = [w for w in re.split(r"[^A-Za-z]+", label.lower()) if len(w) > 3]
    return words or [label.lower()]


def score_schema_validity(run: dict) -> dict:
    pm = run.get("pm") or {}
    verdict = pm.get("verdict")
    action = str(verdict.get("action")) if verdict else None
    reason = (verdict or {}).get("reason") or ""
    return {
        "proves": (
            "The CIO produced a verdict the production parser accepts, with a "
            "legal action and a non-empty reason, from N independent draws voted "
            "the way production votes them. It does NOT prove the verdict is right."
        ),
        "samples_requested": pm.get("samples_requested"),
        "samples_returned": pm.get("samples_returned"),
        "samples_parsed": pm.get("samples_parsed"),
        "parse_rate": (
            round(pm["samples_parsed"] / pm["samples_requested"], 3)
            if pm.get("samples_requested") else None
        ),
        "action": action,
        "action_legal": action in _LEGAL_ACTIONS if action else False,
        "reason_present": bool(reason.strip()),
        "agreement": pm.get("agreement"),
        "approve_votes": pm.get("approve_votes"),
        "actions_drawn": pm.get("actions"),
        "pass": bool(verdict) and action in _LEGAL_ACTIONS and bool(reason.strip()),
    }


def score_envelope_parse_rate(run: dict) -> dict:
    checked, parsed, detail = 0, 0, {}
    for t in run["turns"]:
        if t["agent"] not in _ENVELOPE_AGENTS or t.get("error"):
            continue
        checked += 1
        _prose, env = parse_stance_envelope(t["answer"])
        ok = env.stance is not None and env.conviction is not None and bool(env.headline)
        parsed += int(ok)
        detail[t["agent"]] = {
            "stance": env.stance, "conviction": env.conviction,
            "headline_present": bool(env.headline),
        }
    return {
        "proves": (
            "The machine channel the UI strips and renders from is emitting in a "
            "shape the SHIPPED parser (`room_runner.parse_stance_envelope`) reads. "
            "A miss here is raw syntax on the user's screen AND a null stance "
            "(DEF147/DEF247). It says nothing about whether the stance is correct."
        ),
        "checked": checked,
        "parsed": parsed,
        "rate": round(parsed / checked, 3) if checked else None,
        "per_agent": detail,
    }


def score_numbers_match_sheet(run: dict) -> dict:
    """Every $/%/x number an agent states should be traceable to its own prompt.

    The prompt — sheet AND the transcript it was handed — is the whole universe
    of numbers the agent may quote. A number in the answer that is in neither is
    either arithmetic the agent did (legitimate) or a number it recalled from
    training memory (the thing the sheet's disclosure block forbids). The scorer
    cannot tell those apart, so it reports the rate and the unmatched values
    rather than declaring a fabrication.
    """
    per_agent, tot_n, tot_matched = {}, 0, 0
    for t in run["turns"]:
        if t.get("error") or not t["answer"]:
            continue
        source = _normalise_numbers(t["system_prompt"] + "\n" + t["user_message"])
        stated = _normalise_numbers(t["answer"])
        matched = stated & source
        unmatched = sorted(stated - source)
        tot_n += len(stated)
        tot_matched += len(matched)
        per_agent[t["agent"]] = {
            "stated": len(stated),
            "matched": len(matched),
            "rate": round(len(matched) / len(stated), 3) if stated else None,
            "unmatched_sample": unmatched[:12],
        }
    return {
        "proves": (
            "How much of the arithmetic the Room states is traceable to the bytes "
            "it was given. It does NOT prove the unmatched remainder is fabricated "
            "— derived figures (a ratio the agent computed, a rounded restatement) "
            "land in the same bucket. Read the rate as a MOVEMENT between arms, "
            "never as a fabrication count."
        ),
        "stated": tot_n,
        "matched": tot_matched,
        "rate": round(tot_matched / tot_n, 3) if tot_n else None,
        "per_agent": per_agent,
    }


def score_mandate_echo(run: dict) -> dict:
    """Does each turn respect the horizon/goal it was handed?

    Two checks, both deterministic:
      - the mandate block IS in the prompt (a rendering regression is silent
        otherwise — the agent then reasons against a default it invented);
      - the answer does not assert a horizon the mandate contradicts, e.g. a
        `short` mandate answered with "multi-decade hold".
    """
    mandate = run["mandate"]
    horizon = str(mandate["horizon"])
    goal = str(mandate["primary_goal"])
    # Phrases that CONTRADICT each horizon. Kept narrow and literal: a scorer
    # that guesses at intent is a judge model with worse recall.
    wrong = {
        "short": [r"multi-decade", r"decades?\b", r"\b10\+? *years?", r"buy and hold forever"],
        "medium": [r"multi-decade", r"\bday[- ]trad", r"intraday"],
        "long": [r"\bday[- ]trad", r"intraday", r"scalp"],
        "very_long": [r"\bday[- ]trad", r"intraday", r"scalp"],
    }.get(horizon, [])
    pats = [re.compile(p, re.IGNORECASE) for p in wrong]

    per_agent, block_ok, clean = {}, 0, 0
    checked = 0
    for t in run["turns"]:
        if t.get("error") or not t["answer"]:
            continue
        checked += 1
        prompt = t["system_prompt"] + "\n" + t["user_message"]
        has_block = (
            f"Horizon: {horizon}" in prompt and f"Primary goal: {goal}" in prompt
        )
        hits = sorted({m.group(0).lower() for p in pats for m in p.finditer(t["answer"])})
        block_ok += int(has_block)
        clean += int(not hits)
        per_agent[t["agent"]] = {"mandate_block_present": has_block, "conflicts": hits}
    return {
        "proves": (
            "The mandate the run claims is the mandate the agent was handed "
            f"(Horizon: {horizon} / Primary goal: {goal} literally present in the "
            "prompt), and the turn does not assert a horizon the mandate rules "
            "out. Coherence of the mandate ITSELF is `mandates.py`'s job — it "
            "derives `path` from `primary_goal` the way onboarding does, so the "
            "`h_short` artifact cannot recur."
        ),
        "horizon": horizon,
        "primary_goal": goal,
        "path": str(mandate["path"]),
        "checked": checked,
        "mandate_block_present": block_ok,
        "conflict_free": clean,
        "rate": round(clean / checked, 3) if checked else None,
        "per_agent": per_agent,
    }


def score_live_citation_rate(run: dict) -> dict:
    """Of the LIVE fields an agent was given, how many did it actually name?

    R29, stated here because the number is easy to over-read: this is a
    SUPPRESSION PROXY. It shows agents stopped refusing data they hold. It says
    nothing about whether the Room's answer got better. Do not report a citation
    delta as a quality result.
    """
    per_agent, tot_fields, tot_cited = {}, 0, 0
    for t in run["turns"]:
        if t.get("error") or not t["answer"]:
            continue
        labels = _live_field_labels(t["system_prompt"] + "\n" + t["user_message"])
        if not labels:
            continue
        ans = t["answer"].lower()
        cited = [lb for lb in labels if any(tok in ans for tok in _label_tokens(lb))]
        tot_fields += len(labels)
        tot_cited += len(cited)
        per_agent[t["agent"]] = {
            "live_fields": len(labels),
            "cited": len(cited),
            "rate": round(len(cited) / len(labels), 3),
            "uncited": sorted(set(labels) - set(cited)),
        }
    return {
        "proves": (
            "SUPPRESSION PROXY ONLY (R29). Agents are naming the LIVE fields they "
            "were given instead of denying they have them. It is NOT an outcome "
            "measure and must never be reported as one: a Room that cites every "
            "field and reaches a worse decision scores better here."
        ),
        "live_fields": tot_fields,
        "cited": tot_cited,
        "rate": round(tot_cited / tot_fields, 3) if tot_fields else None,
        "per_agent": per_agent,
    }


def score_run(run: dict) -> dict[str, Any]:
    turns = run["turns"]
    errored = [t["agent"] for t in turns if t.get("error")]
    truncated = [t["agent"] for t in turns if t.get("finish") == "length"]
    return {
        "run": {
            "ticker": run["ticker"],
            "mandate_label": run["mandate_label"],
            "model_root": run["model"]["root"],
            "thinking": run["thinking"],
            "turns": len(turns),
            "turns_errored": errored,
            "turns_truncated_at_budget": truncated,
            "reasoning_tokens_total": sum(t.get("tok_reasoning") or 0 for t in turns),
        },
        "schema_validity": score_schema_validity(run),
        "envelope_parse_rate": score_envelope_parse_rate(run),
        "numbers_match_sheet": score_numbers_match_sheet(run),
        "mandate_echo": score_mandate_echo(run),
        "live_citation_rate": score_live_citation_rate(run),
    }
