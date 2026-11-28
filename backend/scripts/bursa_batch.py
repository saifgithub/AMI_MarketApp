"""CR282 Bursa batch step 3 — convene one Room per sampled Bursa ticker against Alpha.

Reuses the CR035 benchmark plumbing (`scripts.room_benchmark`): the same anonymous
benchmark user (minted with `app_version="room-benchmark"`, which is what every
real-user count already excludes), the same admin plan patch, the same
top-up-on-402 credit path (`POST /v1/admin/users/{id}/credits`; see
`room_benchmark.grant_credits` for why a top-up cannot be done up-front), the same
detached stream-POST + poll. What is new here:

- Mandate: `BURSA_MANDATE_OVERRIDE` — risk score 5, every compliance filter off
  (`liquid_only` included), sent as the Room request's `mandate_override`, exactly
  as CR035 does. `long_only` stays at its schema default (True): the Room only
  ever opens buys and Bursa has no short selling, so it blocks nothing here.
- One run per ticker, recorded in `runs_<batch>.jsonl` (append-only; the latest
  record per ticker wins). Resume skips `completed` and `permanent_failure`
  records; `failed_after_retries` and `script_error` are re-tried on the next run
  (`--retry-permanent` also re-tries permanent failures).
- Transient trouble (transport errors, 408/429/5xx, 409 room-in-session, a Room
  that ends `failed`/`cancelled`/times out) is retried with backoff, every attempt
  logged on the record. A permanent failure (other 4xx: unknown ticker, auth) is
  recorded as `permanent_failure` with the server's reason. Nothing is dropped.
- Concurrency: default 1, the CR035 default. The Room refuses a second concurrent
  Room for the same user (409), so `--concurrency K` mints K benchmark users
  (`<batch>`, `<batch>#w1`, ...), one per worker. Capped at 4.
- `--dry-run` prints the plan and touches nothing: no network, no user, no file.

Runs on melehost inside `ami_api_alpha` against `http://localhost:8000` (CR035's ops
lesson: a Mac-side driver loses runs to local network blips).

Usage (from backend/):
    .venv/bin/python -m scripts.bursa_batch <sample.csv> --batch-id bursa282-2026-11-25 --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from scripts import room_benchmark as rb

REPO_ROOT = rb.REPO_ROOT
DEFAULT_OUT_DIR = REPO_ROOT / "docs/forward_planning/CR282_bursa_malaysia/bursa_batch"
DEFAULT_BASE = rb.DEFAULT_BASE

NOTE = "CR282 bursa batch user"
CREDIT_NOTE = "CR282 bursa batch top-up (metered by CR039)"
BASIC_ROOM_CREDITS = 8  # CR035 docstring: "a Basic Room costs 8" at the trader plan.

BURSA_MANDATE_OVERRIDE = {
    **rb.NEUTRAL_MANDATE_OVERRIDE,
    "display_name": "Benchmark",
    "risk_score": 5,
    "compliance": {
        "halal": False,
        "esg_lite": False,
        "no_tobacco_alcohol_gambling": False,
        "no_fossil_fuels": False,
        "liquid_only": False,
        "derivatives_allowed": False,
        "ticker_blocklist": [],
        "ticker_allowlist": None,
        "custom_constraints": [],
    },
}

DONE_STATUSES = {"completed", "permanent_failure"}
TRANSIENT_HTTP = {408, 409, 425, 429, 500, 502, 503, 504}
MAX_CONCURRENCY = 4
_io_lock = threading.Lock()


def load_tickers(path: Path) -> list[str]:
    """Symbols from a sample CSV (`symbol` column) or a plain one-per-line file."""
    text = path.read_text()
    if path.suffix.lower() == ".csv":
        return [r["symbol"].strip().upper() for r in csv.DictReader(text.splitlines()) if r.get("symbol")]
    return [
        t.strip().upper() for t in text.splitlines() if t.strip() and not t.strip().startswith("#")
    ]


def pending_tickers(
    tickers: list[str], latest: dict[str, dict], retry_permanent: bool,
) -> tuple[list[str], dict[str, int]]:
    """Tickers still to run, plus counts of what was skipped and why."""
    todo: list[str] = []
    skipped = {"completed": 0, "permanent_failure": 0}
    seen: set[str] = set()
    for t in tickers:
        if t in seen:
            continue
        seen.add(t)
        status = (latest.get(t) or {}).get("status")
        if status == "completed" or (status == "permanent_failure" and not retry_permanent):
            skipped[status] += 1
            continue
        todo.append(t)
    return todo, skipped


def classify_error(exc: BaseException) -> tuple[str, str]:
    """('transient' | 'permanent', reason). 402 is handled before this is reached."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        try:
            body = exc.response.text[:300]
        except Exception:  # noqa: BLE001
            body = ""
        kind = "transient" if code in TRANSIENT_HTTP else "permanent"
        return kind, f"HTTP {code}: {body}"
    if isinstance(exc, (httpx.TransportError, TimeoutError)):
        return "transient", f"{type(exc).__name__}: {str(exc)[:200]}"
    return "transient", f"{type(exc).__name__}: {str(exc)[:200]}"


