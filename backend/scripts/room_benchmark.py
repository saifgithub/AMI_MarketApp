"""Room-vs-Street benchmark runner (CR035) — convene the Room for a list of
tickers against the live Alpha backend and record each final Verdict.

Per batch it mints a fresh anonymous user (defeats the 24 h (user, ticker)
dedup), patches the plan via the admin API so runs execute at a representative
tier, then loops tickers sequentially: stream-POST /v1/room/stream (grab the
X-Room-Run-Id header, close — the run is a detached background task), poll
GET /v1/room/{run_id} to terminal status, snapshot the spot price, append one
JSONL record. Resumable: tickers whose latest record is completed are skipped.

Usage (from backend/):
    .venv/bin/python -m scripts.room_benchmark path/to/tickers.txt \
        --batch-id baseline-2026-07-16
    .venv/bin/python -m scripts.room_benchmark tickers.txt --ablation \
        --batch-id ablation-2026-07-16

ADMIN_SECRET is read from the environment, falling back to infra/alpha.env.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

DEFAULT_BASE = "http://192.168.20.59:8000"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "docs/forward_planning/CR035_room_benchmark/results"
ALPHA_ENV = REPO_ROOT / "infra/alpha.env"

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
POST_SPACING_S = 15.0

# Pinned copy of the hydrate_brief_mandate defaults so the benchmark is immune
# to future default drift (neutral goal, risk 3, no ethics filters, no blocklist).
NEUTRAL_MANDATE_OVERRIDE = {
    "display_name": "Benchmark",
    "primary_goal": "long_term_wealth",
    "horizon": "long",
    "path": "long_horizon",
    "risk_score": 3,
    "drawdown_response": 3,
    "regret_asymmetry": 0,
    "concentration_tolerance": 3,
    "max_drawdown_pct": 30,
    "compliance": {},
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _admin_secret() -> str:
    import os

    secret = os.environ.get("ADMIN_SECRET", "")
    if secret:
        return secret
    if ALPHA_ENV.exists():
        for line in ALPHA_ENV.read_text().splitlines():
            if line.startswith("ADMIN_SECRET="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("ADMIN_SECRET not in env and not found in infra/alpha.env")


def mint_user(client: httpx.Client, base: str) -> dict:
    resp = client.post(
        f"{base}/v1/auth/anon",
        json={"locale": "en", "timezone": "UTC", "app_version": "room-benchmark"},
    )
    resp.raise_for_status()
    body = resp.json()
    return {"user_id": body["user"]["id"], "token": body["token"]}


def set_plan(client: httpx.Client, base: str, user_id: str, plan: str) -> None:
    resp = client.patch(
        f"{base}/v1/admin/users/{user_id}/plan",
        json={"plan": plan, "note": "CR035 room benchmark batch user"},
        headers={"Authorization": f"Bearer {_admin_secret()}"},
    )
    resp.raise_for_status()


def grant_credits(client: httpx.Client, base: str, user_id: str, delta: int) -> int:
    """Top up the benchmark user's credit balance, returning the new balance.

    CR039 meters Convene the Room: a Trader plan gets a 150-credit monthly
    allowance and a Basic Room costs 8, so a benchmark user runs dry after
    exactly 18 convenes (which is how arm A died at 18/150 with 402s).

    Granting up-front does NOT work: credit_service._ensure_period re-grants
    the allowance when `credits_plan_at_grant` drifts, and this script patches
    the plan straight after minting — so the first convene would reset any
    pre-granted balance back to 150. Topping up in response to a 402 is
    therefore the only order that survives the re-grant, and it self-heals if
    a long batch drains the balance again.
    """
    resp = client.post(
        f"{base}/v1/admin/users/{user_id}/credits",
        json={"delta": delta, "note": "CR035 benchmark top-up (metered by CR039)"},
        headers={"Authorization": f"Bearer {_admin_secret()}"},
    )
    resp.raise_for_status()
    return int(resp.json().get("credit_balance", -1))


def load_or_create_batch_user(
    out_dir: Path, client: httpx.Client, base: str, batch_id: str, plan: str,
    fresh: bool,
) -> dict:
    """One user per batch_id, persisted to users.json and reused on resume."""
    users_path = out_dir / "users.json"
    users = json.loads(users_path.read_text()) if users_path.exists() else {}
    if not fresh and batch_id in users:
        return users[batch_id]
    user = mint_user(client, base)
    set_plan(client, base, user["user_id"], plan)
    user["plan"] = plan
    user["created_at"] = _now_iso()
    users[batch_id] = user
    users_path.write_text(json.dumps(users, indent=2) + "\n")
    return user


def start_room_run(
    client: httpx.Client, base: str, token: str, user_id: str, ticker: str,
    mandate_override: dict,
) -> tuple[str, bool]:
    """POST /v1/room/stream, return (run_id, cached) from headers, close the SSE."""
    with client.stream(
        "POST",
        f"{base}/v1/room/stream",
        json={
            "user_id": user_id,
            "ticker": ticker,
            "mandate_override": mandate_override,
            "locale": "en",
        },
        headers={"Authorization": f"Bearer {token}"},
    ) as resp:
        resp.raise_for_status()
        run_id = resp.headers["X-Room-Run-Id"]
        cached = resp.headers.get("X-Room-Cached", "").lower() == "true"
    return run_id, cached


def poll_run(
    client: httpx.Client, base: str, token: str, run_id: str,
    interval_s: float, timeout_s: float,
) -> dict:
    deadline = time.monotonic() + timeout_s
    while True:
        resp = client.get(
            f"{base}/v1/room/{run_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        run = resp.json()
        if run.get("status") in TERMINAL_STATUSES:
            return run
        if time.monotonic() > deadline:
            run["status"] = "poll_timeout"
            return run
        time.sleep(interval_s)


def snapshot_price(ticker: str) -> float | None:
    try:
        import yfinance as yf

        price = yf.Ticker(ticker).fast_info["last_price"]
        return round(float(price), 4) if price else None
    except Exception:
        return None


def load_latest_records(runs_path: Path) -> dict[str, dict]:
    """ticker → latest record for this file (append-only JSONL)."""
    latest: dict[str, dict] = {}
    if runs_path.exists():
        for line in runs_path.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                latest[rec["ticker"]] = rec
    return latest


def append_jsonl(path: Path, record: dict) -> None:
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="CR035 Room-vs-Street benchmark runner.")
    parser.add_argument("tickers_file", type=Path)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--plan", default="trader",
                        choices=["floor_pass", "trader", "floor_manager", "trial_trader"])
    parser.add_argument("--batch-id", required=True,
                        help="Batch label; one benchmark user is minted per batch-id.")
    parser.add_argument("--fresh-user", action="store_true",
                        help="Mint a new user even if this batch-id already has one.")
    parser.add_argument("--ablation", action="store_true",
                        help="Tag records as ablation (SUPPRESS_ANALYST_CONSENSUS batch).")
    parser.add_argument("--mandate-json", default=None,
                        help="JSON mandate_override replacing the neutral default "
                             "(compliance-probe batches).")
    parser.add_argument("--credit-grant", type=int, default=2000,
                        help="Credits to grant when a run is refused with 402 "
                             "(CR039 metering). 150 tickers x 8 = 1200.")
    parser.add_argument("--poll-interval", type=float, default=20.0)
    parser.add_argument("--run-timeout", type=float, default=1500.0,
                        help="Seconds to wait for one run to reach a terminal status.")
    args = parser.parse_args()

    tickers = [
        t.strip().upper()
        for t in args.tickers_file.read_text().splitlines()
        if t.strip() and not t.strip().startswith("#")
    ]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    runs_path = args.out_dir / f"runs_{args.batch_id}.jsonl"
    latest = load_latest_records(runs_path)

    client = httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))
    health = client.get(f"{args.base_url}/v1/health")
    health.raise_for_status()
    print(f"backend ok: {health.json()}")

    user = load_or_create_batch_user(
        args.out_dir, client, args.base_url, args.batch_id, args.plan,
        fresh=args.fresh_user,
    )
    print(f"batch user: {user['user_id']} (plan={user['plan']})")

    failures: list[str] = []
    for i, ticker in enumerate(tickers):
        prior = latest.get(ticker)
        if prior and prior.get("status") == "completed":
            print(f"[{i + 1}/{len(tickers)}] {ticker}: already completed, skip")
            continue
        print(f"[{i + 1}/{len(tickers)}] {ticker}: starting…", flush=True)
        triggered_at = _now_iso()
        record = {
            "batch_id": args.batch_id,
            "ticker": ticker,
            "user_id": user["user_id"],
            "ablation": args.ablation,
            "triggered_at": triggered_at,
        }
        mandate_override = (
            json.loads(args.mandate_json) if args.mandate_json else NEUTRAL_MANDATE_OVERRIDE
        )
        try:
            try:
                run_id, cached = start_room_run(
                    client, args.base_url, user["token"], user["user_id"], ticker,
                    mandate_override,
                )
            except httpx.HTTPStatusError as exc:
                # CR039 credit gate. Top up and retry once — see grant_credits()
                # for why this can't be done up-front.
                if exc.response.status_code != 402:
                    raise
                balance = grant_credits(
                    client, args.base_url, user["user_id"], args.credit_grant,
                )
                print(f"    402 insufficient credits — granted {args.credit_grant}, "
                      f"balance now {balance}", flush=True)
                run_id, cached = start_room_run(
                    client, args.base_url, user["token"], user["user_id"], ticker,
                    mandate_override,
                )
            run = poll_run(
                client, args.base_url, user["token"], run_id,
                args.poll_interval, args.run_timeout,
            )
            record.update(
                run_id=run_id,
                cached=cached,
                status=run.get("status"),
                verdict=run.get("verdict"),
                model_tier=run.get("model_tier"),
                duration_ms=run.get("duration_ms"),
                error_message=run.get("error_message"),
            )
        except Exception as exc:  # noqa: BLE001 — record and continue the batch
            record.update(status="script_error", error_message=repr(exc)[:300])
        record["spot_price"] = snapshot_price(ticker)
        record["finished_at"] = _now_iso()
        append_jsonl(runs_path, record)
        verdict = record.get("verdict") or {}
        print(
            f"    → {record.get('status')} action={verdict.get('action')} "
            f"cached={record.get('cached')} spot={record.get('spot_price')}",
            flush=True,
        )
        if record.get("status") != "completed":
            failures.append(ticker)
        time.sleep(POST_SPACING_S)

    print(f"\ndone: {len(tickers) - len(failures)}/{len(tickers)} completed "
          f"→ {runs_path}")
    if failures:
        print(f"failures ({len(failures)}): {', '.join(failures)} — re-run to retry")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
