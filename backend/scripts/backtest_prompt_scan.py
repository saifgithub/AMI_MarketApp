"""CR164 leakage guard (b) — scan the assembled prompts of a backtest batch
for anything the Room should not have been able to see at its as-of date.

For every `backtest_run_index` row of --batch-id (optionally a seeded
subsample via --sample, e.g. 0.1 for the full-sweep tranches), the run's
`room_runs` row supplies the wall-clock window and user, and the LLM calls
are correlated from `llm_audit` by same user_id AND created_at within
[started_at - 60s, finished_at + 60s] — `llm_audit` carries no run id, so
the window IS the join. Each correlated row's full prompt (system_prompt +
JSON-flattened messages) gets two scans:

  HARD FAIL — any parseable date (ISO YYYY-MM-DD, "Month DD, YYYY",
      "Month YYYY", month names case-insensitive incl. abbreviations)
      strictly after the run's as_of. Strict by design: no exception
      phrases, no allowlist — a false positive costs one human read, a
      false negative invalidates the batch (CR038: prompt instructions
      are not controls, and neither are scanner excuses).
  FLAG — the ticker's real post-as_of closes (`price_history_daily`,
      source != mock, date in (as_of, as_of+30d]) rendered to 2 decimals
      and searched in the prompt with digit boundaries (a bare substring
      match inside a longer number is not a price sighting). A number
      match is circumstantial, so it flags for review rather than failing.

Degrade loudly (CR040): a batch with zero index rows, or any sampled run
that correlates to ZERO audit rows (or has no started/finished window), is
a finding, not a silent pass — loud warning lines and exit 2. Any hard
fail → exit 1. Clean → exit 0. Report: <out-dir>/prompt_scan_<batch-id>.md.

Usage (inside the alpha container, or from backend/ against an
AMI_TEST_DATABASE_URL sqlite for local smokes):
    .venv/bin/python scripts/backtest_prompt_scan.py --batch-id pit-pilot-1
    .venv/bin/python scripts/backtest_prompt_scan.py --batch-id pit-full-1 \
        --sample 0.1 --seed 164
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import get_session, init_schema
from app.db.models import (
    BacktestRunIndexRow,
    LLMAuditRow,
    PriceHistoryDailyRow,
    RoomRunRow,
)
from app.services.price_history import _MOCK_SOURCE

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "docs/forward_planning/CR164_room_backtest/results"

CORRELATION_WINDOW_S = 60
PRICE_WINDOW_DAYS = 30
SNIPPET_WIDTH = 80

_MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))
# (?<!\d)/(?!\d) instead of \b so the date part of "2026-08-10T12:00" still
# matches (digit→letter is not a \b boundary) and "12026-08-10" does not.
_ISO_RE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_MONTH_DD_RE = re.compile(
    rf"\b({_MONTH_ALT})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})(?!\d)",
    re.IGNORECASE,
)
_MONTH_YYYY_RE = re.compile(rf"\b({_MONTH_ALT})\.?\s+(\d{{4}})(?!\d)", re.IGNORECASE)


def extract_dates(text: str) -> list[tuple[date, int, int, str]]:
    """Every parseable date mention as (date, span_start, span_end, matched).
    "Month YYYY" parses to the 1st of that month, so it only lands after
    as_of when the whole month does."""
    found: list[tuple[date, int, int, str]] = []
    for m in _ISO_RE.finditer(text):
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        found.append((d, m.start(), m.end(), m.group(0)))
    for m in _MONTH_DD_RE.finditer(text):
        try:
            d = date(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))
        except ValueError:
            continue
        found.append((d, m.start(), m.end(), m.group(0)))
    for m in _MONTH_YYYY_RE.finditer(text):
        try:
            d = date(int(m.group(2)), _MONTHS[m.group(1).lower()], 1)
        except ValueError:
            continue
        found.append((d, m.start(), m.end(), m.group(0)))
    return found


def snippet(text: str, start: int, end: int, width: int = SNIPPET_WIDTH) -> str:
    pad = max(0, width - (end - start))
    lo = max(0, start - pad // 2)
    piece = text[lo:lo + max(width, end - start)]
    return " ".join(piece.split()).replace("|", "\\|")


def prompt_text(row: LLMAuditRow) -> str:
    parts = [row.system_prompt or ""]
    msgs = row.messages or []
    try:
        parts.append(json.dumps(msgs, ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        parts.append(str(msgs))
    return "\n".join(parts)


def post_asof_closes(session, ticker: str, as_of: date) -> list[tuple[date, str]]:
    """(date, adj_close rendered to 2dp) for real rows in (as_of, as_of+30d]."""
    rows = session.execute(
        select(PriceHistoryDailyRow.date, PriceHistoryDailyRow.adj_close)
        .where(
            PriceHistoryDailyRow.ticker == ticker.upper(),
            PriceHistoryDailyRow.date > as_of,
            PriceHistoryDailyRow.date <= as_of + timedelta(days=PRICE_WINDOW_DAYS),
            PriceHistoryDailyRow.source != _MOCK_SOURCE,
        )
        .order_by(PriceHistoryDailyRow.date)
    ).all()
    return [(d, f"{float(px):.2f}") for d, px in rows]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--sample", type=float, default=1.0,
                    help="fraction of index rows to scan (seeded); 1.0 = all")
    ap.add_argument("--seed", type=int, default=164)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = ap.parse_args()

    if not (0.0 < args.sample <= 1.0):
        raise SystemExit(f"FATAL: --sample must be in (0, 1], got {args.sample}")

    init_schema()

    with get_session() as session:
        index_rows = session.execute(
            select(BacktestRunIndexRow)
            .where(BacktestRunIndexRow.batch_id == args.batch_id)
        ).scalars().all()
    index_rows.sort(key=lambda r: (r.as_of, r.ticker))

    if not index_rows:
        print(
            f"WARNING: batch '{args.batch_id}' has ZERO backtest_run_index rows — "
            "nothing to scan. A missing batch is a finding, not a clean pass.",
            flush=True,
        )
        return 2

    if args.sample < 1.0:
        k = max(1, round(len(index_rows) * args.sample))
        rng = random.Random(args.seed)
        index_rows = sorted(
            rng.sample(index_rows, k), key=lambda r: (r.as_of, r.ticker),
        )
        print(f"[scan] seeded sample: {k} of batch runs (sample={args.sample}, "
              f"seed={args.seed})", flush=True)

    hard_fails: list[dict] = []   # run_id, ticker, as_of, audit_id, found_date, snippet
    flags: list[dict] = []        # run_id, ticker, as_of, audit_id, price_date, price, snippet
    correlation_failures: list[dict] = []  # run_id, ticker, as_of, reason
    audit_rows_scanned = 0

    with get_session() as session:
        for idx in index_rows:
            run = session.get(RoomRunRow, idx.room_run_id)
            label = f"{idx.ticker}@{idx.as_of.isoformat()}"
            if run is None:
                print(f"WARNING: {label} run {idx.room_run_id}: no room_runs row — "
                      "correlation impossible", flush=True)
                correlation_failures.append({
                    "run_id": str(idx.room_run_id), "ticker": idx.ticker,
                    "as_of": idx.as_of.isoformat(), "reason": "room_runs row missing",
                })
                continue
            if run.started_at is None or run.finished_at is None:
                print(f"WARNING: {label} run {run.id}: started_at/finished_at NULL "
                      f"(status={run.status}) — no correlation window", flush=True)
                correlation_failures.append({
                    "run_id": str(run.id), "ticker": idx.ticker,
                    "as_of": idx.as_of.isoformat(),
                    "reason": f"no wall-clock window (status={run.status})",
                })
                continue

            lo = run.started_at - timedelta(seconds=CORRELATION_WINDOW_S)
            hi = run.finished_at + timedelta(seconds=CORRELATION_WINDOW_S)
            audit_rows = session.execute(
                select(LLMAuditRow)
                .where(
                    LLMAuditRow.user_id == run.user_id,
                    LLMAuditRow.created_at >= lo,
                    LLMAuditRow.created_at <= hi,
                )
                .order_by(LLMAuditRow.created_at)
            ).scalars().all()

            if not audit_rows:
                print(f"WARNING: {label} run {run.id}: ZERO llm_audit rows in "
                      f"[{lo}, {hi}] for user {run.user_id} — the prompt this run "
                      "actually saw is unverifiable", flush=True)
                correlation_failures.append({
                    "run_id": str(run.id), "ticker": idx.ticker,
                    "as_of": idx.as_of.isoformat(),
                    "reason": "zero llm_audit rows in window",
                })
                continue

            closes = post_asof_closes(session, idx.ticker, idx.as_of)
            for arow in audit_rows:
                audit_rows_scanned += 1
                text = prompt_text(arow)

                seen_dates: set[date] = set()
                for found, s, e, matched in extract_dates(text):
                    if found <= idx.as_of or found in seen_dates:
                        continue
                    seen_dates.add(found)
                    hard_fails.append({
                        "run_id": str(run.id), "ticker": idx.ticker,
                        "as_of": idx.as_of.isoformat(),
                        "audit_id": str(arow.id),
                        "found_date": f"{found.isoformat()} ('{matched}')",
                        "snippet": snippet(text, s, e),
                    })
                    print(f"HARD FAIL: {label} run {run.id} audit {arow.id}: "
                          f"post-as_of date {found.isoformat()} ({matched!r})",
                          flush=True)

                for px_date, px_str in closes:
                    m = re.search(rf"(?<![\d.]){re.escape(px_str)}(?!\d)", text)
                    if m is None:
                        continue
                    flags.append({
                        "run_id": str(run.id), "ticker": idx.ticker,
                        "as_of": idx.as_of.isoformat(),
                        "audit_id": str(arow.id),
                        "price_date": px_date.isoformat(),
                        "price": px_str,
                        "snippet": snippet(text, m.start(), m.end()),
                    })
                    print(f"FLAG: {label} run {run.id} audit {arow.id}: post-as_of "
                          f"close {px_str} ({px_date.isoformat()}) appears in prompt",
                          flush=True)

    lines = [
        f"# CR164 prompt leakage scan — batch `{args.batch_id}`",
        "",
        "Guard (b): post-as_of dates hard-fail; post-as_of close-price matches flag.",
        "Correlation: `llm_audit` rows by same user_id, created_at within",
        f"[started_at − {CORRELATION_WINDOW_S}s, finished_at + {CORRELATION_WINDOW_S}s].",
        "",
        "## Totals",
        "",
        f"- Index rows scanned: **{len(index_rows)}** (sample={args.sample}, seed={args.seed})",
        f"- llm_audit rows scanned: **{audit_rows_scanned}**",
        f"- Hard fails (post-as_of dates): **{len(hard_fails)}**",
        f"- Flags (post-as_of close prices): **{len(flags)}**",
        f"- Correlation failures: **{len(correlation_failures)}**",
        "",
        "## Hard fails",
        "",
    ]
    if hard_fails:
        lines += [
            "| run_id | ticker | as_of | audit row | found date | context |",
            "|---|---|---|---|---|---|",
        ]
        lines += [
            f"| {f['run_id']} | {f['ticker']} | {f['as_of']} | {f['audit_id']} "
            f"| {f['found_date']} | `{f['snippet']}` |"
            for f in hard_fails
        ]
    else:
        lines.append("None.")
    lines += ["", "## Flags (post-as_of closes found in prompt text)", ""]
    if flags:
        lines += [
            "| run_id | ticker | as_of | audit row | price date | price | context |",
            "|---|---|---|---|---|---|---|",
        ]
        lines += [
            f"| {f['run_id']} | {f['ticker']} | {f['as_of']} | {f['audit_id']} "
            f"| {f['price_date']} | {f['price']} | `{f['snippet']}` |"
            for f in flags
        ]
    else:
        lines.append("None.")
    lines += ["", "## Correlation failures", ""]
    if correlation_failures:
        lines += ["| run_id | ticker | as_of | reason |", "|---|---|---|---|"]
        lines += [
            f"| {f['run_id']} | {f['ticker']} | {f['as_of']} | {f['reason']} |"
            for f in correlation_failures
        ]
        lines.append("")
        lines.append("A correlation failure means the prompt that run actually saw "
                     "is UNVERIFIED — the batch cannot be declared scan-clean.")
    else:
        lines.append("None.")
    lines.append("")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"prompt_scan_{args.batch_id}.md"
    out_path.write_text("\n".join(lines))
    print(f"[scan] report written: {out_path}", flush=True)

    if hard_fails:
        print(f"[scan] RESULT: {len(hard_fails)} HARD FAIL(S) — batch is NOT clean "
              "(exit 1)", flush=True)
        return 1
    if correlation_failures:
        print(f"[scan] RESULT: {len(correlation_failures)} correlation failure(s) — "
              "scan coverage incomplete (exit 2)", flush=True)
        return 2
    print(f"[scan] RESULT: clean — {audit_rows_scanned} audit rows across "
          f"{len(index_rows)} runs, 0 hard fails, {len(flags)} flag(s) (exit 0)",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
