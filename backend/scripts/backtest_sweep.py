"""CR164 backtest sweep driver — run one Room backtest batch against a live
backend via the admin as-of endpoint, one JSONL record per (ticker, as_of).

Factored from `scripts/room_benchmark.py` (CR035): the batch-user machinery
(mint anon user, admin plan PATCH, top-up-on-402, poll-to-terminal, resumable
JSONL) is IMPORTED from that module unchanged — its functions are importable
without running its CLI, so no shared-helper split was needed and
room_benchmark's own CLI is untouched.

What is new here is the pair plan: instead of "every ticker, today", the
sweep samples N (ticker, Friday-as_of) pairs deterministically from --seed,
stratified so each selected Friday carries roughly equal tickers, and starts
each pair through `POST /v1/admin/backtest/room-run` (backtest_admin.py).
Server responses drive the loop: 202 → poll `GET /v1/room/{run_id}` to
terminal; 409 → the (batch, ticker, as_of) pair is already indexed server-side
(the `uq_backtest_run` idempotency gate), log and skip; 402 → CR039 credit
gate, top up once and retry.

Leakage guard (c): --window-start is REQUIRED and is the model-cutoff probe's
window_start. Any generated as_of before it aborts the sweep. There is
deliberately NO override flag — the refusal is code, not convention (CR164).

Noise floor: --repeat-pairs N re-runs N already-planned pairs a second time
under batch-id `<batch-id>-repeat` (their records land in
`runs_<batch-id>-repeat.jsonl`), giving the report an in-sweep re-measurement
of verdict instability on identical inputs.

Resumable and interrupt-safe: one JSONL line is appended after each pair; on
restart, pairs whose latest record is completed (or already_indexed) are
skipped, and the server's 409 is the backstop for anything the file missed.

Usage (inside the ami_api_alpha container, from backend/):
    .venv/bin/python scripts/backtest_sweep.py --batch-id pit-pilot-1 \
        --window-start 2026-03-06 --n-pairs 130 --seed 164
    # dry plan check, no network:
    .venv/bin/python scripts/backtest_sweep.py --batch-id x --plan-only \
        --window-start 2026-03-06 --n-pairs 130 --seed 164

ADMIN_SECRET follows room_benchmark's convention: --admin-secret beats the
env var, which beats infra/alpha.env.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.room_benchmark import (  # noqa: E402
    NEUTRAL_MANDATE_OVERRIDE,
    POST_SPACING_S,
    _admin_secret,
    _now_iso,
    append_jsonl,
    grant_credits,
    load_or_create_batch_user,
    poll_run,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE = "http://localhost:8000"
DEFAULT_UNIVERSE = REPO_ROOT / "docs/forward_planning/CR035_room_benchmark/tickers_150.txt"
DEFAULT_OUT_DIR = REPO_ROOT / "docs/forward_planning/CR164_room_backtest/results"

SKIP_STATUSES = {"completed", "already_indexed"}


def parse_universe(path: Path) -> list[str]:
    if not path.exists():
        raise SystemExit(f"universe file not found: {path}")
    tickers = [
        t.strip().upper()
        for t in path.read_text().splitlines()
        if t.strip() and not t.strip().startswith("#")
    ]
    if not tickers:
        raise SystemExit(f"universe file has no tickers: {path}")
    return tickers


def fridays_between(start: date, end: date) -> list[date]:
    first = start + timedelta(days=(4 - start.weekday()) % 7)
    out = []
    d = first
    while d <= end:
        out.append(d)
        d += timedelta(days=7)
    return out


def generate_pairs(
    tickers: list[str], fridays: list[date], n_pairs: int, rng: random.Random,
) -> tuple[list[tuple[str, date]], dict[date, int]]:
    """Deterministic stratified sample of n_pairs (ticker, friday) pairs.

    Each Friday gets floor(n/|fridays|) tickers; the remainder is spread over
    a seeded shuffle of the Fridays. Within a Friday, tickers are a seeded
    shuffle prefix — no (ticker, friday) pair can repeat.
    """
    base, rem = divmod(n_pairs, len(fridays))
    extras_order = list(fridays)
    rng.shuffle(extras_order)
    extra = set(extras_order[:rem])
    quotas = {f: base + (1 if f in extra else 0) for f in fridays}
    if max(quotas.values()) > len(tickers):
        raise SystemExit(
            f"n-pairs {n_pairs} needs {max(quotas.values())} tickers on some "
            f"Friday but the universe has only {len(tickers)} — widen the "
            f"window or shrink n-pairs"
        )
    pairs: list[tuple[str, date]] = []
    for f in fridays:
        if quotas[f] == 0:
            continue
        pool = list(tickers)
        rng.shuffle(pool)
        pairs.extend((t, f) for t in pool[: quotas[f]])
    rng.shuffle(pairs)
    return pairs, quotas


def load_latest_pair_records(runs_path: Path) -> dict[tuple[str, str], dict]:
    """(ticker, as_of) → latest record in this append-only JSONL."""
    latest: dict[tuple[str, str], dict] = {}
    if runs_path.exists():
        for line in runs_path.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                latest[(rec["ticker"], rec["as_of"])] = rec
    return latest


def start_backtest_run(
    client: httpx.Client, base: str, secret: str, body: dict,
) -> httpx.Response:
    return client.post(
        f"{base}/v1/admin/backtest/room-run",
        json=body,
        headers={"Authorization": f"Bearer {secret}"},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="CR164 Room backtest sweep driver.")
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--admin-secret", default=None,
                        help="Beats the ADMIN_SECRET env var / infra/alpha.env fallback.")
    parser.add_argument("--universe-file", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--window-start", required=True, type=date.fromisoformat,
                        help="Model-cutoff probe window_start (ISO). Any generated "
                             "as_of before it aborts. No override flag exists.")
    parser.add_argument("--window-end", type=date.fromisoformat, default=None,
                        help="Default: today - 35 days (room for the +20-trading-day "
                             "scoring horizon to have realized).")
    parser.add_argument("--n-pairs", required=True, type=int)
    parser.add_argument("--repeat-pairs", type=int, default=0,
                        help="Pairs re-run under <batch-id>-repeat for the noise floor.")
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--arm", default="pit_v1")
    parser.add_argument("--plan", default="trader",
                        choices=["floor_pass", "trader", "floor_manager", "trial_trader"])
    parser.add_argument("--credit-grant", type=int, default=2000,
                        help="Credits granted on a 402 (CR039 metering), like room_benchmark.")
    parser.add_argument("--mandate-json", default=None,
                        help="JSON mandate_override replacing room_benchmark's pinned "
                             "NEUTRAL_MANDATE_OVERRIDE.")
    parser.add_argument("--poll-interval", type=float, default=20.0)
    parser.add_argument("--run-timeout", type=float, default=1500.0)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--plan-only", action="store_true",
                        help="Print the deterministic pair plan and exit; no network.")
    args = parser.parse_args()

    window_end = args.window_end or (date.today() - timedelta(days=35))
    if window_end < args.window_start:
        raise SystemExit(
            f"window-end {window_end} is before window-start {args.window_start}"
        )
    if args.n_pairs <= 0:
        raise SystemExit("--n-pairs must be positive")
    if args.repeat_pairs < 0:
        raise SystemExit("--repeat-pairs must be >= 0")

    tickers = parse_universe(args.universe_file)
    fridays = fridays_between(args.window_start, window_end)
    if not fridays:
        raise SystemExit(
            f"no Fridays in [{args.window_start}, {window_end}] — nothing to sweep"
        )

    rng = random.Random(args.seed)
    pairs, quotas = generate_pairs(tickers, fridays, args.n_pairs, rng)
    if args.repeat_pairs > len(pairs):
        raise SystemExit(
            f"--repeat-pairs {args.repeat_pairs} exceeds the {len(pairs)} planned pairs"
        )
    repeats = rng.sample(pairs, args.repeat_pairs) if args.repeat_pairs else []

    # Leakage guard (c): structural refusal, not convention. The generator can
    # only emit Fridays >= window-start, but this check survives any future
    # refactor of the generator.
    early = [(t, f) for t, f in pairs + repeats if f < args.window_start]
    if early:
        raise SystemExit(f"generated as_of before window-start: {early[:5]} — refusing")

    used_dates = sorted({f for _, f in pairs})
    print(
        f"plan: batch={args.batch_id} arm={args.arm} seed={args.seed} "
        f"window=[{args.window_start}..{window_end}]"
    )
    print(
        f"  {len(pairs)} pairs over {len(used_dates)}/{len(fridays)} Fridays, "
        f"{len({t for t, _ in pairs})}/{len(tickers)} tickers, "
        f"{len(repeats)} repeat pairs"
    )
    for f in used_dates:
        print(f"  {f}: {quotas[f]} tickers")
    if args.plan_only:
        for i, (t, f) in enumerate(pairs, 1):
            print(f"  [{i:4d}] {f} {t}")
        for i, (t, f) in enumerate(repeats, 1):
            print(f"  [repeat {i:4d}] {f} {t}")
        return 0

    secret = args.admin_secret or _admin_secret()
    # room_benchmark's set_plan/grant_credits read ADMIN_SECRET from the env
    # themselves; export the resolved secret so a --admin-secret flag reaches them.
    os.environ["ADMIN_SECRET"] = secret

    mandate_override = (
        json.loads(args.mandate_json) if args.mandate_json else NEUTRAL_MANDATE_OVERRIDE
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    runs_paths = {
        args.batch_id: args.out_dir / f"runs_{args.batch_id}.jsonl",
        f"{args.batch_id}-repeat": args.out_dir / f"runs_{args.batch_id}-repeat.jsonl",
    }
    latest = {
        bid: load_latest_pair_records(path) for bid, path in runs_paths.items()
    }

    client = httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))
    health = client.get(f"{args.base_url}/v1/health")
    health.raise_for_status()
    print(f"backend ok: {health.json()}")

    user = load_or_create_batch_user(
        args.out_dir, client, args.base_url, args.batch_id, args.plan, fresh=False,
    )
    print(f"batch user: {user['user_id']} (plan={user['plan']})")

    work = [(args.batch_id, t, f) for t, f in pairs] + [
        (f"{args.batch_id}-repeat", t, f) for t, f in repeats
    ]
    failures: list[str] = []
    done = 0
    try:
        for i, (batch_id, ticker, as_of) in enumerate(work, 1):
            as_of_iso = as_of.isoformat()
            prior = latest[batch_id].get((ticker, as_of_iso))
            if prior and prior.get("status") in SKIP_STATUSES:
                print(f"[{i}/{len(work)}] {ticker}@{as_of_iso} ({batch_id}): "
                      f"{prior['status']}, skip")
                continue
            print(f"[{i}/{len(work)}] {ticker}@{as_of_iso} ({batch_id}): starting…",
                  flush=True)
            record = {
                "batch_id": batch_id,
                "arm": args.arm,
                "ticker": ticker,
                "as_of": as_of_iso,
                "user_id": user["user_id"],
                "run_id": None,
                "status": None,
                "verdict": None,
                "duration_ms": None,
                "finished_at": None,
                "error_message": None,
            }
            body = {
                "user_id": user["user_id"],
                "ticker": ticker,
                "as_of": as_of_iso,
                "batch_id": batch_id,
                "arm": args.arm,
                "mandate_override": mandate_override,
                "locale": "en",
            }
            try:
                resp = start_backtest_run(client, args.base_url, secret, body)
                if resp.status_code == 402:
                    balance = grant_credits(
                        client, args.base_url, user["user_id"], args.credit_grant,
                    )
                    print(f"    402 insufficient credits — granted "
                          f"{args.credit_grant}, balance now {balance}", flush=True)
                    resp = start_backtest_run(client, args.base_url, secret, body)
                if resp.status_code == 409:
                    print(f"    409 already indexed server-side — skip", flush=True)
                    record.update(status="already_indexed",
                                  error_message=resp.text[:300])
                else:
                    resp.raise_for_status()
                    run_id = resp.json()["run_id"]
                    run = poll_run(
                        client, args.base_url, user["token"], run_id,
                        args.poll_interval, args.run_timeout,
                    )
                    record.update(
                        run_id=run_id,
                        status=run.get("status"),
                        verdict=run.get("verdict"),
                        duration_ms=run.get("duration_ms"),
                        error_message=run.get("error_message"),
                    )
            except Exception as exc:  # noqa: BLE001 — record and continue the batch
                record.update(status="script_error", error_message=repr(exc)[:300])
            record["finished_at"] = _now_iso()
            append_jsonl(runs_paths[batch_id], record)
            latest[batch_id][(ticker, as_of_iso)] = record
            verdict = record.get("verdict") or {}
            print(f"    → {record.get('status')} action={verdict.get('action')}",
                  flush=True)
            if record.get("status") == "completed":
                done += 1
            elif record.get("status") != "already_indexed":
                failures.append(f"{ticker}@{as_of_iso}")
            time.sleep(POST_SPACING_S)
    except KeyboardInterrupt:
        print("\ninterrupted — every finished pair is already on disk.")
        print("resume with the SAME command (same --batch-id/--seed/--window-*/"
              "--n-pairs): completed pairs are skipped from the JSONL, and the "
              "server 409s anything the file missed.")
        return 130

    print(f"\ndone: {done} completed, {len(failures)} failed "
          f"→ {runs_paths[args.batch_id]}")
    if failures:
        print(f"failures ({len(failures)}): {', '.join(failures)}")
        print("NOTE: a failed pair is already indexed server-side (409 on retry) — "
              "score what completed, or use a new batch-id for the gaps.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
