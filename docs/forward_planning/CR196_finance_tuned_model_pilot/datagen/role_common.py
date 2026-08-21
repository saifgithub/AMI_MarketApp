#!/usr/bin/env python3
"""role_common.py — shared plumbing for CR196 §2c.4 role-behaviour recipes (12–16).

Recipes 1–9 train the shared analytical SUBSTRATE: read the statements correctly.
Recipes 12–16 train the ROLES that argue over those statements — bear, bull,
research manager, the three risk debators, trader/PM. The Room's buy/sell verdict
is produced by that argument, so role quality is what the verdict rests on.

## The design constraint that shapes every recipe here

One model serves all 13 roles in `content/agents/`. So role behaviour must be
trained as CONDITIONAL on the system prompt ("given you are the Bear, attack"),
never as an unconditional prior ("be bearish"). An unconditional directional
opinion would be inherited by bull and bear alike and the debate would collapse
into consensus wearing two hats — scoring well on eval right up until it is wrong
together. Every example below therefore pairs the REAL role prompt with a target
that is correct FOR THAT ROLE, and the same fact sheet appears under several
different role prompts with legitimately different answers.

## Why the labels are verifiable without an LLM judge

CR038: prompt instructions are not controls — that applies to graders too. These
recipes never ask a model to score a model. Instead the target answer is RENDERED
from computed facts, exactly as recipe4 renders its earnings-quality verdict: the
generator computes what is true of the fact sheet, then writes the answer from
those computed values. An answer that cannot be produced from the computed facts
is not produced at all. Grounding is structural, not checked after the fact.

`assert_grounded()` is the belt-and-braces second pass: every $ figure and every
percentage appearing in a rendered target must trace back to a value the generator
itself computed. It raises rather than warns — a recipe that drifts fails the build.

## Live sources, never hand-copies

- Role prompts: `content/agents/<agent_id>.md`, frontmatter stripped.
- Stance envelope: `_STANCE_FORMAT` / `_STANCE_FORMAT_RISK` read off a real
  `room_prompts` module load (same sys.modules stubbing recipe8 documents), so a
  wording change in production cannot silently invalidate this training data.
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import REPO, fmt_b, pick  # noqa: E402

AGENTS_DIR = os.path.join(REPO, "content", "agents")
BACKEND = os.path.join(REPO, "backend")


def load_role_prompt(agent_id: str) -> str:
    """The real production prompt for one role, frontmatter stripped."""
    path = os.path.join(AGENTS_DIR, f"{agent_id}.md")
    if not os.path.exists(path):
        raise SystemExit(f"role prompt missing: {path}")
    text = open(path).read()
    m = re.match(r"^---\n.*?\n---\n", text, re.S)
    return text[m.end():].strip() if m else text.strip()


_ROOM_PROMPTS = None


def _load_room_prompts():
    """Load the REAL room_prompts module with its DB/network-coupled imports stubbed.

    Identical stub set to recipe8 (see its docstring for the full rationale): the
    module's top-level code must actually execute so the format constants are the
    real Python values, not a regex reconstruction of an f-string. `technicals` is
    stubbed because it pulls `app.core.logging` → `structlog`, which this synthetic
    recipe has no reason to install.
    """
    global _ROOM_PROMPTS
    if _ROOM_PROMPTS is not None:
        return _ROOM_PROMPTS
    if BACKEND not in sys.path:
        sys.path.insert(0, BACKEND)

    def _stub(name, **attrs):
        m = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(m, k, v)
        sys.modules[name] = m
        return m

    _agents_pkg = types.ModuleType("app.agents")
    _agents_pkg.__path__ = [os.path.join(BACKEND, "app", "agents")]
    sys.modules.setdefault("app.agents", _agents_pkg)
    _stub("app.agents.safety_floor", CONTEXT_NOT_SUPPLIED=object())
    _stub("app.services.agent_prompts", build_agent_prompt=lambda *a, **k: "")
    _fund_fns = [
        "analyst_consensus_line", "balance_sheet_line", "dividend_line", "earnings_power_line",
        "identity_line", "buyback_line", "day_move_line", "liquidity_line", "margin_structure_line",
        "margin_trend_line", "primary_trend_line", "relative_strength_line", "risk_profile_line",
        "short_interest_line", "ownership_line", "pe_line", "peg_part", "returns_line",
    ]
    _stub("app.services.fundamentals", **{n: (lambda *a, **k: "") for n in _fund_fns})
    _stub("app.services.journal_context", build_journal_context_block=lambda *a, **k: "")
    _stub("app.services.llm_gateway", ChatMessage=object)
    _stub("app.services.technicals", range_position_pct=lambda *a, **k: 0.0)

    path = os.path.join(BACKEND, "app", "services", "room_prompts.py")
    spec = importlib.util.spec_from_file_location("app.services.room_prompts", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["app.services.room_prompts"] = mod
    spec.loader.exec_module(mod)
    _ROOM_PROMPTS = mod
    return mod


def stance_format(*, with_size: bool) -> str:
    """The live [STANCE: ...] envelope contract the Matrix Console actually parses.

    DEF251 measured 20% of debator turns emitting NO envelope at all — recipes 12,
    13 and 15 train this compliance structurally rather than by asking louder.
    """
    rp = _load_room_prompts()
    return rp._STANCE_FORMAT_RISK if with_size else rp._STANCE_FORMAT


def headline_max() -> int:
    return int(_load_room_prompts().STANCE_HEADLINE_MAX_CHARS)


def stance_line(stance: str, conviction: str, headline: str, size_pct=None) -> str:
    """Render one envelope, truncating HEADLINE to the live production limit."""
    cap = headline_max()
    h = headline if len(headline) <= cap else headline[: cap - 1].rstrip() + "…"
    size = f" SIZE: {size_pct:.1f}% |" if size_pct is not None else ""
    return f"[STANCE: {stance} | CONVICTION: {conviction} |{size} HEADLINE: {h}]"


_MONEY = re.compile(r"\$[\d,]+(?:\.\d+)?[TBM]?")
_PCT = re.compile(r"[-+]?\d+(?:\.\d+)?(?=%|pt)")


def assert_grounded(text: str, allowed: set, where: str):
    """Every $ figure and every percentage in a target must be one the generator computed.

    Raises rather than warns: a drifting renderer fails the build instead of
    quietly shipping a hallucinated number into the weights.
    """
    for tok in _MONEY.findall(text):
        if tok not in allowed:
            raise AssertionError(f"{where}: ungrounded money token {tok!r}")
    for tok in _PCT.findall(text):
        if tok not in allowed:
            raise AssertionError(f"{where}: ungrounded pct token {tok!r}")


def money(v, sink: set) -> str:
    """fmt_b + register the rendered token as grounded."""
    s = fmt_b(v)
    sink.add(s)
    return s


def pct(v, sink: set, signed=True) -> str:
    """Render a ratio as a percentage string and register it as grounded."""
    s = f"{v * 100:+.1f}" if signed else f"{v * 100:.1f}"
    sink.add(s)
    return s


def num(v, sink: set, fmt="{:.1f}") -> str:
    s = fmt.format(v)
    sink.add(s)
    return s
