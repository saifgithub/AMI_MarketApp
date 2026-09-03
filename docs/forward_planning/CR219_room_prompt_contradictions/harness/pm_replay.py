"""Replay the PM stage alone, k times, against a transcript that never moves.

    backend/.venv/bin/python <harness>/pm_replay.py \
        --run results/CAT_long/run.json --k 20 --label R47_CAT

R47 asks for the residual flip rate at the production sample count (n=5, since
CR214). A flip rate is only interpretable if the PM's INPUT is identical across
repetitions: rerunning the eleven upstream agents each time would vary the
transcript, and a verdict difference could then be the transcript's rather than
the PM's own decode variance. So the convene runs ONCE (`run_convene.py`), and
this script replays the PM turn from the exact `system_prompt` /`user_message`
bytes that convene banked in `run.json`. Nothing is re-derived, nothing is
re-rendered — the prompt bytes are read back verbatim.

R48's A/B rides the same driver for the same reason: both arms must see one
fixed transcript, so the only difference between them is the thinking flag.

Each of the k repetitions is a FULL production-mirroring vote:
`pm_self_consistency_samples` draws, each parsed by the production
`_parse_pm_verdict` and voted by the production `_vote_pm_samples`. A repetition
is one *verdict*, not one draw — the flip rate we care about is the rate at
which the SHIPPED procedure lands somewhere else, not the rate at which a single
sample wanders.

Requests are issued strictly sequentially. The serve is a shared LAN resource
and a parallel batch would both perturb the latency numbers and be rude.

Truncation is fatal to a draw, never silent: a draw whose `finish_reason` is
`length` clipped its JSON envelope mid-object, which `_parse_pm_verdict` then
fails safe to PASS on. Counting such a draw as a PASS vote would manufacture
exactly the result R48's thinking arm is at risk of. `truncated` is recorded per
draw and totalled per arm; the write-up must report it.
"""
import argparse
import datetime as dt
import json
import os
import statistics
import sys
from collections import Counter

from _paths import PROFILES, RESULTS, bootstrap

bootstrap()

from app.core.config import settings  # noqa: E402

settings.use_real_market_data = True
settings.suppress_analyst_consensus = False

from app.services import room_runner  # noqa: E402

from build_profile import load_or_build  # noqa: E402
from mandates import battery_mandate  # noqa: E402
from vllm_client import VLLMClient  # noqa: E402

PORTFOLIO_VALUE = 10_000.0


def _pm_turn(run: dict) -> dict:
    for t in run["turns"]:
        if t["agent"] == "portfolio_manager":
            return t
    raise SystemExit("run.json has no portfolio_manager turn")


def _context(run: dict, profiles_dir: str):
    """Rebuild the `_RoomContext` the banked convene used for its PM parse.

    Only what `_parse_pm_verdict` reads matters: ticker, mandate (risk-tier size
    ceiling), the trader levels, and an empty option universe. The trader levels
    are re-derived the way `run_convene.py` derives them — from the SAME cached
    profile the convene loaded, so they are the same numbers.
    """
    mandate = battery_mandate(run["mandate_label"])
    profile = load_or_build(run["ticker"], profiles_dir=profiles_dir)
    base = profile.get("base_price") or 100.0
    return room_runner._RoomContext(
        ticker=run["ticker"],
        mandate=mandate,
        portfolio_value=PORTFOLIO_VALUE,
        current_drawdown_pct=0.0,
        halal_universe=set(),
        classification_universe=None,
        locale_allowed_universe=None,
        profile=profile,
        trader_size_pct=2.5,
        trader_entry=base,
        trader_stop=round(base * 0.9, 2),
        trader_target=round(base * 1.2, 2),
    )


