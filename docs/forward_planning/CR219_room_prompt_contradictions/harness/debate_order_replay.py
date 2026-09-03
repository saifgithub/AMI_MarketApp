"""WP13 / R58 — does the RESEARCHERS debate order move the RM stance / PM verdict?

    backend/.venv/bin/python <harness>/debate_order_replay.py \
        --tickers CAT MSFT XOM AAPL JPM JNJ PG NVDA \
        --mandates short medium long \
        --label R58_debate_order

`05_further_improvements.md` §12: Bull always speaks before Bear
(`room_runner.PHASES`, RESEARCHERS phase). LLM judges anchor on order, and the
Research Manager reads both sides before it writes SYNTHESIS. This script is the
measurement CR219's WP13 asks for: for each (ticker, mandate) CONTEXT, share one
ANALYSTS-phase prefix, then fork into two branches that diverge ONLY in
RESEARCHERS order — Bull-then-Bear (today's fixed order) vs. Bear-then-Bull
(`room_runner._researchers_order`'s odd-run-id branch) — and carry BOTH forks
through SYNTHESIS, EXECUTION, RISK and VERDICT. Nothing else about the run
differs: same profile (same cached pickle, same instant in market time), same
mandate, same four analyst turns, same trader/risk/PM prompts modulo the one
thing under test.

This reuses `run_convene.py`'s own per-agent turn logic (same `build_room_messages`
call shape, same `max_tokens_for` budgets, same production PM voting via
`_parse_pm_verdict` / `_vote_pm_samples`) rather than re-deriving it — the harness
convention (README: "every script runs from any working directory... paths derive
from the script's own location") and the WP's own instruction to read
`run_convene.py`'s idiom rather than build a second one.

**What "same banked context" means here**: unlike `pm_replay.py`, which replays
a PM turn from `system_prompt`/`user_message` bytes ALREADY BANKED in a prior
`run.json`, this script drives fresh RESEARCHERS-onward turns for both orders in
one process, from the SAME loaded profile and the SAME four analyst answers
(computed once, reused by both forks) — so "same context, both orders" is
enforced by construction, not by re-reading a file. The four ANALYSTS turns
cost one call each regardless of debate order (CR077: analysts are blind to
each other and to RESEARCHERS), so sharing them is a legitimate 2x cost saving,
not a shortcut around the thing being measured (RESEARCHERS onward).

Cost per context: 4 analysts (shared) + 2 x (2 researchers + 1 RM + 1 trader +
3 risk debators + `pm_self_consistency_samples` PM draws). At the production
default of 5 PM samples that is 4 + 2x12 = 28 calls per context — this is a
genuinely long, strictly-sequential run against a shared LAN resource (same
discipline as `pm_replay.py`); budget accordingly.
"""
import argparse
import datetime as dt
import json
import os
import sys

from _paths import PROFILES, RESULTS, bootstrap

bootstrap()

from app.core.config import settings  # noqa: E402

settings.use_real_market_data = True
settings.suppress_analyst_consensus = False

from app.schemas.agents import AgentId, AgentMessage  # noqa: E402
from app.services import room_runner  # noqa: E402
from app.services.room_runner import parse_stance_envelope  # noqa: E402
from app.services.room_prompts import (  # noqa: E402
    _PHASE_FOR_AGENT,
    build_room_messages,
    max_tokens_for,
)

from build_profile import load_or_build, live_fields, profile_path  # noqa: E402
from mandates import BATTERY, battery_mandate  # noqa: E402
from vllm_client import VLLMClient  # noqa: E402

ANALYSTS_ORDER = [
    AgentId.FUNDAMENTALS_ANALYST,
    AgentId.MARKET_ANALYST,
    AgentId.NEWS_ANALYST,
    AgentId.SOCIAL_MEDIA_ANALYST,
]

# The two orders under test. Named after `room_runner._researchers_order`'s two
# branches (even/odd run id -> Bull-first/Bear-first) — this script measures
# the same two shapes production can now serve, not an invented third order.
ORDER_BULL_FIRST = "bull_first"
ORDER_BEAR_FIRST = "bear_first"
_RESEARCHER_SEQUENCES = {
    ORDER_BULL_FIRST: [AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER],
    ORDER_BEAR_FIRST: [AgentId.BEAR_RESEARCHER, AgentId.BULL_RESEARCHER],
}

