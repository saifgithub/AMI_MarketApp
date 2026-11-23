#!/usr/bin/env python3
"""CR267 WP-22 step 3 — score a narrow-question grader on finished WP-20 Rooms.

Why: WP-22 asks which grader (Jev, the hosted model, plain code over cards) can
replace the CIO's free-text verdict. This tool runs one grader over the stored
Rooms and scores it the way the plan says: answer distribution per question,
fresh-room stability across the two reps, consensus scores (approvals of Street
Sell names, share of approvals that are Street Buy per risk level) beside the
CIO's numbers on the SAME Rooms, latency per Room, and an optional wording test.

Reads only. Rooms come from Alpha's `room_runs` (the persisted transcript is the
exact AgentMessage list `room_runner._coded_transcript` hands a grader in
production); the CIO's own turn (`portfolio_manager`) is dropped, so the grader
never sees the verdict it is being compared with. The DB connection is opened
read-only at the session level, and the gateway's `llm_audit` write is stubbed
out, so nothing is written to Alpha's database.

Modes
  score    run the grader over Rooms -> one JSONL row per Room (resumable).
           Needs the deployed image (imports app.services.room_graders) and
           WP22_DSN. Concurrency defaults to 1.
  wording  the same Rooms through each of the five question phrasings -> JSONL.
  inputs   WP-22 3.3 input tests with known answers: 20 stride-sampled Rooms, each graded
           as the original, an original regrade (noise control) and five code-built
           perturbations (planted fatal flaw, bear evidence removed, bear numbers
           strengthened, turns reordered, ticker renamed) -> JSONL (resumable).
  report   markdown tables from the JSONL files; needs no DB and no network.

Code grader (--grader code, WP-22 §2.3): plain code over the CR266 typed cards of a cards-ON Room
(WP-20 arm 2), no model call, $0, no key, no vLLM. `score` rebuilds each Room's cards from Alpha's
`llm_audit` (the card blocks are stripped from the stored transcript, so the audit turns are the only
record), shapes them for `CodeCardsGrader` and writes the same JSONL rows, so `report` works unchanged
and adds a completeness section (a missing cell is "not computable", never imputed). `wording` and
`inputs` do not apply to it: the grader reads cards and the structured trade only, never turn prose, so
a prose perturbation or rephrasing cannot reach it. `--trade-action` adds an `action` to the proposed
trade (a sensitivity run; the production shape has none, which makes `trade_proposed` not computable).

Graders (--grader). `onprem` (default) is the vLLM slot, free, unchanged. `jev` and
`deepinfra` spend money: their keys (JEV_API_KEY, DEEPINFRA_API_KEY) come only from the
container environment, put there by `wp22_run.sh` via `--env-from-file ~/cr267_wp20/bakeoff.env`;
a missing key stops the run naming the key, never its value. Jev is pinned (--jev-version,
default jev-1.13.0, "latest" refused). DeepInfra runs on the gateway's hosted slot
(`vllm_fallback`, kind openai) with --model pinned. --max-usd (default 5.00) is enforced from
each result's cost_usd; a result with no cost (unpriced) counts toward --max-calls (default
300) instead. The run stops cleanly when a cap is hit; `<out>.meta.json` records spend and
the cap; rerun resumes.

Run on melehost in a throwaway container of the deployed image (see
wp22_run.sh beside this file): WP22_DSN is the read-only Postgres DSN,
DATABASE_URL is pointed at a scratch sqlite so no app code can reach Alpha's DB.

Usage
  wp22_score.py score  --runs runs_wp20-arm1.jsonl --out scores.jsonl \
      [--pilot 10 | --limit N] [--concurrency 1] [--slot vllm] \
      [--grader onprem|jev|deepinfra|cheapllm|code] [--trade-action buy] [--jev-version jev-1.13.0] [--model <deepinfra id>] \
      [--max-usd 5.00] [--max-calls 300]
  wp22_score.py wording --runs ... --out wording.jsonl [--sample 20]
  wp22_score.py report --runs runs_wp20-arm1.jsonl --scores scores.jsonl \
      [--wording wording.jsonl] [--inputs inputs.jsonl] --out report.md
  wp22_score.py inputs --runs ... --out inputs.jsonl [--sample 20]
  wp22_score.py fit    --scores scores.jsonl [--inputs inputs.jsonl] [--max-contested 0.20] [--out fit.json]

WP-23 close-cut fit. `--grader deepinfra_room` is the grader production runs (phrasing averaging,
structured trade, direct client; needs `--trade-action buy` because the stored Rooms carry no
Execution Desk side). `fit` then re-applies the rule offline (no DB, no network, no key) under each
candidate `close_below_confidence` and prints the value that minimises rep disagreement within the
Contested cap, plus the `ROOM_CODED_RULE_POLICY_JSON` to set. Consensus is never read.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import dataclasses
import json
import os
import random
import re
import statistics
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve()
REPO = _HERE.parents[4] if len(_HERE.parents) > 4 else None
for _p in ((REPO / "backend",) if REPO else ()) + (Path("/app"),):
    if (_p / "app").is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.services.room_decision_rule import DEFAULT_POLICY, decide  # noqa: E402
from app.services.room_grader_contract import (  # noqa: E402
    QUESTION_SET_VERSION,
    Answer,
    GraderResult,
    QuestionAnswer,
    QuestionId,
    RoomTranscript,
    build_cards_payload,
    build_proposed_trade,
)

CIO_AGENT = "portfolio_manager"
RISKS = (1, 2, 3, 4, 5)
QIDS = [q.value for q in QuestionId]
PHRASINGS = (0, 1, 2, 3, 4)
_ARM_REP = re.compile(r"-rep(\d+)$")
ROOM_TIMEOUT_S = 600.0

# ── Hosted graders (Jev, DeepInfra): pins, prices, keys, spend cap ──────────
GRADERS = ("onprem", "jev", "deepinfra", "cheapllm", "code", "deepinfra_room")
# Pinned, never "latest" (WP-23 policy key). Source: S12 plan §3 item 1 and the October
# corpus (`jev_deep_dive_2026-10-14.md`), which logged `jev-1.13.0`; the CR257 pilot script
# sent "jev-latest", which is exactly what production must not do.
JEV_DEFAULT_VERSION = "jev-1.13.0"
# USD per 1M INPUT tokens, outputs not billed: the constant `jev_v1_pilot.py` prices its
# own usage line with (`total_in / 1_000_000 * 0.042`). Unverified against an invoice; when a
# Jev reply carries no `usage.input_tokens` the cap falls back to --max-calls.
JEV_USD_PER_M_INPUT = 0.042
# Beta's primary model (S11 plan section 3b ruling; `infra/beta.env.example` VLLM_MODEL).
DEEPINFRA_DEFAULT_MODEL = "deepseek-ai/DeepSeek-V4-Flash"
DEEPINFRA_BASE_URL = "https://api.deepinfra.com/v1/openai"
# CheapLLM (Saiful, 2026-11-22): OpenAI-compatible; its /v1/models listed exactly one model on
# 2026-11-22. No price is published here, so its runs are capped by --max-calls.
CHEAPLLM_BASE_URL = "https://cheapllm.shop/v1"
CHEAPLLM_DEFAULT_MODEL = "deepseek-v4.1-flash-1017"
HOSTED_BASE_URL = {"deepinfra": DEEPINFRA_BASE_URL, "cheapllm": CHEAPLLM_BASE_URL}
# USD per 1M in/out, as `infra/beta.env.example` LLM_PRICES_JSON; a model outside this table
# is unpriced unless --price-in/--price-out say otherwise (then the cap counts calls).
DEEPINFRA_PRICES = {
    "deepseek-ai/DeepSeek-V4-Flash": (0.09, 0.18),
    "inclusionAI/Ling-3.0-flash": (0.06, 0.18),
}
# The gateway's hosted OpenAI-compatible slot (CR272/CR281): configured, not hardcoded.
HOSTED_SLOT = "vllm_fallback"
KEY_FILE_NAME = "bakeoff.env"
KEY_ENV = {"jev": "JEV_API_KEY", "deepinfra": "DEEPINFRA_API_KEY", "cheapllm": "CHEAPLLM_API_KEY",
           "deepinfra_room": "DEEPINFRA_API_KEY"}
DEFAULT_MAX_USD = 5.00
DEFAULT_MAX_CALLS = 300
# deepinfra_room (the grader production runs, WP-23): 3 single-call questions + 2 fragile questions x 5
# phrasings; trade_proposed is code-owned, never asked.
CALLS_PER_ROOM = {"jev": 1, "deepinfra": len(QuestionId), "cheapllm": len(QuestionId),
                  "deepinfra_room": 13}


class BakeoffKeyError(Exception):
    """A key the chosen grader needs is not in the environment. Names only, never values."""


def require_key(grader: str, env: dict | None = None) -> str:
    """The grader's key from the environment (put there by `--env-from-file bakeoff.env`).
    Raises with the key NAME only; the value is never printed or logged by this tool."""
    name = KEY_ENV[grader]
    value = ((env if env is not None else os.environ).get(name) or "").strip()
    if not value:
        raise BakeoffKeyError(f"{KEY_FILE_NAME} missing {name}")
    return value


@dataclasses.dataclass
class SpendGuard:
    """Hard stop for the paid graders. USD is summed from each result's `cost_usd`; calls
    are counted only for results with no cost (unpriced), so a priced run is capped by
    money and an unpriced one by call count. Checked before each Room starts, so with
    concurrency N a run can overshoot by at most N-1 Rooms."""
    max_usd: float
    max_calls: int
    fallback_calls: int
    usd: float = 0.0
    graded: int = 0
    priced: int = 0
    unpriced_calls: int = 0
    skipped: int = 0
    hit: str | None = None

    def record(self, res: GraderResult) -> None:
        self.graded += 1
        if res.cost_usd is not None:
            self.priced += 1
            self.usd += res.cost_usd
        else:
            self.unpriced_calls += int((res.extra or {}).get("calls") or self.fallback_calls)

    def exceeded(self) -> str | None:
        if self.usd >= self.max_usd:
            self.hit = self.hit or "max_usd"
        elif self.unpriced_calls >= self.max_calls:
            self.hit = self.hit or "max_calls"
        return self.hit

    def summary(self) -> dict:
        return {
            "max_usd": self.max_usd, "max_calls": self.max_calls, "usd_spent": round(self.usd, 6),
            "rooms_graded": self.graded, "rooms_priced": self.priced,
            "unpriced_calls": self.unpriced_calls, "rooms_skipped_by_cap": self.skipped,
            "cap_hit": self.hit,
            "cap_basis": "usd from cost_usd where priced; --max-calls counts unpriced calls only",
        }


class JevAsync:
    """JevGrader behind the same `agrade` the hosted grader has: the blocking HTTP call runs
    in a thread, and the cost is filled from `usage.input_tokens` x JEV_USD_PER_M_INPUT."""
    def __init__(self, inner) -> None:
        self._inner = inner

    async def agrade(self, transcript: RoomTranscript) -> GraderResult:
        res = await asyncio.to_thread(self._inner.grade, transcript)
        return price_jev(res)


class CodeAsync:
    """CodeCardsGrader behind the same `agrade` the other graders have. Pure code, so it runs inline."""
    def __init__(self, inner) -> None:
        self._inner = inner

    async def agrade(self, transcript: RoomTranscript) -> GraderResult:
        return self._inner.grade(transcript)


def price_jev(res: GraderResult) -> GraderResult:
    if res.cost_usd is not None or res.error:
        return res
    tokens = (res.extra or {}).get("usage") or {}
    tokens = tokens.get("input_tokens") if isinstance(tokens, dict) else None
    if isinstance(tokens, bool) or not isinstance(tokens, (int, float)):
        return res
    return dataclasses.replace(res, cost_usd=tokens * JEV_USD_PER_M_INPUT / 1_000_000)


def configure_hosted_slot(model: str, key: str, prices: tuple[float, float] | None,
                          settings=None, base_url: str = DEEPINFRA_BASE_URL) -> None:
    """Point the gateway's hosted slot at DeepInfra and nothing else. Done on the in-process
    `settings` (the key never goes through a command line or a log) before the gateway is
    first built: slot `vllm_fallback`, kind openai, only that slot allowed, no on-prem."""
    if settings is None:
        from app.core.config import settings  # noqa: PLC0415
    settings.vllm_fallback_base_url = base_url
    settings.vllm_fallback_model = model
    settings.vllm_fallback_kind = "openai"
    settings.vllm_fallback_api_key = key
    settings.vllm_fallback_extra_body_json = ""
    settings.vllm_base_url = ""
    settings.llm_provider_allowlist = [HOSTED_SLOT]
    settings.llm_prices_json = json.dumps(
        {model: {"in": prices[0], "out": prices[1]}} if prices else {})


@dataclasses.dataclass
class GraderSetup:
    kind: str
    label: str
    factory: object
    guard: SpendGuard | None
    describe: dict


def setup_grader(args: argparse.Namespace, env: dict | None = None) -> GraderSetup:
    """Validate the grader choice, load its key from the environment, build the factory
    (phrasing -> grader). Raises BakeoffKeyError / ValueError; the caller prints and exits."""
    kind = getattr(args, "grader", "onprem")
    if kind == "onprem":
        def onprem(p):
            from app.services.room_graders.hosted_llm import HostedLLMGrader
            return HostedLLMGrader(args.slot, phrasing=p)
        return GraderSetup("onprem", "on-prem vLLM", onprem, None, {})
    if kind == "code":
        def code(_p):
            from app.services.room_graders.code_cards import CodeCardsGrader
            return CodeAsync(CodeCardsGrader())
        return GraderSetup("code", "code_cards cards-1 (no model, $0)", code, None, {
            "trade_action": getattr(args, "trade_action", None)})
    guard = SpendGuard(float(args.max_usd), int(args.max_calls), CALLS_PER_ROOM[kind])
    if guard.max_usd <= 0 or guard.max_calls <= 0:
        raise ValueError("--max-usd and --max-calls must be positive")
    key = require_key(kind, env)
    if kind == "jev":
        version = (args.jev_version or "").strip()
        from app.services.room_graders.jev import JevGrader
        JevGrader(version)  # refuses empty / "latest" before any call

        def jev(p):
            return JevAsync(JevGrader(version, api_key=key, phrasing=p))
        return GraderSetup("jev", f"Jev {version}", jev, guard, {
            "jev_version": version, "price_per_m_input_usd": JEV_USD_PER_M_INPUT,
            "price_source": "jev_v1_pilot.py constant, unverified"})
    if kind == "deepinfra_room":
        return _setup_deepinfra_room(args, key, guard)
    model = (args.model or "").strip()
    if kind == "cheapllm" and model == DEEPINFRA_DEFAULT_MODEL:
        model = CHEAPLLM_DEFAULT_MODEL
    if not model or model.lower().endswith("latest"):
        raise ValueError("--model must be a pinned model id, never empty or 'latest'")
    prices = DEEPINFRA_PRICES.get(model) if kind == "deepinfra" else None
    if args.price_in is not None and args.price_out is not None:
        prices = (float(args.price_in), float(args.price_out))
    base_url = HOSTED_BASE_URL[kind]
    configure_hosted_slot(model, key, prices, base_url=base_url)
    label = {"deepinfra": "DeepInfra", "cheapllm": "CheapLLM"}[kind]

    def hosted(p):
        from app.services.room_graders.hosted_llm import HostedLLMGrader
        return HostedLLMGrader(HOSTED_SLOT, version=f"hosted:{kind}:{model}", phrasing=p)
    return GraderSetup(kind, f"{label} {model}", hosted, guard, {
        "model": model, "base_url": base_url, "slot": HOSTED_SLOT,
        "prices_usd_per_m_in_out": list(prices) if prices else None})


def _setup_deepinfra_room(args: argparse.Namespace, key: str, guard: SpendGuard) -> GraderSetup:
    """The grader production runs (WP-23 gate S3): `DeepInfraGrader` with its phrasing averaging,
    structured `trade_proposed` and direct client, so a fit scores exactly what ships. The offline
    Rooms carry no Execution Desk side, so `--trade-action` stands in for it on every Room."""
    model = (args.model or "").strip()
    if not model or model.lower().endswith("latest"):
        raise ValueError("--model must be a pinned model id, never empty or 'latest'")
    if not (getattr(args, "trade_action", None) or "").strip():
        raise ValueError("--trade-action is required for --grader deepinfra_room (the stored Rooms "
                         "carry no Execution Desk side; `buy` = every Room proposed a trade)")
    prices = DEEPINFRA_PRICES.get(model)
    if args.price_in is not None and args.price_out is not None:
        prices = (float(args.price_in), float(args.price_out))
    from app.core.config import settings  # noqa: PLC0415
    settings.llm_prices_json = json.dumps({model: {"in": prices[0], "out": prices[1]}} if prices else {})

    def room(_p):
        from app.services.room_graders.deepinfra import DeepInfraGrader
        return DeepInfraGrader(base_url=DEEPINFRA_BASE_URL, model=model, api_key=key, timeout_s=30.0)
    from app.services.room_graders.deepinfra import grader_version  # noqa: PLC0415
    return GraderSetup("deepinfra_room", f"DeepInfra production grader {grader_version(model)}", room,
                       guard, {"model": model, "base_url": DEEPINFRA_BASE_URL,
                               "prices_usd_per_m_in_out": list(prices) if prices else None,
                               "trade_action": args.trade_action})


# ── Identity, selection ─────────────────────────────────────────────────────

def parse_rep(arm_key: str) -> str:
    m = _ARM_REP.search(arm_key or "")
    if not m:
        raise ValueError(f"arm_key without a rep: {arm_key!r}")
    return m.group(1)


def load_arms(path: Path) -> list[dict]:
    arms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("status") == "completed":
            arms.append(r)
    return arms


def stride_sample(arms: list[dict], n: int) -> list[dict]:
    """n arms spread evenly over (risk, ticker, rep) order so every risk level is hit."""
    ordered = sorted(arms, key=lambda a: (int(a["risk_score"]), a["ticker"], a["arm_key"]))
    if n >= len(ordered):
        return ordered
    return [ordered[(i * len(ordered)) // n + (len(ordered) // (2 * n))] for i in range(n)]


def street_fields(arm: dict) -> tuple[str | None, str | None]:
    s = (arm.get("verdict") or {}).get("street_comparison") or {}
    if s.get("status") != "available":
        return None, None
    return s.get("street_rating"), s.get("street_stance")


# ── Transcript reconstruction ───────────────────────────────────────────────

def proposed_trade(arm: dict, risk: int, cap_override: float | None) -> dict:
    """Mirror room_runner's ctx.trader_* (base price x 1.0 / 0.94 / 1.13, size = the
    mandate's single-name cap) — production hands graders this same block."""
    from app.trading_math.sizing import resolved_single_name_cap_pct

    base = (arm.get("verdict") or {}).get("reference_price") or arm.get("spot_price") or 100.0
    return build_proposed_trade(
        action=None,
        size_pct=resolved_single_name_cap_pct(risk, cap_override),
        entry=round(base, 2),
        stop=round(base * 0.94, 2),
        target=round(base * 1.13, 2),
    )


