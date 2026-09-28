"""Run ONE ticker across a set of risk_score mandate values — one full
12-agent Room convene per score — and end with the risk_score/action/votes
table. V2 replacement for v1
`docs/tools/room_investigation/room_risk_score_sweep.py`: one arm per risk
score through `library/runner.py`'s `run_arms` (deterministic uuid5 user ids,
locked JSONL appends, resume on completed).

Use this to answer: "does changing risk_score actually change this Room's
verdict for this ticker, right now?" CR228's findings this generalizes: AAPL
was a unanimous 0/5 PASS at every risk_score 1-5 (no threshold effect); BAC
was APPROVE at 1/3/4/5 and PASS at 2 — later traced (via replay + audit
trace) to the live news feed refreshing between draws, not model instability.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from library import env_bootstrap, provider_gateway, runner  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sweep one ticker across risk_score values, one full Room convene each.",
    )
    parser.add_argument("--ticker", required=True, help="e.g. AAPL")
    parser.add_argument("--risk-scores", default="1,2,3,4,5", help="comma-separated, e.g. 1,2,4,5")
    parser.add_argument("--tag", default=None, help="filename tag, e.g. a date stamp (defaults to the provider name)")
    parser.add_argument("--post-spacing", type=float, default=15.0,
                        help="seconds to hold a concurrency slot open after an arm finishes")
    parser.add_argument("--max-concurrent", type=int, default=3,
                        help="max Room convenes in flight at once; 1 = strictly sequential")
    parser.add_argument("--allow-mock-market-data", action="store_true",
                        help="skip the USE_REAL_MARKET_DATA guard (deliberate mock-data runs only)")
    parser.add_argument("--provider", choices=sorted(provider_gateway.PROVIDERS), default="kimi")
    parser.add_argument("--model", default=None, help="provider model override (default: the provider's registered default)")
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser


async def main_async(args: argparse.Namespace) -> int:
    env_bootstrap.ensure_backend_path()
    env_bootstrap.load_repo_env()
    env_bootstrap.require_database_url()
    env_bootstrap.require_real_market_data(allow_mock=args.allow_mock_market_data)
    gateway = provider_gateway.force_provider(args.provider, model=args.model)

    risk_scores = [int(x) for x in args.risk_scores.split(",")]
    arms = [
        runner.Arm(
            key=f"{args.ticker}-r{score}",
            ticker=args.ticker,
            mandate=runner.base_mandate(
                risk_score=score,
                display_name=f"{args.tag} R{score} sweep ({args.ticker})",
            ),
            label=args.tag,
        )
        for score in risk_scores
    ]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"{args.ticker.lower()}_risk_sweep_{args.tag}.jsonl"
    summary = await runner.run_arms(
        arms,
        batch_id=out_path.stem,
        out_path=out_path,
        benchmarks_dir=Path(__file__).resolve().parents[1] / "benchmarks",
        gateway=gateway,
        max_concurrent=args.max_concurrent,
        post_spacing_s=args.post_spacing,
    )

    by_score = {r.arm.mandate.get("risk_score"): r for r in summary.results}
    print(f"\n{'risk_score':>10s}  {'action':8s}  votes")
    for score in risk_scores:
        r = by_score.get(score)
        if r is None:
            print(f"{score:>10d}  {'(resumed)':8s}  -")
            continue
        v = r.verdict or {}
        action = v.get("action") if r.status == "completed" else r.status
        print(f"{score:>10d}  {str(action):8s}  {v.get('approve_votes')}/{v.get('samples')}")
    return 1 if summary.failed else 0


def main() -> int:
    args = build_parser().parse_args()
    if args.tag is None:
        args.tag = args.provider
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
