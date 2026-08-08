"""CR143 Phase 1a — dump the prompt each agent ACTUALLY receives, per surface.

The 13 files in `content/agents/` are the innermost of six layers. Every prior
read of "the agent prompts" (CR105 most recently) was a read of those files, and
CR105's own Amendment 1 records what that costs: checked against the code that
parses the model's output, two of its four findings were wrong, and shipping the
"fix" would have turned an existing guard red.

So this script never reads a base prompt as if it were the prompt. It calls the
real builders — `build_agent_prompt`, `build_room_messages`,
`build_concierge_messages`, `prepend_grounding_directive` — and writes the
resulting string verbatim. The audit then reads what the model reads.

It also emits a manifest locating each LAYER inside each assembled prompt (offset,
chars, % of total). That is the artifact Phase 2 needs: "the Trader is told X" is
only actionable once you know which layer said it and which layer overrode it.

Deliberate deviations from production, all recorded in the manifest so no reader
mistakes the dump for a capture:
  * user_overlay (Brief Your Agent) is absent — it lives in Postgres, is per-user,
    and no user's briefing belongs in a committed corpus. Its insertion point is
    reported instead.
  * the 1-on-1 live-data blocks are appended in the same order and under the same
    agent gating as `agent_runner.py:186-225`, but from a direct call rather than
    a ticker extracted from a user turn.

Faithfulness is not assumed — `--verify` diffs the reconstruction against real
`llm_audit.system_prompt` rows pulled from melehost. If that check fails the audit
is unsound and stops there (CR143 acceptance).

Usage (from backend/):
    .venv/bin/python -m scripts.dump_assembled_prompts --ticker AAPL
    .venv/bin/python -m scripts.dump_assembled_prompts --verify
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.agents.overlay_generator import generate_overlay
from app.agents.safety_floor import render_safety_floor_block
from app.schemas import AgentId
from app.schemas.agents import TWELVE_AGENT_IDS
from app.schemas.mandate import (
    Compliance,
    Horizon,
    LearningStyle,
    Mandate,
    Path as MandatePath,
    Plan,
    PrimaryGoal,
    RiskComponents,
)
from app.services.agent_prompts import USER_OVERLAY_HEADER, build_agent_prompt, load_base_prompt
from app.services.brief_engine import BRIEF_MODE_PREFIX
from app.services.concierge_prompts import build_concierge_messages
from app.services.llm_gateway import (
    GROUNDING_DIRECTIVE,
    GROUNDING_DIRECTIVE_SENTINEL,
    prepend_grounding_directive,
)
from app.services.room_prompts import _PHASE_FOR_AGENT, build_room_messages

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "docs/forward_planning/CR143_agent_prompt_audit/assembled"

# A fixed, ordinary mandate: risk_score 3, long-only, English, 30% drawdown cap.
# Held constant across every surface so a difference between two dumped prompts is
# always a difference in the CODE, never in the user.
_MANDATE_UUID = UUID("00000000-0000-4000-8000-000000000143")

# The RISK/VERDICT phases are the only ones handed a concrete proposal (DEF066);
# entry 100 / stop 81 / size 5% is the AMD case from the CR035 report, reused here
# so the dumped drawdown line matches the one test_room_prompts.py already pins.
_PROPOSAL = {"size_pct": 5.0, "entry": 100.0, "stop": 81.0, "target": 130.0}

_PARALLEL_PHASE_AGENTS = frozenset(
    a for a, phase in _PHASE_FOR_AGENT.items() if phase == "ANALYSTS"
)


def _mandate() -> Mandate:
    return Mandate(
        user_id=_MANDATE_UUID,
        version=1,
        display_name="Audit Subject",
        locale="en",
        timezone="UTC",
        primary_goal=PrimaryGoal.LONG_TERM_WEALTH,
        horizon=Horizon.LONG,
        target_outcome=None,
        path=MandatePath.LONG_HORIZON,
        risk_score=3,
        risk_components=RiskComponents(
            drawdown_response=3, regret_asymmetry=0, concentration_tolerance=3
        ),
        risk_quotes=[],
        max_drawdown_pct=30,
        compliance=Compliance(long_only=True, liquid_only=True),
        learning_style=LearningStyle.QUICK,
        plan=Plan.TRADER,
        trial_expires_at=None,
        credit_balance=150,
        created_at=datetime(2026, 5, 11),
        updated_at=datetime(2026, 5, 11),
    )


def _portfolio_snapshot(ticker: str) -> str:
    """The CR055 holdings block, in its always-present shape.

    `_build_sim_holdings_block` is the production builder but needs a real
    user_id and a DB session, so this mirrors its rendered shape instead —
    importing the header CONSTANT rather than retyping it, so the one part that
    a reader uses to recognise the block can never drift from production.

    Two holdings rather than an empty portfolio: an empty one renders a shorter
    branch, and the branch that ships to a user who owns things is the one worth
    auditing.
    """
    from app.services.room_runner import _SIM_PORTFOLIO_HEADER

    return (
        f"{_SIM_PORTFOLIO_HEADER}\n"
        "Cash: $42,150.00 | Portfolio value: $108,238.00\n"
        "Open positions:\n"
        "  AAPL ×120 (21.4% of portfolio, unrealised +15,440.00)\n"
        "  MSFT ×40 (15.6% of portfolio, unrealised +796.00)\n"
        f"You hold 0% of {ticker.upper()} — no open position in it. "
        "Any BUY here opens a NEW position.\n"
        "───"
    )


def _locate_layers(assembled: str, layers: list[tuple[str, str]]) -> list[dict[str, Any]]:
    """Locate each named layer inside the assembled prompt.

    Uses `str.find` from the previous layer's end so a fragment repeated across
    layers is attributed to its own occurrence, not the first one anywhere. A
    layer reported as `found: false` is the interesting case — it means the
    composition dropped or transformed it, which is a Phase 2 finding, not a bug
    in this script.
    """
    out: list[dict[str, Any]] = []
    cursor = 0
    total = len(assembled)
    for name, text in layers:
        if not text:
            out.append({"layer": name, "found": False, "chars": 0, "reason": "empty"})
            continue
        idx = assembled.find(text, cursor)
        if idx < 0:
            idx = assembled.find(text)
        if idx < 0:
            out.append(
                {"layer": name, "found": False, "chars": len(text), "reason": "not in assembled"}
            )
            continue
        out.append(
            {
                "layer": name,
                "found": True,
                "offset": idx,
                "chars": len(text),
                "pct_of_prompt": round(100.0 * len(text) / total, 1),
            }
        )
        cursor = idx + len(text)
    return out


def _room_prompt(agent_id: AgentId, mandate: Mandate, ticker: str, profile: dict[str, Any]):
    phase = _PHASE_FOR_AGENT[agent_id]
    system_prompt, _ = build_room_messages(
        agent_id=agent_id,
        mandate=mandate,
        user_id=None,
        ticker=ticker,
        profile=profile,
        transcript=[],
        portfolio_snapshot=_portfolio_snapshot(ticker),
        plan=Plan.TRADER,
        trade_proposal=_PROPOSAL if phase in ("RISK", "VERDICT") else None,
        parallel_phase=agent_id in _PARALLEL_PHASE_AGENTS,
        sector_weights={"Technology": 37.0, "Healthcare": 11.2, "Cash": 51.8},
    )
    return prepend_grounding_directive(system_prompt)


def _one_on_one_prompt(agent_id: AgentId, mandate: Mandate, ticker: str, live: bool):
    """Reconstruct agent_runner.py:160-225 — base + the per-agent live blocks."""
    system_prompt = build_agent_prompt(agent_id, mandate, user_id=None)
    appended: list[tuple[str, str]] = []
    if live:
        from app.services.fundamentals import build_live_data_block
        from app.services.journal_context import build_journal_context_block
        from app.services.news_context import build_news_context_block
        from app.services.social_context import build_social_context_block
        from app.services.technicals import build_technicals_context_block

        blocks: list[tuple[str, Any]] = [("live_data", build_live_data_block)]
        if agent_id == AgentId.NEWS_ANALYST:
            blocks.append(("news_context", build_news_context_block))
        if agent_id == AgentId.SOCIAL_MEDIA_ANALYST:
            blocks.append(("social_context", build_social_context_block))
        if agent_id == AgentId.MARKET_ANALYST:
            blocks.append(("technicals_context", build_technicals_context_block))
        for name, fn in blocks:
            try:
                block = fn(ticker)
            except Exception as exc:  # a dead feed is a finding, not a crash
                appended.append((name, f"<<FETCH FAILED: {type(exc).__name__}: {exc}>>"))
                continue
            if block:
                system_prompt = system_prompt + "\n\n" + block
                appended.append((name, block))
            else:
                appended.append((name, ""))
        if agent_id in (AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER):
            # Journal context needs a real user_id + DB; absent here by design.
            appended.append(("journal_context", ""))
    return prepend_grounding_directive(system_prompt), appended


def _concierge_prompt(mandate: Mandate):
    from app.services.lessons_service import get_lessons_service

    lessons = get_lessons_service().all_meta()
    system_prompt, _ = build_concierge_messages(
        mandate=mandate,
        user_id=None,
        user_message="What should I look at today?",
        history=[],
        recent_journal=[],
        unlocked_agents={a.value for a in TWELVE_AGENT_IDS},
        available_lessons=lessons,
        unlock_requirements=None,
    )
    return prepend_grounding_directive(system_prompt), len(lessons)


def _brief_prompt(agent_id: AgentId):
    """Reconstruct brief_engine.py:243-249 — base + overlay slot + BRIEF_MODE_PREFIX."""
    base = load_base_prompt(agent_id)
    active_block = "\n\nYou have no user_overlay yet — running on defaults."
    return prepend_grounding_directive(base + active_block + "\n\n" + BRIEF_MODE_PREFIX)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def dump(out_dir: Path, ticker: str, live: bool) -> dict[str, Any]:
    mandate = _mandate()
    manifest: dict[str, Any] = {
        "cr": "CR143",
        "generated_for_ticker": ticker,
        "live_market_data": live,
        "git_rev": _git_rev(),
        "mandate": {
            "risk_score": 3, "max_drawdown_pct": 30, "long_only": True,
            "locale": "en", "plan": "trader",
        },
        "deviations_from_production": [
            "user_overlay (Brief Your Agent) absent — per-user, lives in Postgres",
            "Room transcript empty — every agent dumped as if speaking first",
            "1-on-1 journal_context absent — needs a real user_id + DB",
        ],
        "surfaces": {},
    }

    profile: dict[str, Any] = {"data_source": "synthetic"}
    if live:
        from app.services.room_runner import _profile_for_ticker

        profile = _profile_for_ticker(ticker)
    _write(out_dir / "_profile.json", json.dumps(profile, indent=2, default=str))

    # ── Room ────────────────────────────────────────────────────────────────
    room: dict[str, Any] = {}
    for agent_id in TWELVE_AGENT_IDS:
        assembled = _room_prompt(agent_id, mandate, ticker, profile)
        _write(out_dir / "room" / f"{agent_id.value}.txt", assembled)
        layers = _locate_layers(
            assembled,
            [
                ("grounding_directive", GROUNDING_DIRECTIVE.strip()),
                ("base_prompt", load_base_prompt(agent_id).strip()),
                ("mandate_overlay", generate_overlay(agent_id, mandate).strip()),
                ("user_overlay", ""),
                ("portfolio_snapshot", _portfolio_snapshot(ticker).strip()),
                (
                    "safety_floor",
                    render_safety_floor_block(mandate).strip()
                    if agent_id == AgentId.PORTFOLIO_MANAGER
                    else "",
                ),
            ],
        )
        room[agent_id.value] = {
            "phase": _PHASE_FOR_AGENT[agent_id],
            "chars": len(assembled),
            "lines": assembled.count("\n") + 1,
            "layers": layers,
            "unattributed_chars": len(assembled)
            - sum(la.get("chars", 0) for la in layers if la.get("found")),
        }
    manifest["surfaces"]["room"] = room

    # ── 1-on-1 ──────────────────────────────────────────────────────────────
    one: dict[str, Any] = {}
    for agent_id in TWELVE_AGENT_IDS:
        assembled, appended = _one_on_one_prompt(agent_id, mandate, ticker, live)
        _write(out_dir / "one_on_one" / f"{agent_id.value}.txt", assembled)
        one[agent_id.value] = {
            "chars": len(assembled),
            "lines": assembled.count("\n") + 1,
            "live_blocks": {n: len(b) for n, b in appended},
            "live_blocks_empty": [n for n, b in appended if not b],
        }
    manifest["surfaces"]["one_on_one"] = one

    # ── Concierge ───────────────────────────────────────────────────────────
    assembled, lesson_count = _concierge_prompt(mandate)
    _write(out_dir / "concierge" / "concierge.txt", assembled)
    manifest["surfaces"]["concierge"] = {
        "chars": len(assembled),
        "lines": assembled.count("\n") + 1,
        "lessons_in_catalogue": lesson_count,
        "layers": _locate_layers(
            assembled,
            [
                ("grounding_directive", GROUNDING_DIRECTIVE.strip()),
                ("base_prompt", load_base_prompt(AgentId.CONCIERGE).strip()),
                ("mandate_overlay", generate_overlay(AgentId.CONCIERGE, mandate).strip()),
            ],
        ),
    }

    # ── Brief Your Agent ────────────────────────────────────────────────────
    brief: dict[str, Any] = {}
    for agent_id in (*TWELVE_AGENT_IDS, AgentId.CONCIERGE):
        assembled = _brief_prompt(agent_id)
        _write(out_dir / "brief" / f"{agent_id.value}.txt", assembled)
        brief[agent_id.value] = {"chars": len(assembled), "lines": assembled.count("\n") + 1}
    manifest["surfaces"]["brief"] = brief

    manifest["user_overlay_header"] = USER_OVERLAY_HEADER
    _write(out_dir / "_manifest.json", json.dumps(manifest, indent=2))
    return manifest


# ── Faithfulness check (CR143 acceptance) ───────────────────────────────────

# The layer markers, in the order production emits them. Order is the assertion
# that matters most: the PM's safety floor must be LAST of the base layers
# (recency dominance) and the grounding directive FIRST (prepend-only) — those
# two placements are load-bearing and commented as such in llm_gateway.py:84-89.
_ORDERED_MARKERS = [
    "GROUNDING DIRECTIVE",
    "You are the Portfolio Manager",
    "YOUR SIMULATED PORTFOLIO",
    "SAFETY FLOOR",
    "CONVENE THE ROOM",
    "Fact sheet as of",
    "User mandate snapshot",
    "Transcript so far",
    "You are the final decision-maker",
    "There are exactly two action values",
]

_PSQL = (
    "docker exec ami_postgres psql -U postgres -d ami_trade -t -A -c "
    "\"select system_prompt from llm_audit where agent_id='portfolio_manager' "
    "and flow='room_pm' order by created_at desc limit {n};\""
)


def _segment(text: str, start: str, end: str) -> str:
    i = text.find(start)
    j = text.find(end, i + 1) if i >= 0 else -1
    return text[i:j] if i >= 0 and j > i else ""


def verify(out_dir: Path, samples: int) -> int:
    """Diff the reconstruction against real prompts Alpha actually sent.

    Passes when the marker ORDER matches and every char of size difference is
    attributable to a documented deviation (an empty transcript, a different
    ticker, a different mandate). An unexplained residual means the
    reconstruction is not what the model sees, and the audit built on it would be
    unsound — so this exits non-zero rather than warning.
    """
    mine_path = out_dir / "room" / "portfolio_manager.txt"
    if not mine_path.exists():
        print(f"FAIL: no dump at {mine_path} — run without --verify first", file=sys.stderr)
        return 2
    mine = mine_path.read_text(encoding="utf-8")

    raw = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=15", "melehost", _PSQL.format(n=samples)],
        capture_output=True, text=True,
    )
    if raw.returncode != 0:
        print(f"FAIL: could not reach melehost: {raw.stderr.strip()}", file=sys.stderr)
        return 2

    # psql -A -t renders embedded newlines as a literal backslash-n, so rows run
    # together. Split on the grounding SENTINEL (the full line, not the phrase —
    # splitting on the phrase leaves the sentinel's own "─── " prefix behind as a
    # phantom row) and drop anything too short to be a prompt.
    _MIN_PROMPT_CHARS = 1_000
    rows = [
        r for r in raw.stdout.replace("\\n", "\n").split(GROUNDING_DIRECTIVE_SENTINEL)
        if len(r.strip()) >= _MIN_PROMPT_CHARS
    ]
    if not rows:
        print("FAIL: melehost returned no room_pm prompts", file=sys.stderr)
        return 2

    def order(t: str) -> list[str]:
        found = [(t.find(m), m) for m in _ORDERED_MARKERS if t.find(m) >= 0]
        return [m for _, m in sorted(found)]

    mine_order = order(mine)
    failures = 0
    print(f"verifying reconstruction against {len(rows)} real room_pm prompt(s)\n")
    for i, row in enumerate(rows, 1):
        real = GROUNDING_DIRECTIVE_SENTINEL + row
        real_order = order(real)
        # The dumped prompt always carries the holdings block; a real run against a
        # user with no positions renders a different branch, so compare on the
        # markers PRESENT IN BOTH rather than demanding identical sets.
        shared = [m for m in mine_order if m in real_order]
        ok_order = [m for m in real_order if m in shared] == shared
        segs = {
            "transcript": ("Transcript so far", "\nYour turn."),
            "fact_sheet": ("Fact sheet as of", "User mandate snapshot"),
            "safety_floor": ("SAFETY FLOOR", "CONVENE THE ROOM"),
            "base+overlay": ("You are the Portfolio Manager", "SAFETY FLOOR"),
        }
        deltas = {
            n: len(_segment(real, a, b)) - len(_segment(mine, a, b))
            for n, (a, b) in segs.items()
        }
        residual = (len(real) - len(mine)) - sum(deltas.values())
        ok = ok_order and abs(residual) <= 64
        failures += not ok
        print(f"  sample {i}: {'PASS' if ok else 'FAIL'}")
        print(f"    marker order matches : {ok_order}")
        print(f"    real {len(real):,} chars vs dumped {len(mine):,}  "
              f"(delta {len(real) - len(mine):+,})")
        for n, d in deltas.items():
            print(f"      {n:14s} {d:+8,}")
        print(f"    unattributed residual: {residual:+,} (tolerance ±64)")
        if not ok_order:
            print(f"      real : {' > '.join(real_order)}")
            print(f"      mine : {' > '.join(mine_order)}")
    print()
    if failures:
        print(f"FAIL — {failures}/{len(rows)} samples unfaithful. "
              f"The audit cannot be built on this dump (CR143 acceptance).")
        return 1
    print(f"PASS — {len(rows)}/{len(rows)} samples: same layers, same order, "
          f"every char of difference attributed.")
    return 0


def _git_rev() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", default="AAPL")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--no-live", action="store_true",
        help="Skip every network fetch. Produces an ALL-FIELDS-ABSENT profile — "
             "honest, but not what Alpha sends; do not audit numbers from it.",
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Diff the existing dump against real llm_audit prompts on melehost. "
             "Exits non-zero if the reconstruction is unfaithful.",
    )
    parser.add_argument("--verify-samples", type=int, default=5)
    args = parser.parse_args()

    if args.verify:
        return verify(args.out_dir, args.verify_samples)

    manifest = dump(args.out_dir, args.ticker.upper(), live=not args.no_live)

    print(f"wrote {args.out_dir}")
    for surface, data in manifest["surfaces"].items():
        if surface == "concierge":
            print(f"  {surface:12s} {data['chars']:>7,} chars")
            continue
        total = sum(v["chars"] for v in data.values())
        biggest = max(data.items(), key=lambda kv: kv[1]["chars"])
        print(
            f"  {surface:12s} {len(data):>2} prompts · {total:>7,} chars · "
            f"largest {biggest[0]} at {biggest[1]['chars']:,}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