POST_RESEARCHERS_ORDER = [
    AgentId.RESEARCH_MANAGER,
    AgentId.TRADER,
    AgentId.AGGRESSIVE_DEBATOR,
    AgentId.CONSERVATIVE_DEBATOR,
    AgentId.NEUTRAL_DEBATOR,
    AgentId.PORTFOLIO_MANAGER,
]

_PROPOSAL_AGENTS = {
    AgentId.PORTFOLIO_MANAGER,
    AgentId.TRADER,
    AgentId.AGGRESSIVE_DEBATOR,
    AgentId.CONSERVATIVE_DEBATOR,
    AgentId.NEUTRAL_DEBATOR,
}

PORTFOLIO_VALUE = 10_000.0


def _room_context(ticker, mandate, profile, proposal):
    return room_runner._RoomContext(
        ticker=ticker,
        mandate=mandate,
        portfolio_value=PORTFOLIO_VALUE,
        current_drawdown_pct=0.0,
        halal_universe=set(),
        classification_universe=None,
        locale_allowed_universe=None,
        profile=profile,
        trader_size_pct=proposal["size_pct"],
        trader_entry=proposal["entry"],
        trader_stop=proposal["stop"],
        trader_target=proposal["target"],
    )


def _one_turn(client, agent, ticker, mandate, profile, transcript, proposal,
              *, temperature: float, verbose: bool) -> dict:
    """One agent turn, same shape `run_convene.py` produces per turn."""
    phase = _PHASE_FOR_AGENT[agent]
    kw = {}
    if agent in _PROPOSAL_AGENTS and proposal:
        kw["trade_proposal"] = proposal
    system, messages = build_room_messages(
        agent_id=agent,
        mandate=mandate,
        user_id=None,
        ticker=ticker,
        profile=profile,
        transcript=[] if phase == "ANALYSTS" else transcript,
        parallel_phase=(phase == "ANALYSTS"),
        portfolio_value=PORTFOLIO_VALUE,
        **kw,
    )
    user = messages[-1].content
    budget = max_tokens_for(agent)
    r = client.chat(system, user, max_tokens=budget, temperature=temperature)
    rec = {
        "agent": agent.value,
        "phase": phase,
        "max_tokens": budget,
        "system_prompt": system,
        "user_message": user,
        "answer": r.get("answer", ""),
        "elapsed_s": r.get("elapsed_s"),
        "tok_prompt": r.get("tok_prompt"),
        "tok_out": r.get("tok_out"),
        "tok_reasoning": r.get("tok_reasoning"),
        "finish": r.get("finish"),
        "error": r.get("error"),
    }
    if verbose:
        if rec["error"]:
            print(f"    {agent.value:22s} ERROR {rec['error'][:120]}", flush=True)
        else:
            print(
                f"    {agent.value:22s} {rec['elapsed_s']:6.1f}s  "
                f"out {rec['tok_out']:>5}tok  {rec['finish']}",
                flush=True,
            )
    return rec


def _pm_vote(client, ctx, system, user, budget, *, samples: int,
             temperature: float, verbose: bool) -> dict:
    """R32: N independent draws, parsed + voted the way production does."""
    draws = [
        client.chat(system, user, max_tokens=budget, temperature=temperature)
        for _ in range(samples)
    ]
    parsed = []
    for d in draws:
        truncated = d.get("finish") == "length"
        if d.get("error") or not d.get("answer") or truncated:
            continue
        _narr, verdict = room_runner._parse_pm_verdict(d["answer"], ctx)
        if verdict is not None:
            parsed.append((_narr, verdict))
    voted = room_runner._vote_pm_samples(parsed) if parsed else None
    approve_votes = sum(
        1 for _n, v in parsed if str(v.action) in ("APPROVE", "MODIFY")
    )
    record = {
        "samples_requested": samples,
        "samples_returned": sum(1 for d in draws if not d.get("error")),
        "samples_truncated": sum(1 for d in draws if d.get("finish") == "length"),
        "samples_parsed": len(parsed),
        "approve_votes": approve_votes,
        "agreement": voted[2] if voted else None,
        "actions": [str(v.action) for _n, v in parsed],
        "verdict": json.loads(voted[1].model_dump_json()) if voted else None,
        "answer": voted[0] if voted else (draws[0].get("answer") or ""),
        "elapsed_s": round(sum(d.get("elapsed_s") or 0 for d in draws), 1),
        "tok_out_total": sum(d.get("tok_out") or 0 for d in draws),
    }
    if verbose:
        action = str(voted[1].action) if voted else "NO_VERDICT"
        print(
            f"    {'portfolio_manager':22s} {record['elapsed_s']:6.1f}s  "
            f"{samples} draws  {len(parsed)} parsed  action={action} "
            f"agreement={record['agreement']}",
            flush=True,
        )
    return record