def convene(
    client: httpx.Client, base: str, token: str, user_id: str, ticker: str,
    mandate_override: dict,
) -> tuple[str, bool, bool]:
    """POST /v1/room/stream, return (run_id, cached, banked) from the headers."""
    with client.stream(
        "POST", f"{base}/v1/room/stream",
        json={"user_id": user_id, "ticker": ticker,
              "mandate_override": mandate_override, "locale": "en"},
        headers={"Authorization": f"Bearer {token}"},
    ) as resp:
        resp.raise_for_status()
        run_id = resp.headers["X-Room-Run-Id"]
        cached = resp.headers.get("X-Room-Cached", "").lower() == "true"
        banked = resp.headers.get("X-Room-Banked", "").lower() == "true"
    return run_id, cached, banked


def run_ticker(
    client: httpx.Client, args, user: dict, ticker: str, mandate: dict,
    sleep=time.sleep,
) -> dict:
    """One ticker, with retries. Returns the record to append; never raises."""
    record: dict = {
        "batch_id": args.batch_id, "ticker": ticker, "user_id": user["user_id"],
        "risk_score": mandate.get("risk_score"), "triggered_at": rb._now_iso(),
        "attempts": [],
    }
    final: dict = {}
    for attempt in range(1, args.max_attempts + 1):
        entry: dict = {"n": attempt, "at": rb._now_iso()}
        try:
            try:
                run_id, cached, banked = convene(
                    client, args.base_url, user["token"], user["user_id"], ticker, mandate)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 402:
                    raise
                balance = rb.grant_credits(
                    client, args.base_url, user["user_id"], args.credit_grant, note=CREDIT_NOTE)
                entry["credit_grant"] = {"delta": args.credit_grant, "balance": balance}
                run_id, cached, banked = convene(
                    client, args.base_url, user["token"], user["user_id"], ticker, mandate)
            run = rb.poll_run(
                client, args.base_url, user["token"], run_id, args.poll_interval, args.run_timeout)
            status = run.get("status")
            entry.update(run_id=run_id, status=status)
            if status == "completed":
                final = {
                    "status": "completed", "run_id": run_id, "cached": cached, "banked": banked,
                    "verdict": run.get("verdict"), "model_tier": run.get("model_tier"),
                    "duration_ms": run.get("duration_ms"), "error_message": run.get("error_message"),
                }
                record["attempts"].append(entry)
                break
            entry.update(kind="transient", reason=f"room ended {status}: {run.get('error_message')}")
            final = {"status": "failed_after_retries", "run_id": run_id,
                     "error_message": f"room ended {status}: {run.get('error_message')}"}
        except Exception as exc:  # noqa: BLE001 — classified, logged, never dropped
            kind, reason = classify_error(exc)
            entry.update(kind=kind, reason=reason)
            if kind == "permanent":
                record["attempts"].append(entry)
                final = {"status": "permanent_failure", "error_message": reason}
                break
            final = {"status": "failed_after_retries", "error_message": reason}
        record["attempts"].append(entry)
        if attempt < args.max_attempts:
            sleep(args.retry_backoff * 2 ** (attempt - 1))
    record.update(final)
    if not args.no_snapshot:
        record["spot_price"] = rb.snapshot_price(ticker)
    record["finished_at"] = rb._now_iso()
    return record


def worker_user(
    out_dir: Path, client: httpx.Client, base: str, batch_id: str, plan: str,
    k: int, fresh: bool,
) -> dict:
    """The k-th worker's benchmark user (k=0 keeps the plain batch id)."""
    key = batch_id if k == 0 else f"{batch_id}#w{k}"
    users_path = out_dir / "users.json"
    with _io_lock:
        users = json.loads(users_path.read_text()) if users_path.exists() else {}
        if not fresh and key in users:
            return users[key]
        user = rb.mint_user(client, base)
        rb.set_plan(client, base, user["user_id"], plan, note=NOTE)
        user.update(plan=plan, created_at=rb._now_iso())
        users[key] = user
        users_path.write_text(json.dumps(users, indent=2) + "\n")
        return user


