"""Run a LIST of tickers, one full 12-agent Room convene each, at a fixed
mandate. V2 replacement for v1
`docs/tools/room_investigation/room_ticker_batch.py` — the tool for when the
axis under test is TICKER (e.g. CR240's "does DeepInfra/GLM-5.3-Flash reach
the same verdicts as Kimi on the tickers Kimi approved").

The v1 landmines are structural in v2, handled inside `library/runner.py`:
per-arm deterministic uuid5 user ids (the SimEngine.ensure_portfolio race is
impossible by construction, not convention), locked JSONL appends, and resume
on status=="completed" — re-run with the same --batch-id/--out-dir to pick up
where an interrupted batch left off.

`--prompt-variant` names ONE prompt variant for the whole batch (default
`backend-default`); runner.run_arms enforces the one-variant-per-batch rule
because prompt_lab's override is process-wide while arms convene concurrently.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from library import env_bootstrap, prompt_lab, provider_gateway, runner  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a list of tickers, one full Room convene each, fixed mandate.",
    )
    parser.add_argument("--tickers-file", type=Path, required=True,
                        help="one ticker per line; blank lines and # comments are ignored")
    parser.add_argument("--risk-score", type=int, default=3)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--fresh-user", action="store_true",
                        help="mint a new batch base user even if one exists for --batch-id")
    parser.add_argument("--prompt-variant", default=prompt_lab.BACKEND_DEFAULT_VARIANT,
                        help="ONE prompt variant for the whole batch (runner enforces); "
                        "'backend-default' = no overrides")
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

    tickers = [
        t.strip().upper()
        for t in args.tickers_file.read_text().splitlines()
        if t.strip() and not t.strip().startswith("#")
    ]
    arms = [
        runner.Arm(
            key=ticker,
            ticker=ticker,
            mandate=runner.base_mandate(
                risk_score=args.risk_score,
                display_name=f"{args.batch_id} R{args.risk_score} ({args.provider})",
            ),
            label=args.batch_id,
            prompt_variant=args.prompt_variant,
        )
        for ticker in tickers
    ]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"runs_{args.batch_id}.jsonl"
    summary = await runner.run_arms(
        arms,
        batch_id=args.batch_id,
        out_path=out_path,
        benchmarks_dir=Path(__file__).resolve().parents[1] / "benchmarks",
        gateway=gateway,
        max_concurrent=args.max_concurrent,
        post_spacing_s=args.post_spacing,
        fresh_user=args.fresh_user,
    )

    failures = [r.arm.ticker for r in summary.results if r.status != "completed"]
    if failures:
        print(f"failures ({len(failures)}): {', '.join(failures)} — re-run with the same --batch-id to retry")
    return 1 if failures else 0


def main() -> int:
    return asyncio.run(main_async(build_parser().parse_args()))


if __name__ == "__main__":
    sys.exit(main())