def _run_branch(client, order_label, ticker, mandate, profile,
                 analyst_transcript, *, pm_samples, temperature, verbose):
    """RESEARCHERS onward, starting from the shared analyst transcript. Returns
    the turns for this branch plus the RM stance envelope and the PM record."""
    transcript = list(analyst_transcript)
    turns = []
    proposal = None
    rm_stance = None
    pm_record = None

    for agent in _RESEARCHER_SEQUENCES[order_label]:
        rec = _one_turn(
            client, agent, ticker, mandate, profile, transcript, proposal,
            temperature=temperature, verbose=verbose,
        )
        if not rec["error"]:
            transcript.append(AgentMessage(
                agent_id=agent, content=rec["answer"],
                timestamp=dt.datetime.now(dt.UTC),
            ))
        turns.append(rec)

    for agent in POST_RESEARCHERS_ORDER:
        if agent is AgentId.PORTFOLIO_MANAGER:
            phase = _PHASE_FOR_AGENT[agent]
            kw = {"trade_proposal": proposal} if proposal else {}
            system, messages = build_room_messages(
                agent_id=agent, mandate=mandate, user_id=None, ticker=ticker,
                profile=profile, transcript=transcript, parallel_phase=False,
                portfolio_value=PORTFOLIO_VALUE, **kw,
            )
            user = messages[-1].content
            budget = max_tokens_for(agent)
            ctx = _room_context(ticker, mandate, profile, proposal or {
                "size_pct": 2.5, "entry": None, "stop": None, "target": None,
            })
            pm_record = _pm_vote(
                client, ctx, system, user, budget,
                samples=pm_samples, temperature=temperature, verbose=verbose,
            )
            turns.append({
                "agent": agent.value, "phase": phase, "max_tokens": budget,
                "system_prompt": system, "user_message": user,
                "answer": pm_record["answer"],
                "elapsed_s": pm_record["elapsed_s"],
                "tok_out": pm_record["tok_out_total"],
                "finish": None, "error": None,
            })
            continue

        rec = _one_turn(
            client, agent, ticker, mandate, profile, transcript, proposal,
            temperature=temperature, verbose=verbose,
        )
        if not rec["error"]:
            transcript.append(AgentMessage(
                agent_id=agent, content=rec["answer"],
                timestamp=dt.datetime.now(dt.UTC),
            ))
            if agent is AgentId.RESEARCH_MANAGER:
                _prose, env = parse_stance_envelope(rec["answer"])
                rm_stance = {
                    "stance": env.stance, "conviction": env.conviction,
                    "headline": env.headline,
                }
        turns.append(rec)

        if agent is AgentId.TRADER and not rec["error"]:
            base = profile.get("base_price") or 100.0
            proposal = {
                "size_pct": 2.5,
                "entry": base,
                "stop": round(base * 0.9, 2),
                "target": round(base * 1.2, 2),
            }

    return {
        "order": order_label,
        "researcher_sequence": [a.value for a in _RESEARCHER_SEQUENCES[order_label]],
        "turns": turns,
        "rm_stance": rm_stance,
        "pm": pm_record,
    }


def run_context(
    *, ticker: str, mandate_label: str, client: VLLMClient,
    profiles_dir: str = PROFILES, pm_samples: int, temperature: float = 1.0,
    verbose: bool = True,
) -> dict:
    mandate = battery_mandate(mandate_label)
    profile = load_or_build(ticker, profiles_dir=profiles_dir)
    identity = client.identity()

    if verbose:
        print(
            f"\n{ticker} x {mandate_label}  model={identity['root']}  "
            f"pm_samples={pm_samples}",
            flush=True,
        )
        print("  ANALYSTS (shared prefix)", flush=True)

    analyst_transcript: list[AgentMessage] = []
    analyst_turns = []
    for agent in ANALYSTS_ORDER:
        rec = _one_turn(
            client, agent, ticker, mandate, profile, [], None,
            temperature=temperature, verbose=verbose,
        )
        if not rec["error"]:
            analyst_transcript.append(AgentMessage(
                agent_id=agent, content=rec["answer"],
                timestamp=dt.datetime.now(dt.UTC),
            ))
        analyst_turns.append(rec)

    branches = {}
    for order_label in (ORDER_BULL_FIRST, ORDER_BEAR_FIRST):
        if verbose:
            seq = " -> ".join(a.value for a in _RESEARCHER_SEQUENCES[order_label])
            print(f"  RESEARCHERS order={order_label} ({seq})", flush=True)
        branches[order_label] = _run_branch(
            client, order_label, ticker, mandate, profile, analyst_transcript,
            pm_samples=pm_samples, temperature=temperature, verbose=verbose,
        )

    return {
        "ticker": ticker,
        "mandate_label": mandate_label,
        "mandate": json.loads(mandate.model_dump_json()),
        "model": identity,
        "pm_samples": pm_samples,
        "temperature": temperature,
        "profile_cache": profile_path(ticker, profiles_dir),
        "live_fields": live_fields(profile),
        "ran_at": dt.datetime.now(dt.UTC).isoformat(),
        "analyst_turns": analyst_turns,
        "branches": branches,
    }