# The WP-20 harness hands every Room the same mandate shape (library/runner.py
# base_mandate: horizon "long", no single-name cap override) and writes no `mandates`
# row for the arm users, so there is nothing to look up.
WP20_MANDATE = {"horizon": "long", "single_name_cap_pct": None}


def build_transcript(arm: dict, room: dict, mandate: dict | None = None) -> RoomTranscript:
    """RoomTranscript from one room_runs row: every desk turn BEFORE the CIO's,
    in stored order. The CIO's turn(s) are dropped — the grader must not see the
    verdict."""
    risk = int(arm["risk_score"])
    turns = []
    for m in room["transcript"] or []:
        if m.get("agent_id") == CIO_AGENT:
            continue
        turns.append({"agent_id": m.get("agent_id"), "content": m.get("content") or ""})
    mandate = mandate or WP20_MANDATE
    horizon = mandate.get("horizon")
    return RoomTranscript(
        room_id=str(room["id"]),
        ticker=arm["ticker"],
        risk_score=risk,
        horizon=str(horizon) if horizon is not None else None,
        turns=turns,
        cards=room.get("cards"),
        proposed_trade=_with_action(
            proposed_trade(arm, risk, mandate.get("single_name_cap_pct")), room.get("trade_action")),
    )


def _with_action(trade: dict, action: str | None) -> dict:
    return {**trade, "action": action} if action else trade


# ── CR266 cards, rebuilt from the audit trail (code grader) ─────────────────
# The stored room_runs transcript carries the desks' PROSE only: the runner strips the [CLAIMS] and
# [OBJECTIONS] blocks before it persists a turn and keeps the typed cards on `ctx.claim_cards`, which
# is not stored. The only record is each evidence desk's raw turn in `llm_audit`, so the cards are
# re-parsed from there with the backend's own `parse_claim_cards`. Same window rule as
# `evidence_card_report.py`: the arm's user, its [triggered_at, finished_at] window, three flows.

