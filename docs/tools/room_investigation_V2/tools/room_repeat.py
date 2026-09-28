"""Run ONE ticker + ONE risk_score N times — full 12-agent Room convenes — and
report the action distribution and stability. V2 replacement for v1
`docs/tools/room_investigation/room_repeat_consistency.py`: the run loop is
`library/runner.py`'s `run_arms` (deterministic uuid5 user ids, locked JSONL
appends, resume on completed), the mandate is `runner.base_mandate` or a
verbatim `--mandate-file` snapshot, and the distribution/stability numbers are
computed by `library/scoring.py` — never by an LLM.

Use this to answer: "is this ticker/risk_score's verdict a stable, repeatable
result, or did I just see one draw of an unstable distribution?" — the FIRST
thing to run whenever a single Room draw looks surprising (RES009 / CR228: the
risk_score=2 BAC single PASS turned out to be 1 of 6 draws).

`--mandate-file` reproduces a real user's exact `mandates.snapshot` JSON
verbatim; when given, `--risk-score` is only a label for the output filename
and log lines (v1's behavior, kept).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from library import env_bootstrap, provider_gateway, runner, scoring  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Repeat one ticker+risk_score N times, report the action "
        "distribution and stability.",
    )
    parser.add_argument("--ticker", required=True)
    parser.add_argument(
        "--risk-score", type=int, required=True,
        help="drives the synthetic mandate AND the output filename; with "
        "--mandate-file it is only a label — the mandate content sent to the "
        "Room comes entirely from the file",
    )
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--mandate-file", type=Path, default=None,
        help="JSON mandate snapshot (e.g. a real user's mandates.snapshot "
        "column) to use verbatim instead of the synthetic base_mandate()",
    )
    parser.add_argument("--tag", default=None, help="filename tag (defaults to the provider name)")
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


def _records_from(summary: runner.RunSummary) -> list[dict]:
    return [
        {
            "ticker": r.arm.ticker,
            "risk_score": r.arm.mandate.get("risk_score"),
            "status": r.status,
            "verdict": r.verdict,
        }
        for r in summary.results
    ]


async def main_async(args: argparse.Namespace) -> int:
    env_bootstrap.ensure_backend_path()
    env_bootstrap.load_repo_env()
    env_bootstrap.require_database_url()
    env_bootstrap.require_real_market_data(allow_mock=args.allow_mock_market_data)
    gateway = provider_gateway.force_provider(args.provider, model=args.model)

    if args.mandate_file:
        mandate = json.loads(args.mandate_file.read_text())
        print(
            f"Using mandate snapshot from {args.mandate_file} "
            f"(risk_score={mandate.get('risk_score')}, "
            f"single_name_cap_pct={mandate.get('single_name_cap_pct')}, "
            f"sector_cap_pct={mandate.get('sector_cap_pct')}, "
            f"max_drawdown_pct={mandate.get('max_drawdown_pct')}) — "
            f"--risk-score {args.risk_score} is a label only"
        )
    else:
        mandate = runner.base_mandate(
            risk_score=args.risk_score,
            display_name=f"{args.tag} R{args.risk_score} repeat ({args.ticker})",
        )

    arms = [
        runner.Arm(
            key=f"{args.ticker}-r{args.risk_score}-{i}",
            ticker=args.ticker,
            mandate=mandate,
            label=args.tag,
        )
        for i in range(1, args.repeats + 1)
    ]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"{args.ticker.lower()}_repeat_r{args.risk_score}_{args.tag}.jsonl"
    summary = await runner.run_arms(
        arms,
        batch_id=out_path.stem,
        out_path=out_path,
        benchmarks_dir=Path(__file__).resolve().parents[1] / "benchmarks",
        gateway=gateway,
        max_concurrent=args.max_concurrent,
        post_spacing_s=args.post_spacing,
    )

    records = _records_from(summary)
    print(f"\naction distribution: "
          f"{ { '/'.join(map(str, group)): dict(actions) for group, actions in scoring.verdict_distribution(records).items() } }")
    for row in scoring.stability_report(records):
        mark = "stable" if row.stable else "UNSTABLE"
        print(
            f"stability: {'/'.join(map(str, row.group))} n={row.n} "
            f"top={row.top_action} agreement={row.agreement:.2f} {mark} "
            f"(threshold {scoring.DEFAULT_MIN_AGREEMENT:.2f})"
        )
    return 1 if summary.failed else 0


def main() -> int:
    args = build_parser().parse_args()
    if args.tag is None:
        args.tag = args.provider
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