def one_vote(
    client: VLLMClient,
    system: str,
    user: str,
    ctx,
    *,
    budget: int,
    samples: int,
    thinking: bool,
    reasoning_effort: str | None,
    temperature: float,
) -> dict:
    """One full production-mirroring vote: `samples` draws, voted production's way."""
    draws = []
    for _ in range(samples):
        d = client.chat(
            system, user,
            max_tokens=budget,
            temperature=temperature,
            thinking=thinking,
            reasoning_effort=reasoning_effort,
        )
        draws.append(d)

    parsed, per_draw = [], []
    for d in draws:
        truncated = d.get("finish") == "length"
        action = None
        if not d.get("error") and d.get("answer") and not truncated:
            _narr, verdict = room_runner._parse_pm_verdict(d["answer"], ctx)
            if verdict is not None:
                parsed.append((_narr, verdict))
                action = str(verdict.action)
        rec = {
            "error": d.get("error"),
            "finish": d.get("finish"),
            "truncated": truncated,
            "tok_prompt": d.get("tok_prompt"),
            "tok_out": d.get("tok_out"),
            "tok_reasoning": d.get("tok_reasoning"),
            "elapsed_s": d.get("elapsed_s"),
            "action": action,
            "answer_chars": len(d.get("answer") or ""),
        }
        # A draw that produced no action is the one a reader will want to SEE:
        # "unparseable" is a claim about text, and a summary that drops the text
        # cannot be checked. Parsed draws keep only their metrics — the answers
        # are k×n of them and the point of the replay is the distribution.
        if action is None:
            rec["answer"] = d.get("answer") or ""
        per_draw.append(rec)

    voted = room_runner._vote_pm_samples(parsed) if parsed else None
    verdict = json.loads(voted[1].model_dump_json()) if voted else None
    return {
        "action": str(voted[1].action) if voted else "NO_VERDICT",
        "size_pct": (verdict or {}).get("size_pct"),
        "agreement": voted[2] if voted else None,
        "draws_requested": samples,
        "draws_errored": sum(1 for d in per_draw if d["error"]),
        "draws_truncated": sum(1 for d in per_draw if d["truncated"]),
        "draws_parsed": len(parsed),
        "draw_actions": [d["action"] for d in per_draw],
        "reasoning_tokens": sum(d["tok_reasoning"] or 0 for d in per_draw),
        "out_tokens": sum(d["tok_out"] or 0 for d in per_draw),
        "elapsed_s": round(sum(d["elapsed_s"] or 0 for d in per_draw), 1),
        "verdict": verdict,
        "per_draw": per_draw,
    }


def replay(
    *,
    run_path: str,
    k: int,
    client: VLLMClient,
    profiles_dir: str = PROFILES,
    thinking: bool = False,
    reasoning_effort: str | None = None,
    max_tokens: int | None = None,
    samples: int | None = None,
    temperature: float = 1.0,
) -> dict:
    with open(run_path) as fh:
        run = json.load(fh)
    turn = _pm_turn(run)
    system, user = turn["system_prompt"], turn["user_message"]
    prod_budget = turn["max_tokens"]
    budget = max_tokens if max_tokens is not None else prod_budget
    n = samples if samples is not None else int(settings.pm_self_consistency_samples)
    ctx = _context(run, profiles_dir)
    identity = client.identity()

    print(
        f"{run['ticker']} × {run['mandate_label']}  k={k} votes × n={n} draws  "
        f"thinking={thinking} effort={reasoning_effort or '(default)'}  "
        f"max_tokens={budget} (production {prod_budget})  model={identity['root']}",
        flush=True,
    )

    votes = []
    for i in range(k):
        v = one_vote(
            client, system, user, ctx,
            budget=budget, samples=n, thinking=thinking,
            reasoning_effort=reasoning_effort, temperature=temperature,
        )
        votes.append(v)
        print(
            f"  vote {i + 1:>3}/{k}  {v['action']:<10} size={v['size_pct']} "
            f"agree={v['agreement']} parsed={v['draws_parsed']}/{n} "
            f"trunc={v['draws_truncated']} err={v['draws_errored']} "
            f"think={v['reasoning_tokens']} {v['elapsed_s']}s",
            flush=True,
        )

    return {
        "source_run": os.path.abspath(run_path),
        "ticker": run["ticker"],
        "mandate_label": run["mandate_label"],
        "model": identity,
        "k": k,
        "pm_samples": n,
        "thinking": thinking,
        "reasoning_effort": reasoning_effort,
        "max_tokens": budget,
        "production_max_tokens": prod_budget,
        "temperature": temperature,
        "pm_prompt_tokens_banked": turn.get("tok_prompt"),
        "ran_at": dt.datetime.now(dt.UTC).isoformat(),
        "votes": votes,
        "summary": summarise(votes),
    }


