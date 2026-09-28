"""Run a named benchmark definition through `library/runner.py` and score it
with `library/scoring.py` — the CR247 phase-gate instrument (DESIGN.md §5).

A benchmark is a versioned YAML file in `benchmarks/` naming the provider,
the fixed ticker set, the mandate (a `risk_score` block or a mandate-file
reference), the repeat count, and the prompt variant. Arms are the cross
product tickers x repeats with deterministic keys `{ticker}-rep{i}`, so a
benchmark re-run resumes on ``status == "completed"`` per arm.

CR247 Phase 0 consumes this directly: Phase 0.2 runs the baseline benchmark
(pinned to the CURRENT serving model, verified via /v1/models `root`, never
the `ami-llm` alias — D21) BEFORE any prompt change; phases 1-5 swap
`prompt_variant` in a copy of the file and `scoring.diff_batches` (via
--diff-against) decides pass/fail at the gate. Scores are computed in code —
LLMs never compute scores (house rule).

YAML only: pyyaml is already in backend/.venv; nothing else is parsed.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from library import env_bootstrap, prompt_lab, provider_gateway, runner, scoring  # noqa: E402

V2_ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS_DIR = V2_ROOT / "benchmarks"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a versioned benchmark file through the Room and score it.",
    )
    parser.add_argument("--benchmark", required=True,
                        help="path to a benchmark YAML, or a bare name resolved under benchmarks/")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--provider", choices=sorted(provider_gateway.PROVIDERS), default=None,
                        help="override the benchmark file's provider")
    parser.add_argument("--model", default=None, help="provider model override (default: the provider's registered default)")
    parser.add_argument("--max-concurrent", type=int, default=3,
                        help="max Room convenes in flight at once; 1 = strictly sequential")
    parser.add_argument("--repeats", type=int, default=None,
                        help="override the benchmark file's repeat count")
    parser.add_argument("--diff-against", type=Path, default=None,
                        help="baseline run JSONL to diff this run's output against (scoring.diff_batches)")
    parser.add_argument("--allow-mock-market-data", action="store_true",
                        help="skip the USE_REAL_MARKET_DATA guard (deliberate mock-data runs only)")
    return parser


def _resolve_benchmark_path(value: str) -> Path:
    path = Path(value)
    if path.is_file():
        return path
    for candidate in (BENCHMARKS_DIR / value, BENCHMARKS_DIR / f"{value}.yaml", BENCHMARKS_DIR / f"{value}.yml"):
        if candidate.is_file():
            return candidate
    raise SystemExit(
        f"benchmark {value!r} not found — pass a path, or a name that resolves under {BENCHMARKS_DIR}"
    )


def _resolve_mandate(spec: dict, *, benchmark_path: Path) -> dict:
    if "file" in spec:
        path = Path(spec["file"])
        if not path.is_absolute():
            path = benchmark_path.parent / path
        print(f"Using mandate snapshot from {path}")
        return json.loads(path.read_text())
    if "risk_score" in spec:
        return runner.base_mandate(risk_score=int(spec["risk_score"]))
    raise SystemExit(
        f"benchmark mandate block must carry 'risk_score' or 'file', got: {sorted(spec)}"
    )


async def main_async(args: argparse.Namespace) -> int:
    env_bootstrap.ensure_backend_path()
    env_bootstrap.load_repo_env()
    env_bootstrap.require_database_url()
    env_bootstrap.require_real_market_data(allow_mock=args.allow_mock_market_data)

    benchmark_path = _resolve_benchmark_path(args.benchmark)
    bench = yaml.safe_load(benchmark_path.read_text())
    if not isinstance(bench, dict):
        raise SystemExit(f"{benchmark_path} did not parse to a mapping")

    name = bench["name"]
    provider = args.provider or bench["provider"]
    tickers = [str(t).upper() for t in bench["tickers"]]
    repeats = args.repeats if args.repeats is not None else int(bench.get("repeats", 5))
    prompt_variant = bench.get("prompt_variant", prompt_lab.BACKEND_DEFAULT_VARIANT)
    mandate = _resolve_mandate(bench.get("mandate") or {}, benchmark_path=benchmark_path)

    gateway = provider_gateway.force_provider(provider, model=args.model)

    arms = [
        runner.Arm(
            key=f"{ticker}-rep{i}",
            ticker=ticker,
            mandate=mandate,
            label=name,
            prompt_variant=prompt_variant,
        )
        for ticker in tickers
        for i in range(1, repeats + 1)
    ]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"runs_{name}.jsonl"
    print(f"benchmark: {name} ({benchmark_path}) — {len(tickers)} tickers x {repeats} repeats, "
          f"provider={provider}, prompt_variant={prompt_variant}")
    summary = await runner.run_arms(
        arms,
        batch_id=name,
        out_path=out_path,
        benchmarks_dir=BENCHMARKS_DIR,
        gateway=gateway,
        max_concurrent=args.max_concurrent,
    )

    records = [
        {
            "ticker": r.arm.ticker,
            "risk_score": r.arm.mandate.get("risk_score"),
            "status": r.status,
            "verdict": r.verdict,
        }
        for r in summary.results
    ]
    print(f"\nstability report (this run, threshold {scoring.DEFAULT_MIN_AGREEMENT:.2f}):")
    for row in scoring.stability_report(records):
        mark = "stable" if row.stable else "UNSTABLE"
        print(
            f"  {'/'.join(map(str, row.group))}: n={row.n} top={row.top_action} "
            f"agreement={row.agreement:.2f} {mark} dist={dict(row.actions)}"
        )

    if args.diff_against:
        print()
        print(scoring.diff_batches(args.diff_against, out_path))

    return 1 if summary.failed else 0


def main() -> int:
    return asyncio.run(main_async(build_parser().parse_args()))


if __name__ == "__main__":
    sys.exit(main())
