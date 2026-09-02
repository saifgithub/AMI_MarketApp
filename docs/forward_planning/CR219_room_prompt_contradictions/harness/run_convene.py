"""Run one FULL 12-agent Room convene against the on-prem vLLM and score it.

    backend/.venv/bin/python <harness>/run_convene.py --ticker CAT --mandate long

Prompt fidelity: `build_room_messages` is called exactly as `room_runner` calls
it — same phase order, the four analysts sharing an empty transcript by design
(`parallel_phase=True`), the transcript growing turn by turn, and
`max_tokens_for(agent_id)` as the per-agent decode budget. Nothing is appended
to any prompt. This is the difference from `evidence/convene_gemini.py`, which
appends an evaluation addendum to the user message: that addendum is an
INSTRUMENT for eliciting self-reports, and it manufactures at least one
contradiction of its own (the PM's JSON-only contract vs. the two appended
sections — `evidence/README.md` item 2). This harness measures the shipped
prompt, so it sends the shipped prompt.

PM stage mirrors production (R32): `settings.pm_self_consistency_samples`
(default 5, `app/core/config.py:751`) independent draws, parsed with the
production `_parse_pm_verdict` and voted with the production `_vote_pm_samples`
— majority on action, median size among winners, ties to PASS. Never a single
draw: at n=1 the measured flip rate is ~19.7%, so a one-draw verdict cannot be
told from a coin toss.

What this does NOT do: run `enforce_safety_floor`. The floor is a deterministic
post-check on the PM's decision and it needs DB-backed trade history the Mac has
no access to. The harness measures what the ROOM produced; the floor's veto is
production's separate guarantee.
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
from app.services.room_prompts import (  # noqa: E402
    _PHASE_FOR_AGENT,
    build_room_messages,
    max_tokens_for,
)

from build_profile import load_or_build, live_fields, profile_path  # noqa: E402
from mandates import BATTERY, battery_mandate  # noqa: E402
from vllm_client import VLLMClient  # noqa: E402
from score import score_run  # noqa: E402

ORDER = [
    AgentId.FUNDAMENTALS_ANALYST,
    AgentId.MARKET_ANALYST,
    AgentId.NEWS_ANALYST,
    AgentId.SOCIAL_MEDIA_ANALYST,
    AgentId.BULL_RESEARCHER,
    AgentId.BEAR_RESEARCHER,
    AgentId.RESEARCH_MANAGER,
    AgentId.TRADER,
    AgentId.AGGRESSIVE_DEBATOR,
    AgentId.CONSERVATIVE_DEBATOR,
    AgentId.NEUTRAL_DEBATOR,
    AgentId.PORTFOLIO_MANAGER,
]

# The five agents production hands the Execution Desk's proposal to.
_PROPOSAL_AGENTS = {
    AgentId.PORTFOLIO_MANAGER,
    AgentId.TRADER,
    AgentId.AGGRESSIVE_DEBATOR,
    AgentId.CONSERVATIVE_DEBATOR,
    AgentId.NEUTRAL_DEBATOR,
}

PORTFOLIO_VALUE = 10_000.0


def _room_context(ticker, mandate, profile, proposal):
    """A `_RoomContext` carrying only what `_parse_pm_verdict` reads.

    It reads: ticker, mandate (for the risk-tier size ceiling), trader_entry,
    trader_horizon_weeks, option_candidates (empty — the harness mandate does
    not permit derivatives, which is production's ordinary case).
    """
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


def run_convene(
    *,
    ticker: str,
    mandate_label: str,
    client: VLLMClient,
    profiles_dir: str = PROFILES,
    thinking: bool = False,
    pm_samples: int | None = None,
    temperature: float = 1.0,
    verbose: bool = True,
) -> dict:
    mandate = battery_mandate(mandate_label)
    profile = load_or_build(ticker, profiles_dir=profiles_dir)
    live = live_fields(profile)
    identity = client.identity()
    samples = pm_samples if pm_samples is not None else int(
        settings.pm_self_consistency_samples
    )

    if verbose:
        print(
            f"{ticker} × {mandate_label}  model={identity['root']}  "
            f"{len(live)} LIVE fields  pm_samples={samples}  thinking={thinking}",
            flush=True,
        )

    transcript: list[AgentMessage] = []
    turns: list[dict] = []
    proposal: dict | None = None
    pm_record: dict | None = None

    for agent in ORDER:
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

        if agent is AgentId.PORTFOLIO_MANAGER:
            # R32: N independent draws, voted the way production votes them.
            draws = [
                client.chat(
                    system,
                    user,
                    max_tokens=budget,
                    temperature=temperature,
                    thinking=thinking,
                )
                for _ in range(samples)
            ]
            ctx = _room_context(ticker, mandate, profile, proposal or {
                "size_pct": 2.5, "entry": None, "stop": None, "target": None,
            })
            parsed = []
            for d in draws:
                if d.get("error") or not d.get("answer"):
                    continue
                narration, verdict = room_runner._parse_pm_verdict(d["answer"], ctx)
                if verdict is not None:
                    parsed.append((narration, verdict))
            voted = room_runner._vote_pm_samples(parsed) if parsed else None
            approve_votes = sum(
                1 for _n, v in parsed
                if str(v.action) in ("APPROVE", "MODIFY")
            )
            pm_record = {
                "samples_requested": samples,
                "samples_returned": sum(1 for d in draws if not d.get("error")),
                "samples_parsed": len(parsed),
                "approve_votes": approve_votes,
                "agreement": voted[2] if voted else None,
                "actions": [str(v.action) for _n, v in parsed],
                "verdict": json.loads(voted[1].model_dump_json()) if voted else None,
                "draws": [
                    {k: v for k, v in d.items() if k != "answer"} | {
                        "answer": d.get("answer", "")
                    }
                    for d in draws
                ],
            }
            answer = voted[0] if voted else (draws[0].get("answer") or "")
            rec = {
                "agent": agent.value,
                "phase": phase,
                "max_tokens": budget,
                "system_prompt": system,
                "user_message": user,
                "answer": answer,
                "elapsed_s": round(sum(d.get("elapsed_s") or 0 for d in draws), 1),
                "tok_prompt": draws[0].get("tok_prompt"),
                "tok_out": sum(d.get("tok_out") or 0 for d in draws),
                "tok_reasoning": sum(d.get("tok_reasoning") or 0 for d in draws),
                "finish": draws[0].get("finish"),
                "error": next((d["error"] for d in draws if d.get("error")), None),
            }
            if verbose:
                print(
                    f"  {agent.value:22s} {rec['elapsed_s']:6.1f}s  {samples} draws  "
                    f"{len(parsed)} parsed  agreement={pm_record['agreement']}  "
                    f"approve_votes={approve_votes}",
                    flush=True,
                )
        else:
            r = client.chat(
                system, user, max_tokens=budget, temperature=temperature,
                thinking=thinking,
            )
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
            if rec["error"]:
                # CR040: an outage is reported, not smoothed over. The run
                # continues so the remaining turns are still measured, and the
                # scorer counts this turn as failed rather than absent.
                print(f"  {agent.value:22s} ERROR {rec['error'][:120]}", flush=True)
            else:
                if verbose:
                    print(
                        f"  {agent.value:22s} {rec['elapsed_s']:6.1f}s  "
                        f"out {rec['tok_out']:>5}tok "
                        f"(think {rec['tok_reasoning']})  {rec['finish']}",
                        flush=True,
                    )
                transcript.append(AgentMessage(
                    agent_id=agent, content=rec["answer"],
                    timestamp=dt.datetime.now(dt.UTC),
                ))
            if agent is AgentId.TRADER:
                base = profile.get("base_price") or 100.0
                proposal = {
                    "size_pct": 2.5,
                    "entry": base,
                    "stop": round(base * 0.9, 2),
                    "target": round(base * 1.2, 2),
                }
        turns.append(rec)

    return {
        "ticker": ticker,
        "mandate_label": mandate_label,
        "mandate": json.loads(mandate.model_dump_json()),
        "model": identity,
        "thinking": thinking,
        "temperature": temperature,
        "pm_samples": samples,
        "profile_cache": profile_path(ticker, profiles_dir),
        "live_fields": live,
        "ran_at": dt.datetime.now(dt.UTC).isoformat(),
        "turns": turns,
        "pm": pm_record,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ticker", default="CAT")
    ap.add_argument("--mandate", default="long", choices=sorted(BATTERY))
    ap.add_argument("--base-url", default=None, help="override the vLLM base URL")
    ap.add_argument("--profiles-dir", default=PROFILES)
    ap.add_argument("--out-root", default=RESULTS)
    ap.add_argument("--label", default=None, help="subfolder name; default <ticker>_<mandate>")
    ap.add_argument("--thinking", action="store_true", help="R48 arm: per-request thinking ON")
    ap.add_argument("--pm-samples", type=int, default=None,
                    help="override the production sample count (R47 k-sweep)")
    ap.add_argument("--temperature", type=float, default=1.0)
    args = ap.parse_args()

    kw = {"base_url": args.base_url} if args.base_url else {}
    client = VLLMClient(**kw)
    run = run_convene(
        ticker=args.ticker,
        mandate_label=args.mandate,
        client=client,
        profiles_dir=args.profiles_dir,
        thinking=args.thinking,
        pm_samples=args.pm_samples,
        temperature=args.temperature,
    )
    run["scores"] = score_run(run)

    label = args.label or f"{args.ticker.upper()}_{args.mandate}" + (
        "_thinking" if args.thinking else ""
    )
    dest = os.path.join(args.out_root, label)
    os.makedirs(dest, exist_ok=True)
    with open(os.path.join(dest, "run.json"), "w") as fh:
        json.dump(run, fh, indent=1)
    for t in run["turns"]:
        with open(os.path.join(dest, f"{t['agent']}.answer.txt"), "w") as fh:
            fh.write(t["answer"])

    print()
    print(json.dumps(run["scores"], indent=1))
    print(f"\nwrote {dest}/run.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