def summarise(votes: list[dict]) -> dict:
    """Flip rate, parse loss and truncation — the three R47/R48 numbers.

    `flip_rate` is against the MODAL outcome, not against the first vote: the
    first vote is one sample of the same distribution and anchoring on it would
    make the number depend on run order. Modal-outcome disagreement is the rate
    at which the shipped procedure lands somewhere other than its own centre.
    """
    actions = [v["action"] for v in votes]
    counts = Counter(actions)
    modal, modal_n = (counts.most_common(1)[0] if counts else (None, 0))
    k = len(votes)

    all_draw_actions = [a for v in votes for a in v["draw_actions"]]
    draws_total = sum(v["draws_requested"] for v in votes)
    draws_parsed = sum(v["draws_parsed"] for v in votes)
    draws_trunc = sum(v["draws_truncated"] for v in votes)
    draws_err = sum(v["draws_errored"] for v in votes)

    sizes = [v["size_pct"] for v in votes if v["size_pct"] is not None]
    reasoning = [v["reasoning_tokens"] for v in votes]
    out_toks = [v["out_tokens"] for v in votes]

    return {
        "votes": k,
        "outcome_counts": dict(counts),
        "modal_outcome": modal,
        "modal_count": modal_n,
        "flip_rate": round(1 - modal_n / k, 4) if k else None,
        "distinct_outcomes": len(counts),
        "size_pct_values": sorted(set(sizes)),
        "size_pct_median": round(statistics.median(sizes), 3) if sizes else None,
        "draws_requested": draws_total,
        "draws_parsed": draws_parsed,
        "draws_truncated": draws_trunc,
        "draws_errored": draws_err,
        "draw_parse_rate": round(draws_parsed / draws_total, 4) if draws_total else None,
        "draw_parse_loss_rate": (
            round(1 - draws_parsed / draws_total, 4) if draws_total else None
        ),
        "draw_action_counts": dict(Counter(a for a in all_draw_actions if a)),
        "reasoning_tokens_total": sum(reasoning),
        "reasoning_tokens_per_vote_mean": (
            round(statistics.mean(reasoning), 1) if reasoning else None
        ),
        "out_tokens_per_vote_mean": (
            round(statistics.mean(out_toks), 1) if out_toks else None
        ),
        "elapsed_s_total": round(sum(v["elapsed_s"] for v in votes), 1),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", required=True, help="path to a banked convene run.json")
    ap.add_argument("--k", type=int, default=20, help="how many full votes to replay")
    ap.add_argument("--label", required=True, help="output filename stem under results/")
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--profiles-dir", default=PROFILES)
    ap.add_argument("--out-root", default=RESULTS)
    ap.add_argument("--thinking", action="store_true")
    ap.add_argument("--reasoning-effort", default=None,
                    choices=["xhigh", "medium", "low"])
    ap.add_argument("--max-tokens", type=int, default=None,
                    help="per-request override; production budget when omitted")
    ap.add_argument("--pm-samples", type=int, default=None)
    ap.add_argument("--temperature", type=float, default=1.0)
    args = ap.parse_args()

    kw = {"base_url": args.base_url} if args.base_url else {}
    out = replay(
        run_path=args.run,
        k=args.k,
        client=VLLMClient(**kw),
        profiles_dir=args.profiles_dir,
        thinking=args.thinking,
        reasoning_effort=args.reasoning_effort,
        max_tokens=args.max_tokens,
        samples=args.pm_samples,
        temperature=args.temperature,
    )

    os.makedirs(args.out_root, exist_ok=True)
    dest = os.path.join(args.out_root, f"{args.label}.json")
    with open(dest, "w") as fh:
        json.dump(out, fh, indent=1)
    print()
    print(json.dumps(out["summary"], indent=1))
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
