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

VLLM_BASE_URL = "http://192.168.20.74:8000"
MODEL = "ami-llm"

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


def ask(client: httpx.Client, prompt: str, disable_thinking: bool) -> str:
    body = {
        "model": MODEL,
        "temperature": 0,
        "max_tokens": 900,
        "messages": [{"role": "user", "content": prompt}],
    }
    if disable_thinking:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    r = client.post(f"{VLLM_BASE_URL}/v1/chat/completions", json=body, timeout=180)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"] or ""


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
    args = ap.parse_args()
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
                text = ask(client, prompt, disable_thinking)
            except httpx.HTTPStatusError as e:
                if disable_thinking and e.response.status_code == 400:
                    # server rejects chat_template_kwargs — fall back for the whole run
                    disable_thinking = False
                    text = ask(client, prompt, disable_thinking)
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
        text = ask(client, EVENT_PROMPT.format(event=event), disable_thinking)
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
        "model": MODEL,
        "vllm_base_url": VLLM_BASE_URL,
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
    (out_dir / f"cutoff_probe_{stamp}.json").write_text(json.dumps(result, indent=2))

    lines = [
        f"# CR164 model-cutoff probe — {stamp}",
        "",
        f"Model `{MODEL}` at `{VLLM_BASE_URL}`. {len(records)} probes over "
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
    (out_dir / f"cutoff_probe_{stamp}.md").write_text("\n".join(lines) + "\n")
    print(f"\n[done] collapse={collapse} window_start={window_start} → {out_dir}", flush=True)


if __name__ == "__main__":
    main()