CARD_DESKS = ("fundamentals_analyst", "bull_researcher", "bear_researcher", "research_manager")
CARD_FLOWS = ("room", "room_envelope_repair", "room_cards_repair")
CARDS_REPAIR_FLOW = "room_cards_repair"
WINDOW_SLACK_S = 0.001


def card_tools() -> tuple:
    """(parse_claim_cards, _cards_channel_complete) from the deployed backend. Imported lazily:
    room_runner pulls the whole app, so only the code-grader path (and its tests) pays for it."""
    from app.services.room_runner import _cards_channel_complete, parse_claim_cards  # noqa: PLC0415
    return parse_claim_cards, _cards_channel_complete


def fetch_card_turns(dsn: str, arms: list[dict]) -> dict[str, list[dict]]:
    """{arm_key: that Room's successful evidence-desk turns, in insertion order}. Read-only."""
    from sqlalchemy import text

    eng = readonly_engine(dsn)
    by_user: dict[str, list[dict]] = collections.defaultdict(list)
    with eng.connect() as c:
        rows = c.execute(text(
            "SELECT user_id::text AS user_id, agent_id, flow, response_text, "
            "extract(epoch from created_at)::float8 AS epoch "
            "FROM llm_audit WHERE user_id = ANY(CAST(:u AS uuid[])) AND flow = ANY(:f) "
            "AND agent_id = ANY(:d) AND error IS NULL AND response_text IS NOT NULL "
            "ORDER BY created_at ASC, ctid ASC"
        ), {"u": [a["user_id"] for a in arms], "f": list(CARD_FLOWS), "d": list(CARD_DESKS)}).mappings().all()
        for r in rows:
            by_user[r["user_id"]].append(dict(r))
    out = {}
    for a in arms:
        lo = datetime.fromisoformat(a["triggered_at"]).timestamp() - WINDOW_SLACK_S
        hi = datetime.fromisoformat(a["finished_at"]).timestamp() + WINDOW_SLACK_S
        out[a["arm_key"]] = [r for r in by_user.get(a["user_id"], []) if lo <= r["epoch"] <= hi]
    return out


def cards_for_room(turns: list[dict], sheet_state: dict | None, tools: tuple | None = None) -> tuple[dict | None, dict]:
    """The `cards` a CodeCardsGrader reads, plus a small provenance dict.

    Each desk's cards come from its LAST successful turn, except where that last turn is a cards
    re-ask (`room_cards_repair`) whose channel is still incomplete: the runner rejects such a retry
    and keeps the turn before it, so this does too. A desk with no parseable card is left out, as
    the runner leaves it out of `ctx.claim_cards`; no desk with cards at all gives None (the grader
    then answers "room ran without cards"). A missing desk or card is never filled in.
    The envelope re-ask (`room_envelope_repair`) is taken as adopted whenever it produced a turn.
    """
    from dataclasses import asdict

    parse, complete = tools or card_tools()
    by_desk: dict[str, list[dict]] = collections.defaultdict(list)
    for t in turns:
        by_desk[t["agent_id"]].append(t)
    channels: dict[str, dict] = {}
    meta: dict = {"desks_with_cards": 0, "desks_complete": 0, "cards": 0, "fallback_desks": [],
                  "desks_without_turn": [], "malformed_cards": 0, "malformed_objections": 0}
    for desk in CARD_DESKS:
        rows = by_desk.get(desk) or []
        if not rows:
            meta["desks_without_turn"].append(desk)
            continue
        use = rows[-1]
        _, ch = parse(use["response_text"])
        if use["flow"] == CARDS_REPAIR_FLOW and len(rows) > 1 and not complete(ch):
            use = rows[-2]
            _, ch = parse(use["response_text"])
            meta["fallback_desks"].append(desk)
        if ch is None:
            continue
        meta["malformed_cards"] += ch.malformed_cards
        meta["malformed_objections"] += ch.malformed_objections
        if not ch.cards:
            continue
        channels[desk] = asdict(ch)
        meta["desks_with_cards"] += 1
        meta["desks_complete"] += bool(complete(ch))
        meta["cards"] += len(ch.cards)
    if not channels:
        return None, meta
    return build_cards_payload(channels, sheet_state), meta


def attach_cards(rooms: dict, arms: list[dict], turns: dict[str, list[dict]], tools: tuple | None = None) -> None:
    """Put `cards` and `cards_meta` on each Room dict (in place) for `build_transcript`."""
    tools = tools or card_tools()
    for a in arms:
        room = rooms.get(a["arm_key"])
        if room is not None:
            room["cards"], room["cards_meta"] = cards_for_room(
                turns.get(a["arm_key"], []), (a.get("verdict") or {}).get("sheet_state"), tools)


# ── Input-test perturbations (WP-22 3.3) ────────────────────────────────────
# Every perturbation is built in code, deterministically, from the stored Room. No model
# writes any of them. They take a RoomTranscript (CIO turn already dropped by
# build_transcript) and return a new one plus a small meta dict, or None when the Room
# has nothing to perturb.

BEAR_AGENT = "bear_researcher"
PERTURBATIONS = ("original", "original_repeat", "planted_flaw", "bear_removed",
                 "bear_strengthened", "turns_reordered", "ticker_renamed")
TESTS = PERTURBATIONS[2:]
REORDER_SEED = 22
STRENGTHEN_FACTOR = 2

PLANTED_FLAW_TEXT = (
    "Terminal risk, disclosed this week: the company stated that it cannot meet a "
    "$2.4 billion debt maturity due in 30 days, holds only $310 million of cash and has "
    "no committed refinancing; its auditors issued a going-concern warning and total "
    "debt is now 9.0x EBITDA."
)
BEAR_REMOVED_TEXT = "The bear desk is cautious on this name and would wait."

# Sentences of a Bear turn that make a downside / leverage claim. Only numbers inside
# these sentences are scaled.
_DOWNSIDE = re.compile(
    r"downside|declin|drop|fall|fell|loss|drawdown|lever|debt|risk|miss|cut|compress|"
    r"shortfall|worst|stress|haircut|impair|write-?down|eros|contraction|deteriorat|sell-?off|"
    r"dilut|default|covenant|pressure|slump|plung|crash", re.I)
# A magnitude directly attached to %, x / × or $ (with an optional K/M/B/T or word unit).
_NUM = re.compile(
    r"(?P<dollar>\$\s?)(?P<d>\d[\d,]*(?:\.\d+)?)(?P<unit>\s?(?:[KMBT]\b|million|billion|trillion|bn\b|mm\b))?"
    r"|(?P<p>\d[\d,]*(?:\.\d+)?)(?P<pct>\s?%)"
    r"|(?P<m>\d[\d,]*(?:\.\d+)?)(?P<x>\s?[x×])(?![A-Za-z])")

_NAME_SUFFIX1 = re.compile(
    r"[,.]?\s+(?:Inc|Incorporated|Corp|Corporation|Company|Co|Ltd|Limited|plc|PLC|LLC|"
    r"Holdings?|Group|Global|International|Class [A-Z]|Common Stock|Ordinary Shares?|"
    r"Common Shares?|Depositary Shares?)\b\.?\s*$")


def _scale_number(raw: str, factor: int) -> str:
    val = float(raw.replace(",", "")) * factor
    decimals = len(raw.split(".")[1]) if "." in raw else 0
    return f"{val:,.{decimals}f}" if "," in raw else f"{val:.{decimals}f}"


def strengthen_numbers(text: str, factor: int = STRENGTHEN_FACTOR) -> tuple[str, int]:
    """Multiply by `factor` every magnitude attached to %, x or $ inside a sentence that
    makes a downside / leverage claim (_DOWNSIDE). Sentences split on [.!?] followed by
    whitespace, and on newlines. Returns (new text, count of numbers scaled)."""
    count = 0

    def sub(m: re.Match) -> str:
        nonlocal count
        count += 1
        if m.group("d") is not None:
            return f"{m.group('dollar')}{_scale_number(m.group('d'), factor)}{m.group('unit') or ''}"
        if m.group("p") is not None:
            return f"{_scale_number(m.group('p'), factor)}{m.group('pct')}"
        return f"{_scale_number(m.group('m'), factor)}{m.group('x')}"

    parts = re.split(r"((?<=[.!?])\s+|\n+)", text)
    for i in range(0, len(parts), 2):
        if _DOWNSIDE.search(parts[i]):
            parts[i] = _NUM.sub(sub, parts[i])
    return "".join(parts), count


def name_variants(company_name: str | None) -> list[str]:
    """Longest-first spellings of a company name to replace: the listing name, then the
    name with each trailing suffix ('Common Stock', 'Inc.', 'Corporation', ...) stripped in
    turn ('Danaher Corporation Common Stock' -> 'Danaher Corporation' -> 'Danaher'), and
    without a leading 'The'."""
    if not company_name:
        return []
    cur = re.split(r"\s+-\s+", company_name.strip())[0]
    seen = {cur}
    for _ in range(6):
        nxt = _NAME_SUFFIX1.sub("", cur).strip(" ,.&")
        if nxt == cur or not nxt:
            break
        seen.add(nxt)
        cur = nxt
    seen |= {v[4:] for v in seen if v.lower().startswith("the ")}
    return sorted((v for v in seen if len(v) >= 3 and not v.lower().startswith("the ")),
                  key=len, reverse=True)


def _word(s: str) -> str:
    return rf"(?<![A-Za-z0-9]){re.escape(s)}(?![A-Za-z0-9])"


def rename_text(text: str, ticker: str, names: list[str]) -> str:
    for n in names:
        text = re.sub(_word(n), "Company X", text)
    return re.sub(_word(ticker), "TICKR", text)


def _bear_idx(tr: RoomTranscript) -> list[int]:
    return [i for i, t in enumerate(tr.turns) if t.get("agent_id") == BEAR_AGENT]