def compare(context_result: dict) -> dict:
    """Did order move the RM stance or the PM verdict, for one context?"""
    a = context_result["branches"][ORDER_BULL_FIRST]
    b = context_result["branches"][ORDER_BEAR_FIRST]
    rm_a, rm_b = a["rm_stance"], b["rm_stance"]
    pm_a, pm_b = a["pm"], b["pm"]

    rm_stance_matches = (
        rm_a is not None and rm_b is not None and rm_a["stance"] == rm_b["stance"]
    )
    rm_conviction_matches = (
        rm_a is not None and rm_b is not None
        and rm_a["conviction"] == rm_b["conviction"]
    )
    pm_action_a = (pm_a or {}).get("verdict", {}) or {}
    pm_action_b = (pm_b or {}).get("verdict", {}) or {}
    pm_action_matches = (
        bool(pm_action_a) and bool(pm_action_b)
        and pm_action_a.get("action") == pm_action_b.get("action")
    )

    return {
        "ticker": context_result["ticker"],
        "mandate_label": context_result["mandate_label"],
        "rm_stance_bull_first": rm_a,
        "rm_stance_bear_first": rm_b,
        "rm_stance_matches": rm_stance_matches if (rm_a and rm_b) else None,
        "rm_conviction_matches": rm_conviction_matches if (rm_a and rm_b) else None,
        "pm_action_bull_first": pm_action_a.get("action"),
        "pm_action_bear_first": pm_action_b.get("action"),
        "pm_action_matches": pm_action_matches if (pm_action_a and pm_action_b) else None,
        "pm_size_bull_first": pm_action_a.get("size_pct"),
        "pm_size_bear_first": pm_action_b.get("size_pct"),
        "pm_parse_rate_bull_first": (
            round(pm_a["samples_parsed"] / pm_a["samples_requested"], 3)
            if pm_a and pm_a.get("samples_requested") else None
        ),
        "pm_parse_rate_bear_first": (
            round(pm_b["samples_parsed"] / pm_b["samples_requested"], 3)
            if pm_b and pm_b.get("samples_requested") else None
        ),
    }