def print_plan(args, tickers: list[str], todo: list[str], skipped: dict[str, int]) -> None:
    print("CR282 Bursa batch — PLAN" + (" (dry run: nothing convened, no network)" if args.dry_run else ""))
    print(f"  batch id        : {args.batch_id}")
    print(f"  tickers         : {len(tickers)} in file, {len(todo)} to run, "
          f"skipped {skipped['completed']} completed + {skipped['permanent_failure']} permanent")
    print(f"  base url        : {args.base_url}")
    print(f"  plan / account  : {args.plan}; anonymous user, app_version 'room-benchmark', "
          f"{args.concurrency} worker user(s)")
    print(f"  concurrency     : {args.concurrency} (CR035 default 1; cap {MAX_CONCURRENCY})")
    print(f"  attempts/ticker : {args.max_attempts}, backoff {args.retry_backoff}s doubling")
    print(f"  credits         : top-up of {args.credit_grant} on a 402 via the admin credits endpoint; "
          f"~{len(todo) * BASIC_ROOM_CREDITS} needed at {BASIC_ROOM_CREDITS}/Room (CR035 figure)")
    print(f"  mandate override: {json.dumps(BURSA_MANDATE_OVERRIDE, sort_keys=True)}")
    print(f"  results         : {args.out_dir / f'runs_{args.batch_id}.jsonl'}")
    preview = ", ".join(todo[:10]) + (" ..." if len(todo) > 10 else "")
    print(f"  first tickers   : {preview}")


def main() -> int:
    ap = argparse.ArgumentParser(description="CR282 Bursa batch driver (Rooms against Alpha).")
    ap.add_argument("tickers_file", type=Path, help="sample_<seed>.csv or a one-per-line file")
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--plan", default="trader",
                    choices=["floor_pass", "trader", "floor_manager", "trial_trader"])
    ap.add_argument("--concurrency", type=int, default=1)
    ap.add_argument("--max-attempts", type=int, default=3)
    ap.add_argument("--retry-backoff", type=float, default=30.0)
    ap.add_argument("--credit-grant", type=int, default=2000)
    ap.add_argument("--poll-interval", type=float, default=20.0)
    ap.add_argument("--run-timeout", type=float, default=1500.0)
    ap.add_argument("--post-spacing", type=float, default=rb.POST_SPACING_S)
    ap.add_argument("--limit", type=int, default=None, help="run only the first N pending tickers")
    ap.add_argument("--fresh-user", action="store_true")
    ap.add_argument("--retry-permanent", action="store_true")
    ap.add_argument("--no-snapshot", action="store_true", help="skip the yfinance spot-price snapshot")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not 1 <= args.concurrency <= MAX_CONCURRENCY:
        raise SystemExit(f"--concurrency must be 1..{MAX_CONCURRENCY}")

    tickers = load_tickers(args.tickers_file)
    if not tickers:
        raise SystemExit(f"no tickers in {args.tickers_file}")
    runs_path = args.out_dir / f"runs_{args.batch_id}.jsonl"
    latest = rb.load_latest_records(runs_path)
    todo, skipped = pending_tickers(tickers, latest, args.retry_permanent)
    if args.limit is not None:
        todo = todo[: args.limit]
    print_plan(args, tickers, todo, skipped)
    if args.dry_run:
        return 0
    if not todo:
        print("nothing to do")
        return 0

    args.out_dir.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))
    health = client.get(f"{args.base_url}/v1/health")
    health.raise_for_status()
    print(f"backend ok: {health.json()}")
    users = [
        worker_user(args.out_dir, client, args.base_url, args.batch_id, args.plan, k, args.fresh_user)
        for k in range(args.concurrency)
    ]
    for u in users:
        print(f"benchmark user: {u['user_id']} (plan={u['plan']})")

    counts = {"completed": 0, "permanent_failure": 0, "failed_after_retries": 0}
    done = 0
    lock = threading.Lock()
    queue = list(enumerate(todo))
    qlock = threading.Lock()

    def worker(k: int) -> None:
        nonlocal done
        while True:
            with qlock:
                if not queue:
                    return
                i, ticker = queue.pop(0)
            with lock:
                print(f"[{i + 1}/{len(todo)}] w{k} {ticker}: starting", flush=True)
            rec = run_ticker(client, args, users[k], ticker, BURSA_MANDATE_OVERRIDE)
            with lock:
                rb.append_jsonl(runs_path, rec)
                counts[rec["status"]] = counts.get(rec["status"], 0) + 1
                done += 1
                action = (rec.get("verdict") or {}).get("action")
                print(f"    {ticker} -> {rec['status']} action={action} "
                      f"attempts={len(rec['attempts'])}"
                      + (f" ERROR={rec.get('error_message')}" if rec["status"] != "completed" else ""),
                      flush=True)
            time.sleep(args.post_spacing)

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        list(pool.map(worker, range(args.concurrency)))

    print(f"\ndone: {json.dumps(counts)} -> {runs_path}")
    bad = counts["permanent_failure"] + counts["failed_after_retries"]
    if bad:
        print(f"{bad} ticker(s) did not complete; failed_after_retries are re-tried on a re-run, "
              "permanent failures with --retry-permanent")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