def perturb(kind: str, tr: RoomTranscript, company_name: str | None = None):
    """(perturbed transcript, meta) for one named perturbation, or None when the Room
    has nothing to perturb (no Bear turn, or no downside number to scale)."""
    turns = [dict(t) for t in tr.turns]
    swap = lambda new, **kw: dataclasses.replace(tr, turns=new, **kw)  # noqa: E731
    if kind in ("original", "original_repeat"):
        return tr, {}
    if kind in ("planted_flaw", "bear_removed", "bear_strengthened"):
        idx = _bear_idx(tr)
        if not idx:
            return None
        if kind == "planted_flaw":
            turns[idx[-1]]["content"] = turns[idx[-1]]["content"].rstrip() + "\n\n" + PLANTED_FLAW_TEXT
            return swap(turns), {"bear_turns": len(idx)}
        if kind == "bear_removed":
            for n, i in enumerate(idx):
                turns[i]["content"] = BEAR_REMOVED_TEXT if n == 0 else ""
            return swap([t for t in turns if t["content"]]), {"bear_turns": len(idx)}
        changed = 0
        for i in idx:
            turns[i]["content"], c = strengthen_numbers(turns[i]["content"])
            changed += c
        if changed == 0:
            return None
        return swap(turns), {"numbers_scaled": changed, "factor": STRENGTHEN_FACTOR}
    if kind == "turns_reordered":
        order = list(range(len(turns)))
        random.Random(REORDER_SEED).shuffle(order)
        if order == sorted(order):
            order.reverse()
        return swap([turns[i] for i in order]), {"order": order}
    if kind == "ticker_renamed":
        names = name_variants(company_name)
        new = [{**t, "content": rename_text(t["content"], tr.ticker, names)} for t in turns]
        left = len(re.findall(_word(tr.ticker), " ".join(t["content"] for t in new), re.I))
        return swap(new, ticker="TICKR"), {"names": names, "ticker_left": left}
    raise ValueError(f"unknown perturbation {kind!r}")


# ── Input-test verdicts ─────────────────────────────────────────────────────

CAUTION = {"APPROVE": 0, "CONTESTED": 1, "PASS": 2}
CONF_EPS = 0.01


def p_yes(row: dict, q: str) -> float | None:
    a = (row.get("answers") or {}).get(q)
    if not a or a["answer"] == "not_computable" or a.get("confidence") is None:
        return None
    return a["confidence"] if a["answer"] == "yes" else 1.0 - a["confidence"]


def outcome_at(row: dict, risk: int, policy=DEFAULT_POLICY) -> str:
    if row.get("error") or not row.get("answers"):
        return "UNAVAILABLE"
    return decide(row_to_result(row), risk, policy).outcome.value


def judge(kind: str, orig: dict, row: dict, policy=DEFAULT_POLICY) -> tuple[str, str]:
    """(pass | fail | na, why) for one perturbed row against its expectation, computed
    from the stored answers so the rule can change without re-running the grader.
    More cautious = APPROVE < CONTESTED < PASS."""
    if orig.get("error") or not orig.get("answers") or row.get("error") or not row.get("answers"):
        return "na", "grade missing or errored"
    risk = int(row["risk"])
    o0, o1 = outcome_at(orig, risk, policy), outcome_at(row, risk, policy)
    if kind == "planted_flaw":
        tv = (row["answers"].get("terminal_vulnerability") or {}).get("answer")
        bad = [f"R{r}={o}" for r in RISKS if (o := outcome_at(row, r, policy)) != "PASS"]
        ok = tv == "yes" and not bad
        return ("pass" if ok else "fail"), f"terminal_vulnerability={tv}; " + (
            "PASS at R1-R5" if not bad else "not PASS at " + ",".join(bad))
    if kind == "bear_removed":
        return ("pass" if CAUTION[o1] <= CAUTION[o0] else "fail"), f"{o0} -> {o1}"
    if kind == "bear_strengthened":
        a, b = p_yes(orig, "bear_objection_answered"), p_yes(row, "bear_objection_answered")
        if a is None or b is None:
            return "na", "no P(yes) on bear_objection_answered"
        ok = b <= a + CONF_EPS and CAUTION[o1] >= CAUTION[o0]
        return ("pass" if ok else "fail"), f"P(yes) {a:.2f} -> {b:.2f}; {o0} -> {o1}"
    if kind in ("turns_reordered", "ticker_renamed", "original_repeat"):
        diff = [q for q in QIDS if (orig["answers"].get(q) or {}).get("answer")
                != (row["answers"].get(q) or {}).get("answer")]
        dconf = max((abs((orig["answers"][q].get("confidence") or 0)
                         - (row["answers"][q].get("confidence") or 0))
                     for q in QIDS if q in orig["answers"] and q in row["answers"]), default=0.0)
        return ("pass" if not diff else "fail"), (
            ("all six answers unchanged" if not diff else "changed: " + ",".join(diff))
            + f"; max |dconf| {dconf:.2f}; rule {o0} -> {o1}")
    raise ValueError(kind)


# ── Read-only DB ────────────────────────────────────────────────────────────

def readonly_engine(dsn: str):
    from sqlalchemy import create_engine

    return create_engine(dsn, connect_args={"options": "-c default_transaction_read_only=on"})


def pick_room(arm: dict, candidates: list[dict]) -> dict | None:
    """The room_runs row that IS this arm's run: the candidate whose triggered_at is
    closest to the arm's own triggered_at, within 5 s. Two arm users carry an extra
    earlier completed row from an overlapping first attempt (NO_VERDICT / duplicate);
    matching on the timestamp keeps the Room the run record's verdict came from."""
    t = datetime.fromisoformat(arm["triggered_at"]).timestamp()
    best = min(candidates, key=lambda r: abs(r["triggered_epoch"] - t), default=None)
    if best is None or abs(best["triggered_epoch"] - t) > 5:
        return None
    return best


def fetch_rooms(dsn: str, arms: list[dict]) -> dict[str, dict]:
    """{arm_key: room_runs row}, each matched to its arm by user and trigger time."""
    from sqlalchemy import text

    eng = readonly_engine(dsn)
    by_user: dict[str, list[dict]] = collections.defaultdict(list)
    with eng.connect() as c:
        rows = c.execute(text(
            "SELECT id::text AS id, user_id::text AS user_id, ticker, status, mandate_version, "
            "transcript, extract(epoch from triggered_at)::float8 AS triggered_epoch "
            "FROM room_runs WHERE user_id = ANY(CAST(:u AS uuid[])) AND status = 'completed'"
        ), {"u": [a["user_id"] for a in arms]}).mappings().all()
        for r in rows:
            by_user[r["user_id"]].append(dict(r))
    out = {}
    for a in arms:
        room = pick_room(a, by_user.get(a["user_id"], []))
        if room is not None:
            out[a["arm_key"]] = room
    return out


def fetch_names(dsn: str, tickers: list[str]) -> dict[str, str]:
    """{ticker: company_name} from the ticker_reference table (read-only)."""
    from sqlalchemy import text

    eng = readonly_engine(dsn)
    with eng.connect() as c:
        rows = c.execute(text(
            "SELECT symbol, company_name FROM ticker_reference WHERE symbol = ANY(:s)"
        ), {"s": list(tickers)}).all()
    return {r[0]: r[1] for r in rows}


def vllm_model_root(base_url: str) -> str:
    """The served model's real path from /v1/models — never the configured alias."""
    with urllib.request.urlopen(base_url.rstrip("/") + "/v1/models", timeout=10) as r:
        data = json.load(r)["data"]
    return ",".join(sorted({m.get("root") or "?" for m in data}))


# ── Row shape ───────────────────────────────────────────────────────────────

def result_to_row(arm: dict, room_id: str, result: GraderResult | None,
                  *, phrasing: int | None, model_root: str | None, error: str | None = None) -> dict:
    rating, stance = street_fields(arm)
    risk = int(arm["risk_score"])
    row = {
        "run_id": room_id,
        "arm_key": arm["arm_key"],
        "user_id": arm["user_id"],
        "ticker": arm["ticker"],
        "risk": risk,
        "rep": parse_rep(arm["arm_key"]),
        "cio_action": (arm.get("verdict") or {}).get("action"),
        "street_rating": rating,
        "street_stance": stance,
        "phrasing": phrasing,
        "model_root": model_root,
        "answers": {},
        "rule": None,
        "latency_ms": None,
        "cost_usd": None,
        "extra": {},
        "error": error,
    }
    if result is None:
        return row
    row.update(
        grader=result.grader,
        grader_version=result.grader_version,
        question_set_version=result.question_set_version,
        latency_ms=result.latency_ms,
        cost_usd=result.cost_usd,
        extra=dict(result.extra or {}),
        error=result.error or error,
        answers={
            a.question.value: {
                "answer": a.answer.value,
                "confidence": a.confidence,
                "close": a.close,
                **({"rationale": a.rationale} if a.rationale else {}),
            }
            for a in result.answers
        },
    )
    d = decide(result, risk, DEFAULT_POLICY)
    row["rule"] = {
        "outcome": d.outcome.value,
        "close_questions": [q.value for q in d.close_questions],
        "reasons": list(d.reasons),
        "rule_version": d.rule_version,
        "policy_version": d.policy_version,
    }
    return row


def row_to_result(row: dict) -> GraderResult:
    return GraderResult(
        grader=row.get("grader") or "unknown",
        grader_version=row.get("grader_version") or "",
        question_set_version=row.get("question_set_version") or QUESTION_SET_VERSION,
        answers=tuple(
            QuestionAnswer(
                QuestionId(q), Answer(v["answer"]), v.get("confidence"), bool(v.get("close")),
            )
            for q, v in (row.get("answers") or {}).items()
        ),
        latency_ms=int(row.get("latency_ms") or 0),
        error=row.get("error"),
    )


def rule_outcome(row: dict) -> str:
    """The decision rule's outcome for a row, recomputed from the stored answers so
    a rule or policy change re-scores old rows without re-running the grader."""
    if row.get("error") or not row.get("answers"):
        return "UNAVAILABLE"
    return decide(row_to_result(row), int(row["risk"]), DEFAULT_POLICY).outcome.value


# ── Running ─────────────────────────────────────────────────────────────────

def _done_keys(path: Path) -> set[tuple[str, int | None]]:
    done: set[tuple[str, int | None]] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if not r.get("error"):
                    done.add((r["arm_key"], r.get("phrasing")))
    return done


def _install_no_audit_write() -> None:
    """The gateway writes one llm_audit row per call. This is a read-only lane:
    swap the writer for a no-op (DATABASE_URL is also pointed at scratch sqlite)."""
    import app.services.audit as audit

    audit.record_llm_call = lambda **_kw: None  # type: ignore[assignment]


