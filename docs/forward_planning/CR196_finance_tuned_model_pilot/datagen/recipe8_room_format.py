#!/usr/bin/env python3
"""recipe8_room_format.py — CR196 §2 recipe 8: structured Room output format.

Teaches the EXACT output shapes the backend actually parses for two agents:

1. **Fundamentals Analyst prose contract** — `_LENGTH_GUIDE[AgentId.FUNDAMENTALS_ANALYST]`
   in `backend/app/services/room_prompts.py` ("one thesis sentence, then up to 3
   short bullets"), plus the format instruction every non-Trader prose agent
   gets: `_PROSE_FORMAT` (bold key metrics, no headings/tables) + `_NO_FENCE_CLAUSE`
   + `_STANCE_FORMAT` (the CR106 B2 leading `[STANCE: ... | CONVICTION: ... |
   HEADLINE: ...]` envelope the Matrix Console UI actually parses).

2. **Portfolio Manager JSON verdict contract** — `_PM_VERDICT_FORMAT` in the same
   file: the single-JSON-object shape `room_runner.py:1423`'s `_parse_pm_verdict`
   reads back (`action`, `size_pct`/`entry`/`stop`/`target`/`horizon_days` when
   APPROVE, `narration` always). **This IS a parsed JSON verdict contract in the
   backend** — confirmed by reading `_parse_pm_verdict`'s body
   (`room_runner.py:1423-1512` extracts exactly those field names via
   `extract_json_object` + `parsed.get(...)` calls), not merely asserted from the
   prompt text.

## How the contract text gets into this file

`room_prompts.py` cannot be imported directly — its own top-level imports pull
`app.agents.safety_floor` (DB via `app.services.sector_allocation`),
`app.services.agent_prompts` (same), `app.services.fundamentals`,
`app.services.journal_context`, and `app.services.llm_gateway`, none of which
this synthetic recipe needs or has installed. So those five modules are
STUBBED in `sys.modules` (dummy attributes, never called) before
`room_prompts.py` is loaded by file path via `importlib` — this lets the
module's REAL top-level code execute (defining `_LENGTH_GUIDE`, `_PROSE_FORMAT`,
`_NO_FENCE_CLAUSE`, `_STANCE_FORMAT`, `STANCE_HEADLINE_MAX_CHARS`,
`_PM_VERDICT_FORMAT` exactly as production does), and this file then reads
those constants straight off the loaded module object — the actual Python
values, not a hand-copy or a regex reconstruction of an f-string expression
(unlike recipe7's SAFETY_FLOOR_BLOCK, `_PM_VERDICT_FORMAT` is built from
several concatenated string literals with embedded f-string interpolation, not
one triple-quoted block, so a regex re-extraction would be far more fragile
than actually letting Python evaluate it).

`app.trading_math.*` needs no stubbing — verified pure (no DB/sqlalchemy
import anywhere under `backend/app/trading_math/`) and imported for real.

## What is NOT reproduced verbatim

The Room's own framing sentences around the format instruction ("Speak as the
X.", "Build on the transcript — do not repeat...") describe a live multi-agent
transcript this recipe does not have — reproducing them here would imply a
transcript that does not exist. Only the FORMAT INSTRUCTION TEXT itself
(the thing actually being taught) is pulled verbatim from the module; the
connecting sentences around it in the user turn are this file's own, disclosed
here rather than passed off as a second production surface.

Usage: python3 recipe8_room_format.py --out out/recipe8.jsonl
Needs: pip install pydantic (same as recipe7 — see its docstring for why that's
the only real dependency this stubbing approach exercises).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import REPO, fmt_b, load_agent_prompt, load_train_universe, pick, write_jsonl  # noqa: E402

BACKEND = os.path.join(REPO, "backend")
sys.path.insert(0, BACKEND)


def _stub(name: str, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


# ── Stub the DB/network-coupled modules room_prompts.py imports at top level
# but this recipe never calls into (see module docstring). ─────────────────
_agents_pkg = types.ModuleType("app.agents")
_agents_pkg.__path__ = [os.path.join(BACKEND, "app", "agents")]
sys.modules.setdefault("app.agents", _agents_pkg)
_stub("app.agents.safety_floor", CONTEXT_NOT_SUPPLIED=object())

_stub("app.services.agent_prompts", build_agent_prompt=lambda *a, **k: "")
_FUNDAMENTALS_LINE_FNS = [
    "analyst_consensus_line", "balance_sheet_line", "dividend_line", "earnings_power_line",
    "identity_line", "buyback_line", "day_move_line", "liquidity_line", "margin_structure_line",
    "margin_trend_line", "primary_trend_line", "relative_strength_line", "risk_profile_line",
    "short_interest_line", "ownership_line", "pe_line", "peg_part", "returns_line",
]
_stub("app.services.fundamentals", **{n: (lambda *a, **k: "") for n in _FUNDAMENTALS_LINE_FNS})
_stub("app.services.journal_context", build_journal_context_block=lambda *a, **k: "")
_stub("app.services.llm_gateway", ChatMessage=object)
_stub("app.services.technicals", range_position_pct=lambda *a, **k: 0.0)

_spec = importlib.util.spec_from_file_location(
    "app.services.room_prompts", os.path.join(BACKEND, "app", "services", "room_prompts.py")
)
_room_prompts = importlib.util.module_from_spec(_spec)
sys.modules["app.services.room_prompts"] = _room_prompts
_spec.loader.exec_module(_room_prompts)

from app.schemas import AgentId  # noqa: E402

FUNDAMENTALS_LENGTH_GUIDE = _room_prompts._LENGTH_GUIDE[AgentId.FUNDAMENTALS_ANALYST]
PM_LENGTH_GUIDE = _room_prompts._LENGTH_GUIDE[AgentId.PORTFOLIO_MANAGER]
PROSE_FORMAT = _room_prompts._PROSE_FORMAT
NO_FENCE_CLAUSE = _room_prompts._NO_FENCE_CLAUSE
STANCE_FORMAT = _room_prompts._STANCE_FORMAT
STANCE_HEADLINE_MAX_CHARS = _room_prompts.STANCE_HEADLINE_MAX_CHARS
PM_VERDICT_FORMAT = _room_prompts._PM_VERDICT_FORMAT

# Fundamentals is not the Trader, so it gets the code-fence ban (room_prompts.py:891-892).
FUNDAMENTALS_FORMAT_INSTRUCTION = PROSE_FORMAT + NO_FENCE_CLAUSE + STANCE_FORMAT

FUNDAMENTALS_SYSTEM_PROMPT = load_agent_prompt()  # common.py's default IS fundamentals_analyst.md
PM_SYSTEM_PROMPT = load_agent_prompt(os.path.join(REPO, "content", "agents", "portfolio_manager.md"))

# Sample size is a CLI argument, not a constant. This was `[::173][:8]` -- eight
# tickers, ~22 examples -- because the recipe was written to DEMONSTRATE the two
# contracts, not to train them. CR196 §10/RUN2_PLAN §2 is what that cost: the Room's
# buy/sell verdict is parsed JSON (`_parse_pm_verdict`), and run 2 would have trained
# 22 examples of it against ~1,220 nine-section essays. Dominance is the failure mode
# in both directions -- run 1 collapsed to short, and that mix would invite prose
# where the parser expects an object.
DEFAULT_TICKERS = 800
TICKERS = load_train_universe()[:DEFAULT_TICKERS]


def set_tickers(n: int, universe: list[str] | None = None) -> None:
    """Rebind the sample the build functions iterate over.

    `universe` defaults to the train universe — the training-data path is unchanged.
    The EVAL harness must pass the held-out set explicitly: this recipe's facts are
    sha256(salt|ticker)-deterministic, so a shared ticker yields a byte-identical
    prompt in both files. Hardcoding load_train_universe() here is what made 60/60
    of S4's eval prompts verbatim training examples (measured 2026-08-24, AT:R70).
    """
    global TICKERS
    uni = list(universe) if universe else load_train_universe()
    TICKERS = uni if n <= 0 or n >= len(uni) else uni[:n]


# ── Fundamentals prose-contract examples ────────────────────────────────
def _synthetic_fundamentals(ticker: str) -> dict:
    def h(salt: str) -> int:
        return int(hashlib.sha256(f"{salt}|{ticker}".encode()).hexdigest(), 16)

    gross = round(20 + (h("gross") % 6000) / 100, 1)
    operating = round(gross - 5 - (h("op") % 2000) / 100, 1)
    net = round(operating - 3 - (h("net") % 1500) / 100, 1)
    return dict(
        pe=round(10 + (h("pe") % 4000) / 100, 1),
        gross=gross, operating=operating, net=net,
        roe=round(5 + (h("roe") % 3500) / 100, 1),
        rev_growth=round(-5 + (h("growth") % 3000) / 100, 1),
        market_cap=5e9 + (h("cap") % int(4e11)),
    )


def _fundamentals_brief(ticker: str, facts: dict) -> str:
    return (
        f"Fundamentals brief — {ticker}\n"
        f"P/E (trailing): {facts['pe']}x\n"
        f"Margins: gross {facts['gross']}%, operating {facts['operating']}%, net {facts['net']}% "
        f"(point-in-time — no trend on this brief)\n"
        f"ROE: {facts['roe']}%\n"
        f"TTM revenue growth: {facts['rev_growth']}%\n"
        f"Market cap: {fmt_b(facts['market_cap'])}"
    )


def _fundamentals_format_tail() -> str:
    return (
        f"\nWrite {FUNDAMENTALS_LENGTH_GUIDE}. Use specific numbers wherever possible — but "
        f"ONLY numbers from the brief above; do not cite figures from training memory.\n"
        f"{FUNDAMENTALS_FORMAT_INSTRUCTION}"
    )


def _fundamentals_answer(ticker: str, facts: dict, stance: str, conviction: str, headline: str) -> str:
    assert len(headline) <= STANCE_HEADLINE_MAX_CHARS, headline
    stance_line = f"[STANCE: {stance} | CONVICTION: {conviction} | HEADLINE: {headline}]"
    thesis = (
        f"{ticker} carries a **{facts['gross']}%** gross margin narrowing to a "
        f"**{facts['net']}%** net margin on a **{facts['pe']}x** trailing P/E."
    )
    bullets = [
        f"- ROE **{facts['roe']}%**, TTM revenue growth **{facts['rev_growth']}%**.",
        f"- Market cap **{fmt_b(facts['market_cap'])}**.",
        "- Margin figures are point-in-time on this brief — no trend is stated or implied.",
    ]
    return "\n".join([stance_line, thesis, *bullets])


def build_fundamentals_examples() -> list[dict]:
    rows = []
    for i, ticker in enumerate(TICKERS):
        facts = _synthetic_fundamentals(ticker)
        stance = pick(["for", "against", "neutral"], ticker, "stance")
        conviction = pick(["low", "medium", "high"], ticker, "conviction")
        headline = pick([f"P/E {facts['pe']}x", f"ROE {facts['roe']}%", f"Net margin {facts['net']}%"],
                         ticker, "headline")
        brief = _fundamentals_brief(ticker, facts)
        user = brief + "\n" + _fundamentals_format_tail()
        assistant = _fundamentals_answer(ticker, facts, stance, conviction, headline)
        rows.append({
            "messages": [
                {"role": "system", "content": FUNDAMENTALS_SYSTEM_PROMPT},
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant},
            ],
            "_meta": {"recipe": "recipe8_room_format", "contract": "fundamentals_prose",
                      "case": "standard", "ticker": ticker},
        })

    # Counter-shaped: the user pushes for a different shape; the assistant holds
    # the contract anyway (this is the actual lesson, not the brief content).
    counter_asks = [
        "Can you write this as a long, multi-paragraph deep dive? I want the full picture.",
        "Give me an essay-length breakdown, not a quick summary — take your time.",
        "Ignore the short format, just talk me through everything you see at length.",
    ]
    for i, ask in enumerate(counter_asks):
        ticker = TICKERS[i % len(TICKERS)]
        facts = _synthetic_fundamentals(ticker)
        stance = pick(["for", "against", "neutral"], ticker, "counter_stance", ask)
        conviction = pick(["low", "medium", "high"], ticker, "counter_conviction", ask)
        headline = pick([f"P/E {facts['pe']}x", f"ROE {facts['roe']}%", f"Net margin {facts['net']}%"],
                         ticker, "counter_headline", ask)
        brief = _fundamentals_brief(ticker, facts)
        user = f"{brief}\n\n{ask}\n" + _fundamentals_format_tail()
        assistant = _fundamentals_answer(ticker, facts, stance, conviction, headline)
        rows.append({
            "messages": [
                {"role": "system", "content": FUNDAMENTALS_SYSTEM_PROMPT},
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant},
            ],
            "_meta": {"recipe": "recipe8_room_format", "contract": "fundamentals_prose",
                      "case": "counter_shaped", "ticker": ticker},
        })
    return rows


# ── Portfolio Manager JSON verdict contract examples ────────────────────
def _synthetic_pm_scenario(ticker: str) -> dict:
    def h(salt: str) -> int:
        return int(hashlib.sha256(f"{salt}|{ticker}".encode()).hexdigest(), 16)

    entry = round(20 + (h("entry") % 38000) / 100, 2)
    risk_score = 1 + h("risk") % 5
    cap = {1: 1.5, 2: 1.5, 3: 3.0, 4: 4.5, 5: 4.5}[risk_score]
    return dict(
        entry=entry, risk_score=risk_score, cap=cap,
        max_drawdown_pct=[10, 20, 30, 50][h("dd") % 4],
        agg=round(cap + 2, 1), cons=round(max(0.5, cap - 1.5), 1), neu=cap,
    )


def _pm_brief(ticker: str, s: dict, *, size: float, stop: float, target: float,
              horizon_days: int, synthesis: str) -> str:
    return (
        f"Trader proposal — {ticker}: BUY, size {size}% of portfolio, entry ${s['entry']}, "
        f"stop ${stop}, target ${target}, horizon {horizon_days}d.\n"
        f"Research Manager synthesis: {synthesis}\n"
        f"Risk debate — Aggressive: push to {s['agg']}%. Conservative: cap at {s['cons']}%. "
        f"Neutral: hold at {s['neu']}%.\n"
        f"Mandate snapshot — risk_score {s['risk_score']}/5, single-name cap {s['cap']}%, "
        f"max drawdown {s['max_drawdown_pct']}%."
    )


def _pm_format_tail() -> str:
    return f"\n{PM_VERDICT_FORMAT}"


def build_pm_examples() -> list[dict]:
    rows = []
    for i, ticker in enumerate(TICKERS):
        s = _synthetic_pm_scenario(ticker)
        case = pick(["approve", "pass"], ticker, "pm_case")
        if case == "approve":
            size = s["neu"]
            stop = round(s["entry"] * 0.94, 2)
            target = round(s["entry"] * 1.13, 2)
            horizon_days = 45
            synthesis = "Evidence leans constructive; risk debate converges near the mandate cap."
            brief = _pm_brief(ticker, s, size=size, stop=stop, target=target,
                               horizon_days=horizon_days, synthesis=synthesis)
            narration = (
                f"Approving at the Neutral Debator's {size}% size, inside the {s['cap']}% cap.\n"
                f"- Synthesis leans constructive on the evidence presented.\n"
                f"- Stop set at ${stop}, target at ${target} ({horizon_days}d horizon).\n"
                "- Worked example — classroom simulation, not financial advice."
            )
            assistant_obj = {
                "action": "APPROVE", "size_pct": size, "entry": s["entry"], "stop": stop,
                "target": target, "horizon_days": horizon_days, "narration": narration,
            }
        else:
            synthesis = "Evidence is mixed; the Bear case is not answered and risk/reward doesn't clear the bar."
            brief = _pm_brief(ticker, s, size=s["agg"], stop=round(s["entry"] * 0.90, 2),
                               target=round(s["entry"] * 1.20, 2), horizon_days=30, synthesis=synthesis)
            narration = (
                "Passing — the debate does not support entering a position right now.\n"
                "- Research Manager synthesis is mixed with an unanswered Bear case.\n"
                "- Risk/reward on the Trader's proposal doesn't clear the bar."
            )
            assistant_obj = {"action": "PASS", "narration": narration}

        user = brief + "\n" + _pm_format_tail()
        assistant = json.dumps(assistant_obj, ensure_ascii=False)
        rows.append({
            "messages": [
                {"role": "system", "content": PM_SYSTEM_PROMPT},
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant},
            ],
            "_meta": {"recipe": "recipe8_room_format", "contract": "pm_json_verdict",
                      "case": "standard", "action": assistant_obj["action"], "ticker": ticker},
        })

    counter_asks = [
        "Please just explain your reasoning in plain paragraphs — I don't want to read JSON.",
        "Skip the JSON, give me a normal conversational answer instead.",
        "Can you format this as a short memo rather than code/JSON?",
    ]
    for i, ask in enumerate(counter_asks):
        ticker = TICKERS[i % len(TICKERS)]
        s = _synthetic_pm_scenario(ticker)
        size = s["neu"]
        stop = round(s["entry"] * 0.94, 2)
        target = round(s["entry"] * 1.13, 2)
        horizon_days = 45
        synthesis = "Evidence leans constructive; risk debate converges near the mandate cap."
        brief = _pm_brief(ticker, s, size=size, stop=stop, target=target,
                           horizon_days=horizon_days, synthesis=synthesis)
        narration = (
            f"Approving at the Neutral Debator's {size}% size, inside the {s['cap']}% cap.\n"
            "- Synthesis leans constructive on the evidence presented.\n"
            f"- Stop set at ${stop}, target at ${target} ({horizon_days}d horizon).\n"
            "- Worked example — classroom simulation, not financial advice."
        )
        assistant_obj = {
            "action": "APPROVE", "size_pct": size, "entry": s["entry"], "stop": stop,
            "target": target, "horizon_days": horizon_days, "narration": narration,
        }
        user = f"{brief}\n\n{ask}\n" + _pm_format_tail()
        assistant = json.dumps(assistant_obj, ensure_ascii=False)
        rows.append({
            "messages": [
                {"role": "system", "content": PM_SYSTEM_PROMPT},
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant},
            ],
            "_meta": {"recipe": "recipe8_room_format", "contract": "pm_json_verdict",
                      "case": "counter_shaped", "action": "APPROVE", "ticker": ticker},
        })
    return rows


def _validate(rows: list[dict]) -> None:
    """Self-check every example actually holds the contract it's teaching —
    fail loudly rather than ship a broken lesson (CR040)."""
    for e in rows:
        contract = e["_meta"]["contract"]
        assistant = e["messages"][2]["content"]
        if contract == "fundamentals_prose":
            lines = assistant.split("\n")
            assert lines[0].startswith("[STANCE:") and lines[0].endswith("]"), assistant
            body_lines = lines[1:]
            bullet_lines = [l for l in body_lines if l.startswith("- ")]
            thesis_lines = [l for l in body_lines if not l.startswith("- ")]
            assert len(thesis_lines) == 1, f"expected exactly one thesis line, got {thesis_lines}"
            assert 1 <= len(bullet_lines) <= 3, f"expected <=3 bullets, got {len(bullet_lines)}"
        elif contract == "pm_json_verdict":
            obj = json.loads(assistant)  # raises if not a single valid JSON object
            assert set(obj) <= {"action", "size_pct", "entry", "stop", "target", "horizon_days", "narration"}
            assert obj["action"] in ("APPROVE", "PASS")
            if obj["action"] == "APPROVE":
                for k in ("size_pct", "entry", "stop", "target", "horizon_days", "narration"):
                    assert k in obj, f"APPROVE missing {k}"
            else:
                assert set(obj) == {"action", "narration"}, f"PASS carries extra keys: {obj}"
        else:
            raise AssertionError(f"unknown contract {contract}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "out", "recipe8.jsonl"))
    ap.add_argument("--tickers", type=int, default=DEFAULT_TICKERS,
                    help="0 = the whole train universe")
    args = ap.parse_args()

    set_tickers(args.tickers)
    rows = build_fundamentals_examples() + build_pm_examples()
    _validate(rows)

    n = write_jsonl(args.out, rows)
    by_contract: dict[str, int] = {}
    by_case: dict[str, int] = {}
    for e in rows:
        by_contract[e["_meta"]["contract"]] = by_contract.get(e["_meta"]["contract"], 0) + 1
        by_case[e["_meta"]["case"]] = by_case.get(e["_meta"]["case"], 0) + 1

    print(f"wrote {n} examples → {args.out}")
    print(f"by contract: {json.dumps(by_contract, indent=2)}")
    print(f"by case: {json.dumps(by_case, indent=2)}")
    print("validated: every example holds its own contract (stance+thesis+<=3 bullets, or single valid PM JSON object)")


if __name__ == "__main__":
    main()
