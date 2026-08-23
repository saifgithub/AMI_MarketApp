#!/usr/bin/env python3
"""distill_teacher.py — CR196 recipe 10 stage 2: generate the long-form targets.

Reads the briefs `recipe10_longform_report.py --stage briefs` wrote, sends each to
an OpenAI-compatible endpoint serving **vanilla Fastino**, and appends one JSONL
record per candidate. `--stage assemble` then filters and ranks them; nothing here
judges quality, so this script stays dumb and restartable.

## The one hard rule, enforced structurally

Targets may come from open models or self-distilled Fastino, **never Claude** —
Anthropic's terms bar training a competing model on Claude outputs (CR196 §2
recipe 10). That is not left to a comment: `assert_not_anthropic()` refuses to run
against a host or model name that looks Anthropic-ish. Prompt instructions are not
controls (CR038) and neither are docstrings; this one is a check.

## Resumability

The output is append-only JSONL keyed by (ticker, candidate index). On restart the
script reads what is already there and asks only for what is missing. A run killed
at hour 6 of 9 resumes at hour 6 — which matters because the GPU is borrowed.

## Thinking must be OFF, and it is not off by default

The checkpoint's `chat_template.jinja` defaults `enable_thinking` to TRUE and emits an
OPEN `<think>` block; appending "/no_think" to the user turn does NOT override it
(measured in Phase 4 — `eval/basis/run_local_arm.py` carries the same finding and
asserts on it). The chat-completions endpoint applies the template SERVER-side, so
without an explicit override every target would arrive with reasoning text baked in,
and we would train on it. `chat_template_kwargs.enable_thinking=false` is sent on
every request and the response is checked for a leaked `<think>` block. This is a
P27-shaped trap: it runs green, returns fluent text, and quietly trains the wrong
thing.

## Decoding

Best-of-n needs variation, so this samples (temperature 0.7 by default) — unlike
every arm in `eval/basis/`, which is pinned to temperature 0 because §5a.1 requires
it for MEASUREMENT. Generation is not measurement. `--n 1 --temperature 0` gives a
deterministic single-shot run if that is wanted instead.

Usage (from the Mac, against a vLLM instance on the training box):
  python3 distill_teacher.py --base-url http://alpha-spark:8000/v1 \
      --model fastino-finance-bf16 --briefs out/recipe10_briefs.jsonl \
      --out out/recipe10_completions.jsonl --n 2 --concurrency 8 --limit 20

Run the --limit shakedown FIRST and read the reported throughput. The full-run cost
is that number times the ticker count; do not estimate it any other way.
"""
import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter

BANNED = re.compile(r"(anthropic|claude)", re.I)


def assert_not_anthropic(base_url, model):
    """Structural bar on the one teacher we may not distil from."""
    for label, value in (("base URL", base_url), ("model", model)):
        if BANNED.search(value or ""):
            raise SystemExit(
                f"REFUSING: {label} {value!r} looks like an Anthropic endpoint.\n"
                "CR196 §2 recipe 10: training targets may come from open models or "
                "self-distilled Fastino, never Claude — Anthropic's terms bar "
                "training a competing model on Claude outputs. If this is a "
                "false positive, rename the host; do not remove the check.")


def post(base_url, api_key, payload, timeout):
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key or 'none'}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    ap.add_argument("--briefs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=2, help="candidates per ticker")
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--top-p", type=float, default=0.95)
    ap.add_argument("--max-tokens", type=int, default=4000)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--limit", type=int, default=0, help="shakedown: first N tickers")
    args = ap.parse_args()

    assert_not_anthropic(args.base_url, args.model)

    briefs = [json.loads(l) for l in open(args.briefs)]
    # recipe-10 briefs carry status; the per-surface eval prompts do not (they are
    # rendered, not fetched). Absent status means "usable".
    briefs = [b for b in briefs if b.get("status", "ok") == "ok"]
    if args.limit:
        briefs = briefs[:args.limit]

    done = Counter()
    if os.path.exists(args.out):
        for line in open(args.out):
            try:
                done[json.loads(line)["ticker"]] += 1
            except Exception:
                continue
        print(f"[resume] {sum(done.values())} completions already on disk "
              f"across {len(done)} tickers")

    work = [(b, i) for b in briefs for i in range(args.n)
            if i >= done[b["ticker"]]]
    if not work:
        print("[done] nothing missing")
        return
    print(f"[gen] {len(work)} candidates over {len(briefs)} tickers · "
          f"n={args.n} temp={args.temperature} concurrency={args.concurrency}")

    lock = threading.Lock()
    out_f = open(args.out, "a")
    stats = Counter()
    t0 = time.time()

    def one(item):
        b, idx = item
        payload = {"model": args.model,
                   "messages": [{"role": "system", "content": b["system"]},
                                {"role": "user", "content": b["user"]}],
                   "temperature": args.temperature, "top_p": args.top_p,
                   "max_tokens": args.max_tokens, "seed": 1000 + idx,
                   "chat_template_kwargs": {"enable_thinking": False}}
        t1 = time.time()
        try:
            resp = post(args.base_url, args.api_key, payload, args.timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            with lock:
                stats[f"error:{type(e).__name__}"] += 1
            return
        ch = (resp.get("choices") or [{}])[0]
        msg = ch.get("message") or {}
        text = msg.get("content") or ""
        # Reasoning must not reach the target. If the server ignored the override,
        # stop the run rather than write thousands of contaminated targets.
        if "<think>" in text or msg.get("reasoning_content"):
            raise SystemExit(
                f"{b['ticker']}: response carries a <think> block or "
                "reasoning_content despite enable_thinking=false. The server "
                "ignored the override; fix that before generating targets, or "
                "every one of them trains reasoning text as report prose.")
        usage = resp.get("usage") or {}
        rec = {"ticker": b["ticker"], "candidate": idx, "text": text,
               **({"surface": b["surface"]} if "surface" in b else {}),
               "finish_reason": ch.get("finish_reason"),
               "completion_tokens": usage.get("completion_tokens"),
               "seconds": round(time.time() - t1, 1), "model": args.model,
               "temperature": args.temperature}
        with lock:
            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out_f.flush()
            stats["ok"] += 1
            stats[f"finish:{ch.get('finish_reason')}"] += 1
            n = stats["ok"]
            if n % 10 == 0 or n == 1:
                el = time.time() - t0
                print(f"  {n}/{len(work)}  {el / n:.1f}s/candidate  "
                      f"eta {(len(work) - n) * el / n / 60:.0f}m", flush=True)

    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        list(ex.map(one, work))
    out_f.close()

    el = time.time() - t0
    print(f"[gen] {stats['ok']}/{len(work)} in {el / 60:.1f}m "
          f"({el / max(stats['ok'], 1):.1f}s/candidate wall, "
          f"concurrency {args.concurrency})")
    for k in sorted(stats):
        print(f"  {k:28s} {stats[k]}")
    if stats["ok"]:
        rate = stats["ok"] / el
        print(f"[gen] MEASURED throughput {rate * 3600:.0f} candidates/hour — "
              f"multiply by your ticker count, do not extrapolate any other way")


if __name__ == "__main__":
    main()