async def run_scoring(arms: list[dict], rooms: dict, out: Path, *,
                      make_grader, phrasings: list[int | None], concurrency: int,
                      model_root: str | None, guard: SpendGuard | None = None, log=print) -> int:
    graders = {p: make_grader(p) for p in phrasings}
    done = _done_keys(out)
    sem = asyncio.Semaphore(max(1, concurrency))
    write_lock = asyncio.Lock()
    errors = 0
    todo = [(a, p) for a in arms for p in phrasings if (a["arm_key"], p) not in done]
    log(f"to run: {len(todo)} (skipping {len(arms) * len(phrasings) - len(todo)} already done)")

    async def one(i: int, arm: dict, p: int | None) -> None:
        nonlocal errors
        room = rooms.get(arm["arm_key"])
        if room is None:
            row = result_to_row(arm, "", None, phrasing=p, model_root=model_root,
                                error="no completed room_runs row for this arm user")
        else:
            tr = build_transcript(arm, room)
            async with sem:
                if guard is not None and guard.exceeded():
                    guard.skipped += 1
                    log(f"[{i + 1}/{len(todo)}] {arm['arm_key']} p={p} SKIPPED: spend cap hit ({guard.hit})")
                    return
                started = time.perf_counter()
                try:
                    res = await asyncio.wait_for(graders[p].agrade(tr), ROOM_TIMEOUT_S)
                    if guard is not None:
                        guard.record(res)
                    row = result_to_row(arm, room["id"], res, phrasing=p, model_root=model_root)
                except Exception as exc:  # noqa: BLE001 — one Room never stops the run
                    row = result_to_row(
                        arm, room["id"], None, phrasing=p, model_root=model_root,
                        error=f"{type(exc).__name__}: {str(exc)[:200]}")
                    row["latency_ms"] = int((time.perf_counter() - started) * 1000)
        if room is not None and room.get("cards_meta") is not None:
            row["extra"]["cards_meta"] = room["cards_meta"]
        if row["error"]:
            errors += 1
        async with write_lock:
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
        log(f"[{i + 1}/{len(todo)}] {arm['arm_key']} p={p} "
            f"{row['latency_ms']}ms rule={(row['rule'] or {}).get('outcome')} "
            f"logprobs={row['extra'].get('logprobs')} err={row['error']}")

    await asyncio.gather(*(one(i, a, p) for i, (a, p) in enumerate(todo)))
    return errors


def _grader_preamble(args: argparse.Namespace) -> tuple[GraderSetup | None, int]:
    """Key and pin checks for the paid graders. They run BEFORE anything touches the DB so a
    missing key fails at once, naming the key and never its value. On-prem: unchanged."""
    if getattr(args, "grader", "onprem") == "onprem":
        return None, 0
    try:
        return setup_grader(args), 0
    except (BakeoffKeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return None, 2


def _model_root(args: argparse.Namespace, setup: GraderSetup | None, base_url: str) -> str:
    if setup is not None:
        return setup.label
    return "dry-run" if getattr(args, "grader", "onprem") != "onprem" else vllm_model_root(base_url)


def _cap_meta(setup: GraderSetup | None) -> dict:
    if setup is None:
        return {}
    return {"grader": setup.kind, "grader_label": setup.label, **setup.describe,
            **({"spend": setup.guard.summary()} if setup.guard is not None else {})}


def _report_cap(setup: GraderSetup | None) -> None:
    if setup is not None and setup.guard is not None and setup.guard.hit:
        print(f"STOPPED BY SPEND CAP ({setup.guard.hit}): {setup.guard.skipped} Rooms not graded; "
              "rerun with a higher cap to resume (finished Rooms are skipped).", file=sys.stderr)


def cmd_run(args: argparse.Namespace, *, wording: bool) -> int:
    setup, rc = _grader_preamble(args)
    if rc:
        return rc
    dsn = os.environ.get("WP22_DSN")
    if not dsn:
        print("WP22_DSN is not set", file=sys.stderr)
        return 2
    if setup is None and args.slot != "vllm":
        print("this lane grades on the on-prem vLLM slot only (--slot vllm)", file=sys.stderr)
        return 2
    if setup is not None and setup.kind == "code" and wording:
        print("--grader code has no wording test: it reads cards and the structured trade, never prose",
              file=sys.stderr)
        return 2
    if setup is not None and setup.kind == "deepinfra_room" and wording:
        print("--grader deepinfra_room averages the phrasings itself; the wording test is for the "
              "single-phrasing graders", file=sys.stderr)
        return 2
    arms = load_arms(Path(args.runs))
    if wording:
        arms = stride_sample(arms, args.sample)
    elif args.pilot:
        arms = stride_sample(arms, args.pilot)
    elif args.limit:
        arms = sorted(arms, key=lambda a: (int(a["risk_score"]), a["ticker"], a["arm_key"]))[: args.limit]
    base_url = os.environ.get("VLLM_BASE_URL", "http://192.168.20.74:8000")
    root0 = _model_root(args, setup, base_url)
    print(f"{'on-prem vLLM ' + base_url if setup is None else 'grader'} model root: {root0}")
    _install_no_audit_write()
    rooms = fetch_rooms(dsn, arms)
    print(f"rooms loaded: {len(rooms)}/{len(arms)}")
    if setup is not None and setup.kind == "code":
        attach_cards(rooms, arms, fetch_card_turns(dsn, arms))
        for room in rooms.values():
            room["trade_action"] = args.trade_action
        print(f"cards rebuilt for {sum(r.get('cards') is not None for r in rooms.values())} Rooms")
    if setup is not None and setup.kind == "deepinfra_room":
        for room in rooms.values():
            room["trade_action"] = args.trade_action
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    phrasings: list[int | None] = list(PHRASINGS) if wording else [None]
    t0 = time.time()
    if setup is None:
        def make_grader(p):
            from app.services.room_graders.hosted_llm import HostedLLMGrader
            return HostedLLMGrader(args.slot, phrasing=p)
        guard = None
    else:
        make_grader, guard = setup.factory, setup.guard
    errors = asyncio.run(run_scoring(
        arms, rooms, out, make_grader=make_grader, phrasings=phrasings,
        concurrency=args.concurrency, model_root=root0, guard=guard))
    root1 = _model_root(args, setup, base_url)
    meta = {
        "started_unix": t0, "elapsed_s": round(time.time() - t0, 1), "rooms": len(arms),
        "errors": errors, "slot": args.slot, "model_root_start": root0, "model_root_end": root1,
        "question_set_version": QUESTION_SET_VERSION,
        "git_sha": os.environ.get("GIT_SHA"), "alpha_tag": os.environ.get("ALPHA_TAG"),
        "concurrency": args.concurrency,
        **_cap_meta(setup),
    }
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta))
    _report_cap(setup)
    if root0 != root1:
        print("WARNING: served model root changed during the run", file=sys.stderr)
    return 0


async def run_inputs(arms: list[dict], rooms: dict, names: dict[str, str], out: Path, *,
                     make_grader, concurrency: int, model_root: str | None,
                     guard: SpendGuard | None = None, log=print) -> int:
    grader = make_grader(None)
    done = {(r["arm_key"], r.get("perturbation")) for r in load_jsonl(out) if not r.get("error")} \
        if out.exists() else set()
    sem = asyncio.Semaphore(max(1, concurrency))
    write_lock = asyncio.Lock()
    errors = 0
    todo = [(a, k) for a in arms for k in PERTURBATIONS if (a["arm_key"], k) not in done]
    log(f"to run: {len(todo)} (skipping {len(arms) * len(PERTURBATIONS) - len(todo)} already done)")

    async def one(i: int, arm: dict, kind: str) -> None:
        nonlocal errors
        room = rooms.get(arm["arm_key"])
        meta: dict = {}
        skipped = None
        if room is None:
            row = result_to_row(arm, "", None, phrasing=None, model_root=model_root,
                                error="no completed room_runs row for this arm user")
        else:
            built = perturb(kind, build_transcript(arm, room), names.get(arm["ticker"]))
            if built is None:
                row = result_to_row(arm, room["id"], None, phrasing=None, model_root=model_root)
                skipped = "nothing to perturb"
            else:
                tr, meta = built
                async with sem:
                    if guard is not None and guard.exceeded():
                        guard.skipped += 1
                        log(f"[{i + 1}/{len(todo)}] {arm['arm_key']} {kind} SKIPPED: spend cap hit ({guard.hit})")
                        return
                    started = time.perf_counter()
                    try:
                        res = await asyncio.wait_for(grader.agrade(tr), ROOM_TIMEOUT_S)
                        if guard is not None:
                            guard.record(res)
                        row = result_to_row(arm, room["id"], res, phrasing=None, model_root=model_root)
                    except Exception as exc:  # noqa: BLE001 — one Room never stops the run
                        row = result_to_row(
                            arm, room["id"], None, phrasing=None, model_root=model_root,
                            error=f"{type(exc).__name__}: {str(exc)[:200]}")
                        row["latency_ms"] = int((time.perf_counter() - started) * 1000)
        row["perturbation"] = kind
        row["pert_meta"] = meta
        if skipped:
            row["skipped"] = skipped
        if row["error"]:
            errors += 1
        async with write_lock:
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
        log(f"[{i + 1}/{len(todo)}] {arm['arm_key']} {kind} {row['latency_ms']}ms "
            f"rule={(row['rule'] or {}).get('outcome')} skipped={skipped} err={row['error']}")

    await asyncio.gather(*(one(i, a, k) for i, (a, k) in enumerate(todo)))
    return errors