def _summarise(comparisons: list[dict]) -> dict:
    rm_judged = [c for c in comparisons if c["rm_stance_matches"] is not None]
    pm_judged = [c for c in comparisons if c["pm_action_matches"] is not None]
    return {
        "n_contexts": len(comparisons),
        "rm_stance_judged": len(rm_judged),
        "rm_stance_moved": sum(1 for c in rm_judged if not c["rm_stance_matches"]),
        "rm_stance_move_rate": (
            round(sum(1 for c in rm_judged if not c["rm_stance_matches"]) / len(rm_judged), 4)
            if rm_judged else None
        ),
        "rm_conviction_judged": sum(1 for c in comparisons if c["rm_conviction_matches"] is not None),
        "rm_conviction_moved": sum(
            1 for c in comparisons if c["rm_conviction_matches"] is False
        ),
        "pm_action_judged": len(pm_judged),
        "pm_action_moved": sum(1 for c in pm_judged if not c["pm_action_matches"]),
        "pm_action_move_rate": (
            round(sum(1 for c in pm_judged if not c["pm_action_matches"]) / len(pm_judged), 4)
            if pm_judged else None
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tickers", nargs="+", required=True)
    ap.add_argument("--mandates", nargs="+", default=sorted(BATTERY),
                    choices=sorted(BATTERY))
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--profiles-dir", default=PROFILES)
    ap.add_argument("--out-root", default=RESULTS)
    ap.add_argument("--label", required=True)
    ap.add_argument("--pm-samples", type=int, default=None,
                    help="override; defaults to settings.pm_self_consistency_samples")
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--resume", action="store_true",
                    help="skip (ticker, mandate) pairs already present in an "
                         "existing <label>.json (e.g. after a crash/OOM kill) "
                         "instead of redoing them")
    args = ap.parse_args()

    kw = {"base_url": args.base_url} if args.base_url else {}
    client = VLLMClient(**kw)
    pm_samples = args.pm_samples if args.pm_samples is not None else int(
        settings.pm_self_consistency_samples
    )

    os.makedirs(args.out_root, exist_ok=True)
    dest = os.path.join(args.out_root, f"{args.label}.json")

    contexts: list[dict] = []
    comparisons: list[dict] = []
    done: set[tuple[str, str]] = set()
    if args.resume and os.path.exists(dest):
        with open(dest) as fh:
            prior = json.load(fh)
        prior_contexts = prior.get("contexts", [])
        prior_comparisons = prior.get("comparisons", [])
        # A comparison with BOTH matches None means every draw on at least one
        # branch errored (e.g. the LAN serve was down mid-run) — that context
        # produced no usable data and must be RETRIED, not skipped. Only a
        # context that actually judged something counts as done.
        usable_keys = {
            (c["ticker"], c["mandate_label"]) for c in prior_comparisons
            if c["rm_stance_matches"] is not None or c["pm_action_matches"] is not None
        }
        broken_keys = {
            (c["ticker"], c["mandate_label"]) for c in prior_comparisons
        } - usable_keys
        contexts = [
            c for c in prior_contexts
            if (c["ticker"], c["mandate_label"]) in usable_keys
        ]
        comparisons = [
            c for c in prior_comparisons
            if (c["ticker"], c["mandate_label"]) in usable_keys
        ]
        done = usable_keys
        print(
            f"--resume: {len(usable_keys)} usable (ticker, mandate) pairs kept, "
            f"{len(broken_keys)} broken pairs will be RETRIED: {sorted(broken_keys)}",
            flush=True,
        )

    for ticker in args.tickers:
        for mandate_label in args.mandates:
            if (ticker, mandate_label) in done:
                continue
            ctx_result = run_context(
                ticker=ticker, mandate_label=mandate_label, client=client,
                profiles_dir=args.profiles_dir, pm_samples=pm_samples,
                temperature=args.temperature,
            )
            contexts.append(ctx_result)
            cmp = compare(ctx_result)
            comparisons.append(cmp)
            print(
                f"  -> RM stance match={cmp['rm_stance_matches']}  "
                f"PM action match={cmp['pm_action_matches']}  "
                f"({cmp['pm_action_bull_first']} vs {cmp['pm_action_bear_first']})",
                flush=True,
            )
            # Checkpoint after EVERY context, not just at the end — a crash
            # (this exact failure mode: an OOM kill on a shared, contended
            # machine took the process mid-run with 16/24 contexts computed
            # and nothing durable to show for them) must lose at most one
            # context's work, never the whole run. `--resume` reads this file
            # back to skip what's already here.
            checkpoint = {
                "label": args.label,
                "n_contexts": len(comparisons),
                "tickers": args.tickers,
                "mandates": args.mandates,
                "pm_samples": pm_samples,
                "temperature": args.temperature,
                "ran_at": dt.datetime.now(dt.UTC).isoformat(),
                "identity": client.identity(),
                "summary": _summarise(comparisons),
                "comparisons": comparisons,
                "contexts": contexts,
                "complete": False,
            }
            tmp = dest + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(checkpoint, fh, indent=1)
            os.replace(tmp, dest)  # atomic on POSIX — never a half-written file

    summary = _summarise(comparisons)
    out = {
        "label": args.label,
        "n_contexts": len(comparisons),
        "tickers": args.tickers,
        "mandates": args.mandates,
        "pm_samples": pm_samples,
        "temperature": args.temperature,
        "ran_at": dt.datetime.now(dt.UTC).isoformat(),
        "identity": client.identity(),
        "summary": summary,
        "comparisons": comparisons,
        "contexts": contexts,
        "complete": True,
    }

    tmp = dest + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(out, fh, indent=1)
    os.replace(tmp, dest)

    print()
    print(json.dumps(summary, indent=1))
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
