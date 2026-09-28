"""Batch run-loop for room_investigation_V2 (DESIGN.md §4.3).

Absorbs the run-loop shape v1 copy-pasted across three scripts —
``room_ticker_batch.py`` (ticker axis), ``room_repeat_consistency.py``
(repeat axis), and ``room_risk_score_sweep.py`` (risk_score axis) — into one
``run_arms()`` over an explicit ``Arm`` cell (ticker, mandate, prompt_variant,
label), replacing v1's one-script-per-axis shape.

Structural fixes over v1 (DESIGN.md §3 landmines 2, 5, 6):

- **Per-arm deterministic user ids.** ``arm_user_id(batch_user, arm.key)``
  is ``uuid5`` of the batch's persistent base user and the arm key, so no
  caller can ever share one ``user_id`` across concurrent convenes. V1's
  batch script shared one user and hit ``SimEngine.ensure_portfolio``'s
  unlocked SELECT-then-INSERT (CR246-class race: ``SimPortfolioRow``'s
  ``UniqueConstraint(user_id, kind, run_id)`` is NULL-ineffective because
  every training portfolio row has ``run_id IS NULL`` and NULL never equals
  NULL in a SQL unique constraint). Here the race is impossible by
  construction, not by convention.
- **Locked JSONL appends.** Every finished arm's record is appended under
  one ``asyncio.Lock``; v1 had the lock in the batch script only.
- **Prompt-variant constraint.** ``prompt_lab.apply_overrides`` patches a
  PROCESS-WIDE module attribute, and this module convenes arms
  concurrently — so a batch may carry at most ONE non-default prompt
  variant, enforced at scheduling time (``ValueError``). Benchmarks vary
  prompts per benchmark FILE (one variant per ``run_arms`` call), never
  per arm within a batch.

This module does NOT bootstrap the environment or force a provider — the
CLI entry point does ``env_bootstrap`` + ``provider_gateway.force_provider``
once and passes the forced gateway in. Backend (``app.*``) imports are lazy
so this module imports cleanly before ``env_bootstrap.ensure_backend_path()``
ran.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4, uuid5

try:
    from library import prompt_lab
except ImportError:
    import prompt_lab


@dataclass(frozen=True)
class Arm:
    key: str
    ticker: str
    mandate: dict
    label: str = ""
    prompt_variant: str = "backend-default"


@dataclass(frozen=True)
class ArmResult:
    arm: Arm
    user_id: str
    status: str
    verdict: dict | None
    duration_ms: int
    error_message: str | None
    spot_price: float | None
    triggered_at: str
    finished_at: str


@dataclass(frozen=True)
class RunSummary:
    batch_id: str
    total: int
    completed: int
    failed: int
    skipped_resumed: int
    results: list[ArmResult]


def base_mandate(*, risk_score: int, display_name: str | None = None) -> dict:
    """V1's mandate shape verbatim (room_kimi_gateway.base_mandate):
    risk_score/drawdown_response/concentration_tolerance track the arm value,
    max_drawdown_pct pinned at 30, compliance {}. The default display name is
    provider-agnostic here — v1 hardcoded "(Kimi)" into every label.
    """
    return {
        "display_name": display_name or f"Room bench R{risk_score}",
        "primary_goal": "long_term_wealth",
        "horizon": "long",
        "path": "long_horizon",
        "risk_score": risk_score,
        "drawdown_response": risk_score,
        "regret_asymmetry": 0,
        "concentration_tolerance": risk_score,
        "max_drawdown_pct": 30,
        "compliance": {},
    }


def snapshot_price(ticker: str) -> float | None:
    try:
        import yfinance as yf
        price = yf.Ticker(ticker).fast_info["last_price"]
        return round(float(price), 4) if price else None
    except Exception:  # noqa: BLE001 — a spot-price miss must not sink the run
        return None


def arm_user_id(batch_user_id: UUID, arm_key: str) -> UUID:
    """Deterministic per-(batch, arm) user id: uuid5(base, key).

    This is the structural fix for v1's ensure_portfolio race (CR246 class):
    concurrent arms can never share one user_id, because each arm's id is
    derived from its own key. SimPortfolioRow's UniqueConstraint(user_id,
    kind, run_id) is NULL-ineffective (run_id IS NULL for every training
    portfolio, and NULL != NULL in SQL), so the DB offers no real protection
    against N concurrent callers inserting for the same user_id — the only
    sound fix at this layer is that the race can never be entered. uuid5 (not
    uuid4) keeps the id reproducible across resumes with the same batch_id
    and traceable back to the batch's base user in users_<batch_id>.json.
    """
    return uuid5(batch_user_id, arm_key)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _load_latest_records(path: Path) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                if "arm_key" in rec:
                    latest[rec["arm_key"]] = rec
    return latest


async def _append_jsonl(lock: asyncio.Lock, path: Path, record: dict) -> None:
    # Concurrent arms all append to the SAME file — `open(..., "a")` + write()
    # is not guaranteed atomic against interleaved writers on every
    # platform/size, so every writer serializes through this one lock.
    async with lock:
        with path.open("a") as f:
            f.write(json.dumps(record, default=str) + "\n")


async def _convene_arm(
    arm: Arm,
    *,
    runner: Any,
    mandate: Any,
    user_id: UUID,
    agent_timeout_s: float,
) -> tuple[str, dict | None, int, str | None]:
    """One full Room convene; returns (status, verdict, duration_ms, error).

    The verdict event shape is v1's (room_kimi_gateway.run_one_ticker):
    RoomEvent(kind="verdict", verdict=<Verdict>) — model_dump()'d when
    pydantic. No verdict event -> "no_verdict"; any exception ->
    "script_error" with repr clipped to 300 chars, and the batch continues.
    """
    started = time.monotonic()
    verdict = None
    status = "completed"
    error_message = None
    try:
        async for ev in runner.run(
            run_id=uuid4(), user_id=user_id, ticker=arm.ticker,
            mandate=mandate, agent_timeout_s=agent_timeout_s,
        ):
            if ev.kind == "verdict" and ev.verdict is not None:
                verdict = (
                    ev.verdict.model_dump()
                    if hasattr(ev.verdict, "model_dump")
                    else ev.verdict
                )
        if verdict is None:
            status = "no_verdict"
    except Exception as exc:  # noqa: BLE001 — record and continue the batch
        status = "script_error"
        error_message = repr(exc)[:300]
    duration_ms = int((time.monotonic() - started) * 1000)
    return status, verdict, duration_ms, error_message


async def run_arms(
    arms: Iterable[Arm],
    *,
    batch_id: str,
    out_path: Path,
    benchmarks_dir: Path,
    gateway,
    max_concurrent: int = 3,
    post_spacing_s: float = 15.0,
    agent_timeout_s: float = 300.0,
    fresh_user: bool = False,
) -> RunSummary:
    """Run one full Room convene per arm against the passed (forced) gateway.

    Resume: arms whose key already has a ``status == "completed"`` record in
    ``out_path`` are skipped and counted in ``skipped_resumed``; their stored
    records are NOT merged into ``RunSummary.results`` — the summary covers
    this run only.

    Prompt variants: every arm's ``prompt_variant`` resolves through
    ``prompt_lab.load_variant`` ("backend-default" -> None -> no-op) and
    applies via ``prompt_lab.apply_overrides`` around that arm's convene
    ONLY. The override is process-wide, so a batch may carry at most one
    non-default variant — two arms with different non-default variants raise
    ``ValueError`` at scheduling time. Benchmarks vary prompts per benchmark
    FILE: one variant per ``run_arms`` call, never per concurrent arm. Arms
    carrying the variant also serialize on an internal lock for the whole
    convene, because a concurrent peer exiting its ``apply_overrides`` block
    would otherwise restore the backend-default loader mid-convene.

    Returns the summary; never calls sys.exit — callers decide exit codes.
    """
    from app.services.mandate_store import resolve_mandate
    from app.services.room_runner import RoomRunner

    arms = list(arms)
    keys = [a.key for a in arms]
    if len(set(keys)) != len(keys):
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        raise ValueError(
            f"duplicate arm key(s) {dupes} — arm.key must be unique within a "
            "batch; it drives the deterministic user id and resume matching"
        )
    variants = {a.prompt_variant for a in arms} - {prompt_lab.BACKEND_DEFAULT_VARIANT}
    if len(variants) > 1:
        raise ValueError(
            f"one batch may carry at most one non-default prompt variant, got "
            f"{sorted(variants)} — prompt_lab.apply_overrides is process-wide "
            "and this module convenes arms concurrently; benchmarks vary "
            "prompts per benchmark FILE (one variant per run_arms call)"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    users_path = out_path.parent / f"users_{batch_id}.json"
    users = json.loads(users_path.read_text()) if users_path.exists() else {}
    if fresh_user or batch_id not in users:
        base_user_id = uuid4()
        users[batch_id] = {"user_id": str(base_user_id), "created_at": _now_iso()}
        users_path.write_text(json.dumps(users, indent=2) + "\n")
    else:
        base_user_id = UUID(users[batch_id]["user_id"])
    print(f"batch base user: {base_user_id} (local synthetic — not minted via "
          f"/v1/auth/anon, never touches melehost's user table)")

    runner = RoomRunner(llm=gateway)

    user_ids = {a.key: arm_user_id(base_user_id, a.key) for a in arms}
    mandates = {a.key: resolve_mandate(user_ids[a.key], a.mandate) for a in arms}

    latest = _load_latest_records(out_path)
    to_run = [
        a for a in arms
        if not (latest.get(a.key) and latest[a.key].get("status") == "completed")
    ]
    skipped_resumed = len(arms) - len(to_run)
    for a in arms:
        if a not in to_run:
            print(f"[{a.key}] already completed, skip", flush=True)

    write_lock = asyncio.Lock()
    override_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(max_concurrent)
    results: list[ArmResult] = []
    total = len(to_run)
    finished = 0

    async def _run_one(arm: Arm) -> None:
        nonlocal finished
        async with semaphore:
            user_id = user_ids[arm.key]
            print(f"[{arm.key}] starting… (slot acquired, user={user_id})", flush=True)
            overrides = prompt_lab.load_variant(
                arm.prompt_variant, benchmarks_dir=benchmarks_dir
            )
            triggered_at = _now_iso()
            if overrides is None:
                status, verdict, duration_ms, error_message = await _convene_arm(
                    arm, runner=runner, mandate=mandates[arm.key],
                    user_id=user_id, agent_timeout_s=agent_timeout_s,
                )
            else:
                async with override_lock:
                    with prompt_lab.apply_overrides(overrides):
                        status, verdict, duration_ms, error_message = await _convene_arm(
                            arm, runner=runner, mandate=mandates[arm.key],
                            user_id=user_id, agent_timeout_s=agent_timeout_s,
                        )
            spot = snapshot_price(arm.ticker)
            finished_at = _now_iso()
            record = {
                "batch_id": batch_id,
                "arm_key": arm.key,
                "label": arm.label,
                "prompt_variant": arm.prompt_variant,
                "ticker": arm.ticker,
                "risk_score": arm.mandate.get("risk_score"),
                "user_id": str(user_id),
                "ablation": False,
                "triggered_at": triggered_at,
                "spot_price": spot,
                "status": status,
                "verdict": verdict,
                "duration_ms": duration_ms,
                "error_message": error_message,
                "finished_at": finished_at,
            }
            await _append_jsonl(write_lock, out_path, record)
            results.append(ArmResult(
                arm=arm,
                user_id=str(user_id),
                status=status,
                verdict=verdict,
                duration_ms=duration_ms,
                error_message=error_message,
                spot_price=spot,
                triggered_at=triggered_at,
                finished_at=finished_at,
            ))
            finished += 1
            v = verdict or {}
            print(
                f"[{arm.key}] ({finished}/{total}) → {status} "
                f"action={v.get('action')} "
                f"votes={v.get('approve_votes')}/{v.get('samples')} "
                f"spot={spot} duration_ms={duration_ms}",
                flush=True,
            )
            # Holds this concurrency slot open after the convene — v1's
            # rate-spreading behavior: pacing survives parallelism instead of
            # every queued arm firing at once.
            await asyncio.sleep(post_spacing_s)

    if to_run:
        print(
            f"running {total} arm(s), up to {max_concurrent} concurrent …",
            flush=True,
        )
        await asyncio.gather(*(_run_one(a) for a in to_run))

    completed = sum(1 for r in results if r.status == "completed")
    failed = len(results) - completed
    print(
        f"\ndone: {completed}/{len(arms)} completed "
        f"({failed} failed, {skipped_resumed} resumed-skipped) → {out_path}"
    )
    return RunSummary(
        batch_id=batch_id,
        total=len(arms),
        completed=completed,
        failed=failed,
        skipped_resumed=skipped_resumed,
        results=results,
    )