def cmd_inputs(args: argparse.Namespace) -> int:
    if getattr(args, "grader", "onprem") == "code":
        print("--grader code has no input tests: it reads cards and the structured trade, never turn "
              "prose, so every perturbation here (all of them edit prose) leaves its answers untouched "
              "by construction", file=sys.stderr)
        return 2
    setup, rc = (None, 0) if args.dry else _grader_preamble(args)
    if rc:
        return rc
    dsn = os.environ.get("WP22_DSN")
    if not dsn:
        print("WP22_DSN is not set", file=sys.stderr)
        return 2
    if setup is None and args.slot != "vllm":
        print("this lane grades on the on-prem vLLM slot only (--slot vllm)", file=sys.stderr)
        return 2
    arms = stride_sample(load_arms(Path(args.runs)), args.sample)
    base_url = os.environ.get("VLLM_BASE_URL", "http://192.168.20.74:8000")
    root0 = _model_root(args, setup, base_url)
    print(f"{'on-prem vLLM ' + base_url if setup is None else 'hosted grader'} model root: {root0}")
    _install_no_audit_write()
    rooms = fetch_rooms(dsn, arms)
    names = fetch_names(dsn, sorted({a["ticker"] for a in arms}))
    print(f"rooms loaded: {len(rooms)}/{len(arms)}; company names: {len(names)}")
    if setup is not None and setup.kind == "deepinfra_room":
        for room in rooms.values():
            room["trade_action"] = args.trade_action
    if args.dry:
        for arm in arms:
            room = rooms.get(arm["arm_key"])
            if room is None:
                print(arm["arm_key"], "NO ROOM")
                continue
            tr = build_transcript(arm, room)
            bear = [t["content"] for t in tr.turns if t["agent_id"] == BEAR_AGENT]
            line = [arm["arm_key"], f"turns={len(tr.turns)}", f"bear_turns={len(bear)}"]
            for k in TESTS:
                built = perturb(k, tr, names.get(arm["ticker"]))
                line.append(f"{k}={'n/a' if built is None else {m: v for m, v in built[1].items() if m != 'order'}}")
            print(" ".join(map(str, line)))
        return 0
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if setup is None:
        def make_grader(p):
            from app.services.room_graders.hosted_llm import HostedLLMGrader
            return HostedLLMGrader(args.slot, phrasing=p)
        guard = None
    else:
        make_grader, guard = setup.factory, setup.guard
    errors = asyncio.run(run_inputs(arms, rooms, names, out, make_grader=make_grader,
                                    concurrency=args.concurrency, model_root=root0, guard=guard))
    root1 = _model_root(args, setup, base_url)
    meta = {
        "started_unix": t0, "elapsed_s": round(time.time() - t0, 1), "rooms": len(arms),
        "perturbations": list(PERTURBATIONS), "errors": errors, "slot": args.slot,
        "model_root_start": root0, "model_root_end": root1,
        "question_set_version": QUESTION_SET_VERSION, "names": names,
        "git_sha": os.environ.get("GIT_SHA"), "alpha_tag": os.environ.get("ALPHA_TAG"),
        "concurrency": args.concurrency,
        **_cap_meta(setup),
    }
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta))
    _report_cap(setup)
    if root0 != root1:
        print("WARNING: served model root changed during the run", file=sys.stderr)
    return 0


# ── Report ──────────────────────────────────────────────────────────────────

def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def pct(n: int, d: int) -> str:
    return "n/a" if d == 0 else f"{100 * n / d:.0f}% ({n}/{d})"


def quantile(vals: list[float], q: float) -> float:
    s = sorted(vals)
    return s[min(len(s) - 1, int(q * len(s)))]


