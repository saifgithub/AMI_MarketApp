"""CR164 leakage guard (c): find the vLLM model's knowledge-collapse month.

A historical backtest of the Room is only valid over dates the LLM cannot
"remember" (docs/benchmark/claude/09 R-rules, kimi §6.5). This probe measures
where the served model's market knowledge actually ends, instead of trusting a
model card: for each (anchor ticker, month) it asks the model for the closing
price on the month's last trading day, scores the answer against the real close
from yfinance, and reports the first month where accuracy collapses or the
model starts answering UNKNOWN. CR164's sweep window then starts at
``collapse_month + 8 weeks`` — the margin absorbs fuzzy near-cutoff knowledge.

Runs from the Mac, LAN-direct against the vLLM host (this is a measurement of
the *model*, not the gateway plumbing — and the Mac has no DB for the
gateway's llm_audit write path). Sequential, temperature 0.

Usage:
    .venv/bin/python scripts/backtest_cutoff_probe.py \
        --out ../docs/forward_planning/CR164_room_backtest/results
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import statistics
import sys
import time
from pathlib import Path

import httpx
import yfinance as yf

# CR217 — defaults, not constants. The probe measures a MODEL's knowledge
# cutoff, and the served model is no longer fixed: CR211 swapped the on-prem
# serve, and CR217 evaluates a second host entirely. A hardcoded endpoint made
# the probe silently un-runnable against any candidate, which matters because
# an as-of backtest is only valid over dates the model cannot remember — swap
# the model without re-probing and a later cutoff turns recall into apparent
# edge.
DEFAULT_VLLM_BASE_URL = "http://192.168.20.74:8000"
DEFAULT_MODEL = "ami-llm"

ANCHORS = {
    "SPY": "the SPDR S&P 500 ETF",
    "QQQ": "the Invesco QQQ ETF",
    "AAPL": "Apple Inc.",
    "NVDA": "NVIDIA Corporation",
    "MSFT": "Microsoft Corporation",
    "TSLA": "Tesla Inc.",
}

# Sanity months (model should know these well) through the candidate cutoff region.
START_MONTH = (2023, 9)
END_MONTH = (2026, 7)

# Event-recall battery: price refusal is not proof of no knowledge — a model can
# refuse price estimates on caution alone while still recalling later events.
# The window start must clear the LAST event the model recalls, not just the
# price-collapse month. Baseline events (pre-2024-09) validate the probe itself;
# boundary events walk forward from the price-collapse candidate.
# Truth months are hand-verified facts, not model output.
EVENT_PROBES = [
    ("svb_collapse", "the collapse of Silicon Valley Bank", "2023-03", "baseline"),
    ("btc_etf", "the first approval of US spot Bitcoin ETFs by the SEC", "2024-01", "baseline"),
    ("nvda_split", "NVIDIA's 10-for-1 stock split taking effect", "2024-06", "baseline"),
    ("crowdstrike", "the global IT outage caused by a CrowdStrike update", "2024-07", "baseline"),
    ("fed_sep24_cut", "the FOMC's first rate cut of the 2024 easing cycle (a 50bp cut)", "2024-09", "boundary"),
    ("us_election_winner", "Donald Trump winning the US presidential election", "2024-11", "boundary"),
    ("fed_dec24_cut", "the FOMC cutting rates by 25bp at its December 2024 meeting", "2024-12", "boundary"),
    ("deepseek_r1", "the DeepSeek R1 release triggering a large one-day NVIDIA selloff", "2025-01", "boundary"),
    ("liberation_day", "President Trump's 'Liberation Day' reciprocal tariffs announcement", "2025-04", "boundary"),
    ("circle_ipo", "Circle Internet Group's IPO on the NYSE (ticker CRCL)", "2025-06", "boundary"),
    ("figma_ipo", "Figma's IPO (ticker FIG)", "2025-07", "boundary"),
]

EVENT_PROMPT = (
    "From your training knowledge only: in which month and year did the following "
    "happen — {event}? Reply with ONLY the month and year in the form 'YYYY-MM'. "
    "If you have no knowledge of this event, reply with exactly: UNKNOWN"
)

_MONTH_RE = re.compile(r"(20\d{2})[-/](\d{1,2})")

# Collapse criteria: a month fails when the median relative error of answered
# probes exceeds ERR_THRESHOLD or at least half the anchors answer UNKNOWN;
# collapse is the first failing month that is followed by another failing month
# (two in a row, so one noisy month can't end the window early).
ERR_THRESHOLD = 0.10
REFUSAL_THRESHOLD = 0.5
MARGIN_DAYS = 56  # 8 weeks

PROMPT = (
    "From your training knowledge only, give your best single-number estimate of "
    "the closing price of {name} (ticker {ticker}) on the last trading day of "
    "{month_name} {year}. Reply with ONLY the number, no words, no currency sign. "
    "If you genuinely have no knowledge of that period, reply with exactly: UNKNOWN"
)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_NUM_RE = re.compile(r"-?\d{1,6}(?:,\d{3})*(?:\.\d+)?")


def month_range(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    out = []
    y, m = start
    while (y, m) <= end:
        out.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def month_end_closes(ticker: str, months: list[tuple[int, int]]) -> dict[tuple[int, int], float]:
    first = dt.date(months[0][0], months[0][1], 1)
    last = dt.date(months[-1][0], months[-1][1], 28) + dt.timedelta(days=10)
    hist = yf.Ticker(ticker).history(
        start=first.isoformat(), end=last.isoformat(), interval="1d", auto_adjust=False
    )
    if hist is None or hist.empty:
        raise SystemExit(f"FATAL: yfinance returned no history for {ticker} — cannot ground the probe")
    closes: dict[tuple[int, int], float] = {}
    for ts, row in hist.iterrows():
        key = (ts.year, ts.month)
        if key in months:
            closes[key] = float(row["Close"])  # last write per month wins = month-end close
    return closes


def ask(
    client: httpx.Client, prompt: str, disable_thinking: bool,
    model: str, base_url: str, max_tokens: int = 900,
) -> str:
    body = {
        "model": model,
        "temperature": 0,
        # CR217 — 900 was sized for a NON-reasoning server and silently breaks
        # on a reasoning one. GLM-5.3 spends ~1,000 tokens on an invisible
        # preamble before its first visible character, so at 900 every probe
        # returns empty content, `parse_estimate` reads empty as UNKNOWN, and
        # UNKNOWN is scored as a refusal — the probe would report that the model
        # knows nothing about any month, and hand back a "collapse" at the very
        # first one. A cutoff probe that cannot see the model's answers cannot
        # measure its cutoff.
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if disable_thinking:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    # CR217 — retry, because one timeout used to lose the whole probe. This is
    # 200+ sequential calls and the previous version raised out of the loop on
    # the first `httpx.ReadTimeout`, discarding every measurement taken so far.
    # A reasoning model also makes the old 180s budget tight: it spends its
    # decode budget on invisible thinking before the answer, so a probe call
    # costs far more wall-clock than its short reply suggests.
    last: Exception | None = None
    for attempt in range(3):
        try:
            r = client.post(f"{base_url}/v1/chat/completions", json=body, timeout=420)
            r.raise_for_status()
            msg = r.json()["choices"][0]["message"]
            # A reasoning model may put its chain-of-thought in `reasoning` or
            # `reasoning_content` depending on the server build; neither is the
            # answer. GLM-5.3 uses `reasoning`, which is why a probe reading only
            # `reasoning_content` sees an empty turn and calls it a refusal.
            return msg.get("content") or ""
        except Exception as exc:  # noqa: BLE001 — any transport fault is retryable here
            last = exc
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
    # Exhausted: report it as an unanswered probe rather than killing the run.
    # An UNKNOWN is scored as a refusal, which is the conservative direction —
    # it can only pull the collapse month EARLIER, never later, so it cannot
    # manufacture a wider valid window than the model has earned.
    print(f"  !! probe failed after 3 attempts ({type(last).__name__}); scoring UNKNOWN")
    return "UNKNOWN"


def parse_estimate(text: str) -> float | None:
    """Return the model's numeric estimate, or None for UNKNOWN/unparseable."""
    cleaned = _THINK_RE.sub("", text).strip()
    if "UNKNOWN" in cleaned.upper():
        return None
    nums = _NUM_RE.findall(cleaned)
    if not nums:
        return None
    return float(nums[-1].replace(",", ""))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="directory for the probe report")
    ap.add_argument("--sleep", type=float, default=0.5)
    ap.add_argument("--base-url", default=DEFAULT_VLLM_BASE_URL,
                    help="OpenAI-compatible host to probe (no trailing /v1).")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help="Model id to request. See --stamp-suffix for report naming.")
    ap.add_argument("--max-tokens", type=int, default=900,
                    help="Decode budget per probe. Raise well above the model's "
                         "thinking preamble for a REASONING model, or every "
                         "answer comes back empty and scores as a refusal.")
    ap.add_argument("--stamp-suffix", default="",
                    help="Appended to the report filename, so probing a second "
                         "model does not overwrite the first one's report.")
    args = ap.parse_args()
    base_url = args.base_url.rstrip("/")

    # CLAUDE.md: the `ami-llm` alias was REUSED across the CR211 model swap and
    # now names a different model than it did before 2026-08-28, so a report
    # keyed to the requested id can silently mis-attribute a measurement to the
    # wrong model. Record what the server says it is actually serving.
    try:
        served_root = httpx.get(f"{base_url}/v1/models", timeout=15).json()["data"][0]
        served_identity = served_root.get("root") or served_root.get("id")
    except Exception as exc:  # noqa: BLE001 — an unidentifiable server is reportable, not fatal
        served_identity = f"UNIDENTIFIED ({type(exc).__name__})"
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    months = month_range(START_MONTH, END_MONTH)
    truth: dict[str, dict[tuple[int, int], float]] = {}
    for t in ANCHORS:
        truth[t] = month_end_closes(t, months)
        print(f"[truth] {t}: {len(truth[t])}/{len(months)} month-end closes", flush=True)

    client = httpx.Client()
    disable_thinking = True
    records = []
    for y, m in months:
        month_name = dt.date(y, m, 1).strftime("%B")
        for ticker, name in ANCHORS.items():
            actual = truth[ticker].get((y, m))
            if actual is None:
                continue
            prompt = PROMPT.format(name=name, ticker=ticker, month_name=month_name, year=y)
            try:
                text = ask(client, prompt, disable_thinking, args.model, base_url,
                           args.max_tokens)
            except httpx.HTTPStatusError as e:
                if disable_thinking and e.response.status_code == 400:
                    # server rejects chat_template_kwargs — fall back for the whole run
                    disable_thinking = False
                    text = ask(client, prompt, disable_thinking, args.model, base_url,
                           args.max_tokens)
                else:
                    raise
            est = parse_estimate(text)
            rel_err = abs(est - actual) / actual if est is not None else None
            records.append(
                {
                    "ticker": ticker,
                    "year": y,
                    "month": m,
                    "actual": round(actual, 2),
                    "estimate": est,
                    "rel_err": round(rel_err, 4) if rel_err is not None else None,
                    "raw": _THINK_RE.sub("", text).strip()[:200],
                }
            )
            print(
                f"[probe] {y}-{m:02d} {ticker}: actual={actual:.2f} est={est} "
                f"err={f'{rel_err:.1%}' if rel_err is not None else 'UNKNOWN'}",
                flush=True,
            )
            time.sleep(args.sleep)

    per_month = []
    for y, m in months:
        rows = [r for r in records if (r["year"], r["month"]) == (y, m)]
        if not rows:
            continue
        errs = [r["rel_err"] for r in rows if r["rel_err"] is not None]
        refusals = sum(1 for r in rows if r["estimate"] is None)
        med = statistics.median(errs) if errs else None
        failing = (med is None or med > ERR_THRESHOLD) or (refusals / len(rows) >= REFUSAL_THRESHOLD)
        per_month.append(
            {
                "month": f"{y}-{m:02d}",
                "median_rel_err": round(med, 4) if med is not None else None,
                "refusal_rate": round(refusals / len(rows), 2),
                "n": len(rows),
                "failing": failing,
            }
        )

    event_results = []
    for key, event, truth_month, category in EVENT_PROBES:
        text = ask(client, EVENT_PROMPT.format(event=event), disable_thinking,
                   args.model, base_url, args.max_tokens)
        cleaned = _THINK_RE.sub("", text).strip()
        m = _MONTH_RE.search(cleaned)
        answered = None if "UNKNOWN" in cleaned.upper() or not m else f"{int(m.group(1))}-{int(m.group(2)):02d}"
        ty, tm = (int(x) for x in truth_month.split("-"))
        correct = False
        if answered:
            ay, am = (int(x) for x in answered.split("-"))
            correct = abs((ay * 12 + am) - (ty * 12 + tm)) <= 1
        event_results.append(
            {"key": key, "category": category, "truth": truth_month,
             "answered": answered, "correct": correct, "raw": cleaned[:120]}
        )
        print(f"[event] {key} ({truth_month}): answered={answered} correct={correct}", flush=True)
        time.sleep(args.sleep)

    baseline_events = [e for e in event_results if e["category"] == "baseline"]
    baseline_recall = sum(e["correct"] for e in baseline_events) / max(len(baseline_events), 1)
    known_boundary = [e["truth"] for e in event_results if e["category"] == "boundary" and e["correct"]]
    last_known_event = max(known_boundary) if known_boundary else None

    collapse = None
    for i in range(len(per_month) - 1):
        if per_month[i]["failing"] and per_month[i + 1]["failing"]:
            collapse = per_month[i]["month"]
            break
    if collapse is None and per_month and per_month[-1]["failing"]:
        collapse = per_month[-1]["month"]

    if baseline_recall < 0.75:
        print(
            f"FATAL: baseline event recall is {baseline_recall:.0%} — the model fails "
            "events it must know, so refusals cannot be read as a knowledge boundary. "
            "The probe design is invalid for this model; do NOT pick a window start.",
            file=sys.stderr,
        )
        collapse = None

    if collapse is None:
        print(
            "FATAL: no valid collapse month — extend the probe or fix the design; "
            "do NOT pick a window start by hand.",
            file=sys.stderr,
        )
        window_start = None
    else:
        # The window must clear BOTH the price-collapse month and the last event
        # the model recalls — whichever is later.
        anchor_month = max(collapse, last_known_event) if last_known_event else collapse
        cy, cm = (int(x) for x in anchor_month.split("-"))
        anchor = dt.date(cy, cm, 1) + dt.timedelta(days=MARGIN_DAYS)
        window_start = (anchor + dt.timedelta(days=(4 - anchor.weekday()) % 7)).isoformat()  # first Friday

    stamp = dt.date.today().isoformat()
    result = {
        "probed_at": stamp,
        "model": args.model,
        "served_identity": served_identity,
        "vllm_base_url": base_url,
        "criteria": {
            "err_threshold": ERR_THRESHOLD,
            "refusal_threshold": REFUSAL_THRESHOLD,
            "margin_days": MARGIN_DAYS,
        },
        "collapse_month": collapse,
        "baseline_event_recall": round(baseline_recall, 2),
        "last_known_event": last_known_event,
        "window_start": window_start,
        "per_month": per_month,
        "events": event_results,
        "records": records,
    }
    name = f"cutoff_probe_{stamp}{args.stamp_suffix}"
    (out_dir / f"{name}.json").write_text(json.dumps(result, indent=2))

    lines = [
        f"# CR164 model-cutoff probe — {stamp}",
        "",
        f"Model `{args.model}` (server reports `{served_identity}`) at "
        f"`{base_url}`. {len(records)} probes over "
        f"{len(per_month)} months × {len(ANCHORS)} anchors, temperature 0.",
        "",
        f"**Price-collapse month: {collapse}** · baseline event recall {baseline_recall:.0%} · "
        f"last recalled boundary event: **{last_known_event or 'none'}**",
        "",
        f"**window_start (first Friday ≥ max(collapse, last event) + 8w): {window_start}**",
        "",
        "| Event | truth | answered | correct |",
        "|---|---|---|---|",
        *[f"| {e['key']} ({e['category']}) | {e['truth']} | {e['answered'] or 'UNKNOWN'} | "
          f"{'✓' if e['correct'] else '✗'} |" for e in event_results],
        "",
        "| Month | median rel err | refusal rate | failing |",
        "|---|---|---|---|",
    ]
    for pm in per_month:
        err = f"{pm['median_rel_err']:.1%}" if pm["median_rel_err"] is not None else "—"
        lines.append(f"| {pm['month']} | {err} | {pm['refusal_rate']:.0%} | {'YES' if pm['failing'] else ''} |")
    (out_dir / f"{name}.md").write_text("\n".join(lines) + "\n")
    print(f"\n[done] collapse={collapse} window_start={window_start} → {out_dir}", flush=True)


if __name__ == "__main__":
    main()