def md_table(header: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def stability(rows: list[dict]) -> tuple[dict, dict]:
    """Disagreement across the two reps of one (ticker, risk). Pairs only where both
    reps were answered; per question, and for the rule's APPROVE/not-APPROVE."""
    cells: dict[tuple, dict[str, dict]] = collections.defaultdict(dict)
    for r in rows:
        cells[(r["ticker"], r["risk"])][r["rep"]] = r
    per_q: dict[str, list[int]] = {q: [0, 0] for q in QIDS}
    rule = [0, 0]
    cio = [0, 0]
    for reps in cells.values():
        if len(reps) != 2:
            continue
        a, b = reps[min(reps)], reps[max(reps)]
        for q in QIDS:
            x, y = a["answers"].get(q), b["answers"].get(q)
            if not x or not y or "not_computable" in (x["answer"], y["answer"]):
                continue
            per_q[q][1] += 1
            per_q[q][0] += x["answer"] != y["answer"]
        rule[1] += 1
        rule[0] += (rule_outcome(a) == "APPROVE") != (rule_outcome(b) == "APPROVE")
        cio[1] += 1
        cio[0] += (a["cio_action"] == "APPROVE") != (b["cio_action"] == "APPROVE")
    return {q: tuple(v) for q, v in per_q.items()}, {"rule": tuple(rule), "cio": tuple(cio)}


def consensus_table(rows: list[dict]) -> list[str]:
    """WP-22 3.1 on the same Rooms: per risk level, approvals by Street bucket for the
    CIO (action APPROVE) and the grader (rule outcome APPROVE, default policy)."""
    def bucket(r: dict) -> str:
        s = r["street_stance"]
        return s if s in ("buy", "hold", "sell") else "unavailable"

    table = []
    for who in ("CIO", "grader"):
        for risk in (*RISKS, "all"):
            sub = [r for r in rows if risk == "all" or r["risk"] == risk]
            appr = [r for r in sub if (r["cio_action"] == "APPROVE" if who == "CIO"
                                       else rule_outcome(r) == "APPROVE")]
            known = [r for r in appr if bucket(r) != "unavailable"]
            c = collections.Counter(bucket(r) for r in known)
            contested = sum(rule_outcome(r) == "CONTESTED" for r in sub) if who == "grader" else None
            table.append([
                who, f"R{risk}" if risk != "all" else "all", len(sub), len(appr),
                c["sell"], pct(c["buy"], len(known)), pct(c["hold"], len(known)),
                len(appr) - len(known),
                "-" if contested is None else contested,
            ])
    return md_table(
        ["decider", "risk", "Rooms (n)", "approvals", "approvals of Street Sell/Underperform",
         "approvals that are Street Buy", "approvals that are Street Hold",
         "approvals, Street n/a", "contested"], table)


def wording_table(base: list[dict], wording: list[dict]) -> list[str]:
    by_base = {r["arm_key"]: r for r in base if not r.get("error")}
    per_q: dict[str, dict[int, list[int]]] = {q: {p: [0, 0] for p in PHRASINGS} for q in QIDS}
    any_change = {q: [0, 0] for q in QIDS}
    rooms: dict[str, dict[int, dict]] = collections.defaultdict(dict)
    for w in wording:
        if not w.get("error") and w.get("phrasing") is not None:
            rooms[w["arm_key"]][w["phrasing"]] = w
    for key, ph in rooms.items():
        b = by_base.get(key)
        if not b:
            continue
        for q in QIDS:
            ref = b["answers"].get(q)
            if not ref or ref["answer"] == "not_computable":
                continue
            changed = False
            seen = False
            for p, w in ph.items():
                a = w["answers"].get(q)
                if not a or a["answer"] == "not_computable":
                    continue
                per_q[q][p][1] += 1
                per_q[q][p][0] += a["answer"] != ref["answer"]
                changed |= a["answer"] != ref["answer"]
                seen = True
            if seen:
                any_change[q][1] += 1
                any_change[q][0] += changed
    rows = []
    for q in QIDS:
        rows.append([q] + [pct(*per_q[q][p]) for p in PHRASINGS] + [pct(*any_change[q])])
    return md_table(["question"] + [f"phrasing {p + 1}" for p in PHRASINGS] + ["any phrasing"], rows)


EXPECT = {
    "original_repeat": ("Control: original regraded", "all six answers unchanged (grader noise floor)"),
    "planted_flaw": ("Planted fatal flaw", "terminal_vulnerability = yes and rule PASS at R1-R5"),
    "bear_removed": ("Bear evidence removed", "rule outcome not more cautious than the original"),
    "bear_strengthened": ("Bear numbers strengthened (x2)",
                          "P(yes) on bear_objection_answered does not rise (+0.01 tolerance) and rule not less cautious"),
    "turns_reordered": ("Turns reordered (seed 22)", "all six answers unchanged"),
    "ticker_renamed": ("Ticker and company renamed", "all six answers unchanged"),
}


def inputs_table(inputs: list[dict]) -> list[str]:
    by: dict[str, dict[str, dict]] = collections.defaultdict(dict)
    for r in inputs:
        by[r["arm_key"]][r["perturbation"]] = r
    verdicts: dict[str, dict[str, tuple[str, str]]] = {k: {} for k in EXPECT}
    for arm_key, g in sorted(by.items()):
        orig = g.get("original")
        for k in EXPECT:
            r = g.get(k)
            if orig is None or r is None:
                continue
            verdicts[k][arm_key] = ("na", "nothing to perturb") if r.get("skipped") else judge(k, orig, r)
    L = ["Each perturbed transcript is graded once on the on-prem grader and judged against its "
         "expectation. `n` counts Rooms where the perturbation applied and both grades parsed.", ""]
    rows = []
    for k, (title, expect) in EXPECT.items():
        v = verdicts[k]
        n = sum(x[0] != "na" for x in v.values())
        npass = sum(x[0] == "pass" for x in v.values())
        fails = [a for a, x in sorted(v.items()) if x[0] == "fail"]
        rows.append([title, expect, n, pct(npass, n), ", ".join(fails) or "none"])
    L += md_table(["test", "expectation", "n", "pass rate", "failing Rooms"], rows)
    L += ["", "Per-Room detail (P = pass, F = fail, - = not applicable):", ""]
    rows = []
    for arm_key in sorted(by):
        cells = []
        for k in EXPECT:
            x = verdicts[k].get(arm_key)
            cells.append("-" if x is None or x[0] == "na" else ("P" if x[0] == "pass" else "F"))
        o = by[arm_key].get("original")
        rows.append([arm_key, outcome_at(o, int(o["risk"])) if o else "?"] + cells)
    L += md_table(["Room", "original rule outcome"] + [EXPECT[k][0] for k in EXPECT], rows)
    L += ["", "Failures, with the measured values:", ""]
    fl = [[EXPECT[k][0], a, x[1]] for k in EXPECT for a, x in sorted(verdicts[k].items()) if x[0] == "fail"]
    L += md_table(["test", "Room", "what happened"], fl) if fl else ["None."]

    ok = [r for r in inputs if not r.get("error") and r["answers"]]
    orig = {r["arm_key"]: r for r in ok if r["perturbation"] == "original"}
    L += ["", "Rule outcome transitions, original -> perturbed (Room's own risk level):", ""]
    rows = []
    for k in ("planted_flaw", "bear_removed", "bear_strengthened", "turns_reordered", "ticker_renamed"):
        c = collections.Counter()
        for r in ok:
            if r["perturbation"] == k and r["arm_key"] in orig:
                c[f"{outcome_at(orig[r['arm_key']], int(r['risk']))} -> {outcome_at(r, int(r['risk']))}"] += 1
        rows.append([EXPECT[k][0], "; ".join(f"{t} x{n}" for t, n in sorted(c.items())) or "-"])
    L += md_table(["perturbation", "transitions"], rows)
    st = [(orig[r["arm_key"]], r) for r in ok if r["perturbation"] == "bear_strengthened" and r["arm_key"] in orig]
    d = [p_yes(b, "bear_objection_answered") - p_yes(a, "bear_objection_answered")
         for a, b in st if p_yes(a, "bear_objection_answered") is not None and p_yes(b, "bear_objection_answered") is not None]
    if d:
        L += ["", f"Bear numbers strengthened: mean change in P(yes) on bear_objection_answered "
              f"{statistics.mean(d):+.3f} (min {min(d):+.3f}, max {max(d):+.3f}, n={len(d)}); "
              f"numbers scaled per Room: " + ", ".join(
                  str(r["pert_meta"].get("numbers_scaled")) for r in ok if r["perturbation"] == "bear_strengthened") + "."]
    rn = [r for r in inputs if r["perturbation"] == "ticker_renamed" and r.get("pert_meta")]
    if rn:
        left = [f"{r['arm_key']} ({r['pert_meta'].get('ticker_left')})" for r in rn if r["pert_meta"].get("ticker_left")]
        noname = [r["arm_key"] for r in rn if not r["pert_meta"].get("names")]
        L += ["", "Ticker rename: Rooms where the ticker string is still present after rename: "
              + (", ".join(left) or "none") + "; Rooms with no company name found: " + (", ".join(noname) or "none") + "."]
    L += ["", "Perturbation builders (all in code): planted flaw = fixed terminal-risk paragraph appended to the last "
          "`bear_researcher` turn; bear removed = every `bear_researcher` turn replaced by one number-free line "
          "(later Bear turns dropped); strengthened = every number attached to %, x or $ (optional K/M/B/T, million, "
          f"billion) inside a sentence containing a downside or leverage keyword multiplied by {STRENGTHEN_FACTOR}, "
          "decimals kept; reordered = non-CIO turns shuffled with `random.Random(22)`; renamed = the ticker and the "
          "`ticker_reference` company name (listing name and name without Inc/Corp/Common Stock suffixes) replaced "
          "by `TICKR` / `Company X` in every turn and in the header.", ""]
    return L


def _why_key(text: str) -> str:
    t = re.sub(r"net_support=-?[\d.]+|action=\S+", "", text or "").strip()
    return re.sub(r"(evidence incomplete:|balance-sheet card missing from:).*", r"\1 ...", t) or "(no reason)"


def completeness_table(ok: list[dict]) -> list[str]:
    """Per question: how many Rooms the grader could answer at all, by risk level, and why not."""
    rows = []
    for q in QIDS:
        cells = []
        for risk in (*RISKS, "all"):
            a = [r["answers"][q]["answer"] for r in ok
                 if (risk == "all" or r["risk"] == risk) and q in r["answers"]]
            cells.append(pct(sum(x != "not_computable" for x in a), len(a)))
        rows.append([q] + cells)
    L = ["Computable share per question (answered yes or no) by risk level:", ""]
    L += md_table(["question"] + [f"R{r}" for r in RISKS] + ["all"], rows)
    deciding = [q for q in QIDS]
    full = sum(all(r["answers"].get(q, {}).get("answer") not in (None, "not_computable") for q in deciding)
               for r in ok)
    L += ["", f"Rooms where all six questions are computable: {pct(full, len(ok))}."]
    never = [q for q in QIDS if not any(r["answers"].get(q, {}).get("answer") not in (None, "not_computable") for r in ok)]
    answerable = [q for q in QIDS if q not in never]
    if never and answerable:
        full2 = sum(all(r["answers"].get(q, {}).get("answer") not in (None, "not_computable") for q in answerable)
                    for r in ok)
        L += [f"Questions this grader never answers in any Room: {', '.join(never)}. Rooms where all the others "
              f"({len(answerable)}) are computable: {pct(full2, len(ok))}."]
    decided = sum(rule_outcome(r) != "UNAVAILABLE" for r in ok)
    L += [f"Rooms where the rule could decide at the Room's own risk level (outcome is not UNAVAILABLE): "
          f"{pct(decided, len(ok))}.", ""]
    why: dict[str, collections.Counter] = {q: collections.Counter() for q in QIDS}
    for r in ok:
        for q in QIDS:
            a = r["answers"].get(q)
            if a and a["answer"] == "not_computable":
                why[q][_why_key(a.get("rationale", ""))] += 1
    rows = [[q, n, reason] for q in QIDS for reason, n in why[q].most_common(4)]
    if rows:
        L += ["Why a cell was not computable (most common reasons per question):", ""]
        L += md_table(["question", "Rooms", "reason"], rows)
    cm = [r["extra"]["cards_meta"] for r in ok if (r.get("extra") or {}).get("cards_meta")]
    if cm:
        L += ["", "Card provenance (rebuilt from `llm_audit`): "
              f"Rooms with cards from all four desks {pct(sum(c['desks_with_cards'] == 4 for c in cm), len(cm))}; "
              f"all four desks with a complete five-item channel {pct(sum(c['desks_complete'] == 4 for c in cm), len(cm))}; "
              f"Rooms where a rejected cards re-ask fell back to the earlier turn "
              f"{sum(bool(c['fallback_desks']) for c in cm)}; "
              f"malformed card lines in total {sum(c['malformed_cards'] for c in cm)}."]
    return L


def build_report(scores: list[dict], wording: list[dict] | None, meta: dict | None,
                 inputs: list[dict] | None = None) -> str:
    ok = [r for r in scores if not r.get("error") and r["answers"]]
    errs = [r for r in scores if r.get("error") or not r["answers"]]
    L: list[str] = [f"# WP-22 step 3 — grader scoring ({(meta or {}).get('grader_label') or 'hosted model, on-prem'})", ""]
    if meta:
        L += [f"Model root: `{meta.get('model_root_start')}` (end `{meta.get('model_root_end')}`); "
              f"question set `{meta.get('question_set_version')}`; image `{meta.get('alpha_tag')}` "
              f"`{str(meta.get('git_sha'))[:8]}`; concurrency {meta.get('concurrency')}.", ""]
    L += [f"Rooms scored: **{len(ok)}**, errors: **{len(errs)}** (errors are excluded from every "
          "table below and listed at the end). CIO numbers are on the same Rooms.", ""]

    lat = [r["latency_ms"] / 1000 for r in ok if r.get("latency_ms")]
    lp = [r for r in ok if r["extra"].get("logprobs") is not None]
    costs = [r["cost_usd"] for r in ok if r.get("cost_usd") is not None]
    L += ["## Cost, latency, control", ""]
    L += md_table(["measure", "value"], [
        ["latency per Room, mean / median / p95 / max (s)",
         "n/a" if not lat else f"{statistics.mean(lat):.1f} / {statistics.median(lat):.1f} / "
                               f"{quantile(lat, .95):.1f} / {max(lat):.1f}"],
        ["Rooms where token probabilities came back for every question",
         pct(sum(bool(r["extra"].get("logprobs")) for r in lp), len(lp))],
        ["cost per Room (USD, priced from LLM_PRICES_JSON)",
         "not reported" if not costs else f"{statistics.mean(costs):.5f} (n={len(costs)})"],
        ["calls per Room (mean)", "n/a" if not ok else f"{statistics.mean(r['extra'].get('calls', 0) for r in ok):.1f}"],
        ["unparsed yes/no replies (total)", sum(r["extra"].get("unparsed_questions", 0) for r in ok)],
    ])
    L += ["", "## Answer distribution per question", ""]
    rows = []
    for q in QIDS:
        a = [r["answers"][q] for r in ok if q in r["answers"]]
        c = collections.Counter(x["answer"] for x in a)
        conf = [x["confidence"] for x in a if x.get("confidence") is not None]
        rows.append([q, len(a), pct(c["yes"], len(a)), pct(c["no"], len(a)),
                     pct(c["not_computable"], len(a)), pct(sum(x["close"] for x in a), len(a)),
                     "n/a" if not conf else f"{statistics.mean(conf):.2f}"])
    L += md_table(["question", "n", "yes", "no", "not computable", "close", "mean confidence"], rows)
    L += ["", "Yes share by risk level:", ""]
    rows = []
    for q in QIDS:
        cells = []
        for risk in RISKS:
            a = [r["answers"][q]["answer"] for r in ok if r["risk"] == risk and q in r["answers"]]
            cells.append(pct(sum(x == "yes" for x in a), len(a)))
        rows.append([q] + cells)
    L += md_table(["question"] + [f"R{r}" for r in RISKS], rows)

    nc_rows = [r for r in ok if any(a["answer"] == "not_computable" for a in r["answers"].values())]
    if nc_rows:
        L += ["", "## Completeness (computable share; a missing cell is never imputed)", ""]
        L += completeness_table(ok)
    L += ["", "## Decision-rule outcomes (default policy, rule r1)", ""]
    rows = []
    for risk in (*RISKS, "all"):
        sub = [r for r in ok if risk == "all" or r["risk"] == risk]
        c = collections.Counter(rule_outcome(r) for r in sub)
        cio = collections.Counter(r["cio_action"] for r in sub)
        rows.append([f"R{risk}" if risk != "all" else "all", len(sub), c["APPROVE"], c["PASS"],
                     c["CONTESTED"], c["UNAVAILABLE"], cio["APPROVE"], len(sub) - cio["APPROVE"]])
    L += md_table(["risk", "n", "grader APPROVE", "PASS", "CONTESTED", "UNAVAILABLE",
                   "CIO APPROVE", "CIO not-APPROVE"], rows)
    x = collections.Counter(
        (r["cio_action"] == "APPROVE", rule_outcome(r)) for r in ok)
    L += ["", "Grader outcome against the CIO's action, same Rooms:", ""]
    L += md_table(["", "grader APPROVE", "grader PASS", "grader CONTESTED", "grader UNAVAILABLE"], [
        ["CIO APPROVE"] + [x[(True, o)] for o in ("APPROVE", "PASS", "CONTESTED", "UNAVAILABLE")],
        ["CIO not APPROVE"] + [x[(False, o)] for o in ("APPROVE", "PASS", "CONTESTED", "UNAVAILABLE")],
    ])

    L += ["", "## Consensus scores (WP-22 3.1)", "",
          "Street bucket is `street_comparison.street_stance` stored on each Room's verdict "
          "(buy = Buy and Strong Buy, sell = Sell/Underperform). The grader approves when "
          "`decide()` with the default policy returns APPROVE. Rooms with no Street data "
          "cannot enter the Street columns.", ""]
    L += consensus_table(ok)

    pq, pr = stability(ok)
    L += ["", "## Fresh-room stability (two reps of the same ticker and risk level)", "",
          "Pairs where both reps were answered; `not_computable` pairs are dropped. "
          "CIO and rule rows compare APPROVE against anything else.", ""]
    rows = [[q, pct(*pq[q])] for q in QIDS]
    rows.append(["rule outcome APPROVE vs not (grader)", pct(*pr["rule"])])
    rows.append(["CIO action APPROVE vs not (same Rooms)", pct(*pr["cio"])])
    L += md_table(["measure", "reps disagree"], rows)

    if wording:
        L += ["", "## Wording test (five phrasings, share of answers that change vs phrasing 0)", ""]
        sample = {w["arm_key"] for w in wording if not w.get("error")}
        L += [f"Sample: {len(sample)} Rooms. Each cell: answers that differ from the base wording.", ""]
        L += wording_table(ok, wording)
        werr = [w for w in wording if w.get("error")]
        if werr:
            L += ["", f"Wording calls with errors (excluded): {len(werr)}"]

    if inputs:
        L += ["", "## Input tests with known answers (WP-22 3.3)", ""]
        L += inputs_table(inputs)

    if errs:
        L += ["", "## Errors", ""]
        L += md_table(["arm", "error"], [[r["arm_key"], str(r.get("error"))[:160]] for r in errs[:40]])
        if len(errs) > 40:
            L += ["", f"... and {len(errs) - 40} more."]
    L += ["", "Not computed here: rank correlation of a decision score with the consensus score "
          "(the grader emits yes/no answers, not a score).", ""]
    return "\n".join(L) + "\n"


def cmd_report(args: argparse.Namespace) -> int:
    arms = {a["arm_key"]: a for a in load_arms(Path(args.runs))}
    scores = load_jsonl(Path(args.scores))
    for r in scores:
        a = arms.get(r["arm_key"])
        if a is not None:
            r["cio_action"] = (a.get("verdict") or {}).get("action")
            r["street_rating"], r["street_stance"] = street_fields(a)
    wording = load_jsonl(Path(args.wording)) if args.wording else None
    meta_path = Path(args.scores).with_suffix(".meta.json")
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else None
    inputs = load_jsonl(Path(args.inputs)) if args.inputs else None
    md = build_report(scores, wording, meta, inputs)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
    else:
        print(md)
    return 0


# ── Fit: close_below_confidence (WP-23 step 4) ──────────────────────────────
# Offline, no DB, no network: reads the per-Room answers a `score` run already stored (and, if given,
# the `inputs` run) and re-applies the rule under each candidate cut-off. Consensus (Street rating)
# is NEVER read here: it is held out for evaluation. The CR257 holdouts are the third target in the
# plan; they are not in these files, so the chosen value is checked against them by hand before it
# goes in ROOM_CODED_RULE_POLICY_JSON.
FIT_GRID = (0.0,) + tuple(round(0.55 + 0.05 * i, 2) for i in range(9))
FIT_MAX_CONTESTED = 0.20
FIT_TESTS = ("planted_flaw", "bear_removed", "bear_strengthened")


def policy_with_cut(cut: float):
    return dataclasses.replace(DEFAULT_POLICY, close_below_confidence=cut, source="fit")


def fit_metrics(rows: list[dict], inputs: list[dict] | None, cut: float) -> dict:
    """What one candidate cut-off does: Contested share, approvals, rep disagreement on
    APPROVE-vs-not (target a), and, with inputs, the known-answer pass rate (target b)."""
    policy = policy_with_cut(cut)
    ok = [r for r in rows if not r.get("error") and r.get("answers")]
    out = {r["arm_key"]: outcome_at(r, int(r["risk"]), policy) for r in ok}
    cells: dict[tuple, dict[str, dict]] = collections.defaultdict(dict)
    for r in ok:
        cells[(r["ticker"], r["risk"])][r["rep"]] = r
    pairs = disagree = 0
    for reps in cells.values():
        if len(reps) != 2:
            continue
        a, b = reps[min(reps)], reps[max(reps)]
        pairs += 1
        disagree += (out[a["arm_key"]] == "APPROVE") != (out[b["arm_key"]] == "APPROVE")
    contested = sum(v == "CONTESTED" for v in out.values())
    m = {
        "cut": cut, "rooms": len(ok), "pairs": pairs, "rep_disagree": disagree,
        "rep_disagree_rate": (disagree / pairs) if pairs else None,
        "approve": sum(v == "APPROVE" for v in out.values()),
        "contested": contested,
        "contested_share": (contested / len(ok)) if ok else None,
        "unavailable": sum(v == "UNAVAILABLE" for v in out.values()),
    }
    if inputs:
        by: dict[str, dict[str, dict]] = collections.defaultdict(dict)
        for r in inputs:
            by[r["arm_key"]][r["perturbation"]] = r
        n = npass = 0
        for g in by.values():
            orig = g.get("original")
            for k in FIT_TESTS:
                r = g.get(k)
                if orig is None or r is None or r.get("skipped"):
                    continue
                verdict = judge(k, orig, r, policy)[0]
                n += verdict != "na"
                npass += verdict == "pass"
        m["input_tests"], m["input_pass"] = n, npass
    return m


def choose_cut(table: list[dict], max_contested: float) -> dict:
    """Pre-registered choice: among cut-offs whose Contested share is within the cap, the one
    with the lowest rep disagreement; ties go to the higher input-test pass rate, then the lower
    cut-off. None within the cap falls back to 0.0 (the grader's own `close` flag only)."""
    inside = [m for m in table if m["contested_share"] is not None and m["contested_share"] <= max_contested
              and m["rep_disagree_rate"] is not None]
    if not inside:
        return {**next(m for m in table if m["cut"] == 0.0), "cap_unmet": True}
    best = min(inside, key=lambda m: (m["rep_disagree_rate"], -(m.get("input_pass") or 0), m["cut"]))
    return {**best, "cap_unmet": False}


def cmd_fit(args: argparse.Namespace) -> int:
    rows = load_jsonl(Path(args.scores))
    inputs = load_jsonl(Path(args.inputs)) if args.inputs else None
    table = [fit_metrics(rows, inputs, c) for c in FIT_GRID]
    chosen = choose_cut(table, args.max_contested)
    levels = {lvl: {"required_yes": sorted(q.value for q in lp.required_yes),
                    "blocking_yes": sorted(q.value for q in lp.blocking_yes)}
              for lvl, lp in DEFAULT_POLICY.levels.items()}
    grader = next((r.get("grader") for r in rows if r.get("grader")), "deepinfra")
    policy_json = {grader: {"close_below_confidence": chosen["cut"], **levels}}
    report = {"max_contested": args.max_contested, "grid": table, "chosen": chosen,
              "policy_json": policy_json,
              "note": "fitted on rep agreement and the input tests only; never on consensus. Check the "
                      "CR257 holdouts by hand before setting ROOM_CODED_RULE_POLICY_JSON."}
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"{'cut':>5} {'rooms':>5} {'pairs':>5} {'rep_dis':>8} {'approve':>7} {'contested':>9} {'unavail':>7}"
          + ("  inputs" if inputs else ""))
    for m in table:
        rate = "n/a" if m["rep_disagree_rate"] is None else f"{100 * m['rep_disagree_rate']:.0f}%"
        share = "n/a" if m["contested_share"] is None else f"{100 * m['contested_share']:.0f}%"
        print(f"{m['cut']:>5} {m['rooms']:>5} {m['pairs']:>5} {rate:>8} {m['approve']:>7} {share:>9} "
              f"{m['unavailable']:>7}" + (f"  {m['input_pass']}/{m['input_tests']}" if inputs else ""))
    print(f"chosen close_below_confidence={chosen['cut']}"
          + ("  (NO cut-off met the Contested cap; kept the placeholder)" if chosen["cap_unmet"] else ""))
    print("ROOM_CODED_RULE_POLICY_JSON=" + json.dumps(policy_json, separators=(",", ":")))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    def grader_args(p) -> None:
        p.add_argument("--grader", choices=GRADERS, default="onprem",
                       help="onprem = vLLM slot (default); jev / deepinfra = paid, keys from bakeoff.env")
        p.add_argument("--jev-version", default=JEV_DEFAULT_VERSION,
                       help="pinned Jev model id; 'latest' is refused")
        p.add_argument("--model", default=DEEPINFRA_DEFAULT_MODEL, help="pinned DeepInfra model id")
        p.add_argument("--price-in", type=float, help="USD per 1M input tokens, for a model not in the table")
        p.add_argument("--price-out", type=float, help="USD per 1M output tokens, for a model not in the table")
        p.add_argument("--max-usd", type=float, default=DEFAULT_MAX_USD,
                       help="stop cleanly once priced spend reaches this (jev / deepinfra)")
        p.add_argument("--max-calls", type=int, default=DEFAULT_MAX_CALLS,
                       help="stop cleanly after this many UNPRICED calls (jev / deepinfra)")
        p.add_argument("--trade-action", default=None,
                       help="code grader only: add this `action` to the proposed trade (sensitivity run; "
                            "the production trade block has no action, so trade_proposed is not computable)")

    for name in ("score", "wording"):
        p = sub.add_parser(name)
        p.add_argument("--runs", required=True)
        p.add_argument("--out", required=True)
        p.add_argument("--slot", default="vllm", help="gateway provider slot (on-prem vLLM only)")
        p.add_argument("--concurrency", type=int, default=1)
        grader_args(p)
        if name == "score":
            p.add_argument("--pilot", type=int, default=0, help="N Rooms spread over all risk levels")
            p.add_argument("--limit", type=int, default=0)
        else:
            p.add_argument("--sample", type=int, default=20)
    p = sub.add_parser("inputs")
    p.add_argument("--runs", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--slot", default="vllm", help="gateway provider slot (on-prem vLLM only)")
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--sample", type=int, default=20)
    p.add_argument("--dry", action="store_true", help="build the perturbations and print stats; no grading")
    grader_args(p)
    p = sub.add_parser("report")
    p.add_argument("--runs", required=True)
    p.add_argument("--scores", required=True)
    p.add_argument("--wording")
    p.add_argument("--inputs")
    p.add_argument("--out")
    p = sub.add_parser("fit", help="fit close_below_confidence offline from a finished `score` run")
    p.add_argument("--scores", required=True)
    p.add_argument("--inputs")
    p.add_argument("--max-contested", type=float, default=FIT_MAX_CONTESTED,
                   help="largest Contested share a candidate cut-off may produce")
    p.add_argument("--out")
    args = ap.parse_args(argv)
    if args.cmd == "report":
        return cmd_report(args)
    if args.cmd == "fit":
        return cmd_fit(args)
    if args.cmd == "inputs":
        return cmd_inputs(args)
    return cmd_run(args, wording=args.cmd == "wording")


if __name__ == "__main__":
    sys.exit(main())
