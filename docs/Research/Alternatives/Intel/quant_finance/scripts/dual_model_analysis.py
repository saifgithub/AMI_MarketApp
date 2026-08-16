#!/usr/bin/env python3
"""
Send ONE identical fundamentals brief to BOTH local models and compare.

  Qwen3.6-35B-A3B-NVFP4   -> :8000  (ami-llm)          262K ctx
  Nemotron-3.5-Lightning  -> :8030  (nemotron-3.5-...)  65K ctx

Same data, same prompt, same temperature -- so any difference in output is the
model, not the input. Useful both for choosing a model and for cross-checking:
where two independent models agree on a reading of the numbers, confidence is
higher; where they diverge, that is a flag to inspect manually.

Usage:
    python3 dual_model_analysis.py AAPL
    python3 dual_model_analysis.py AAPL MSFT NVDA
    python3 dual_model_analysis.py AAPL --out /path/to/report.md
"""
import argparse
import concurrent.futures as cf
import sys
import time

import requests

sys.path.insert(0, "/opt/saiful/llm_research/quant_finance/scripts")
from fundamentals_llm2 import (          # reuse the audited collector
    from_yfinance, from_openbb, cross_verify, market_context,
    build_brief, SYSTEM, SINGLE, PEER,
)

# token_mult: Nemotron 3.5 Lightning is a reasoning model whose trace is
# charged against the SAME completion budget as the answer. At max_tokens=5000
# on a ~5.4K-char brief it spent the entire budget thinking and returned an
# EMPTY answer. It needs materially more headroom than Qwen (run with
# /no_think), so its budget is scaled up rather than shared.
MODELS = [
    {"name": "Qwen3.6-35B-A3B-NVFP4",
     "url": "http://localhost:8000/v1/chat/completions",
     "model": "ami-llm", "no_think": True, "token_mult": 1.0},
    {"name": "Nemotron-3.5-Lightning-30B-A3B",
     "url": "http://localhost:8030/v1/chat/completions",
     "model": "nemotron-3.5-lightning", "no_think": False, "token_mult": 3.0},
]


def ask(cfg, brief, peer, max_tokens):
    content = (PEER if peer else SINGLE).format(brief=brief)
    if cfg["no_think"]:
        content += "\n/no_think"
    max_tokens = int(max_tokens * cfg.get("token_mult", 1.0))
    t0 = time.time()
    try:
        r = requests.post(cfg["url"], json={
            "model": cfg["model"],
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": content}],
            "temperature": 0.3, "max_tokens": max_tokens,
        }, timeout=1800)
        r.raise_for_status()
        j = r.json()
        msg = j["choices"][0]["message"]
        text = msg.get("content") or ""
        reasoning = msg.get("reasoning") or msg.get("reasoning_content") or ""
        usage = j.get("usage", {})
        # A reasoning model can burn the whole budget on its trace and return
        # nothing. That is a failure, not a success -- surface it as one.
        finish = j["choices"][0].get("finish_reason")
        if not text.strip():
            return {"name": cfg["name"], "ok": False,
                    "text": f"[EMPTY ANSWER] finish_reason={finish}; "
                            f"{usage.get('completion_tokens')} completion tokens "
                            f"consumed (budget {max_tokens}). The reasoning trace "
                            f"exhausted the budget before an answer was emitted. "
                            f"Raise max_tokens or token_mult for this model.",
                    "reasoning": reasoning, "elapsed": time.time() - t0,
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens")}
        return {
            "name": cfg["name"], "ok": True, "text": text,
            "reasoning": reasoning, "elapsed": time.time() - t0,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        }
    except Exception as e:
        return {"name": cfg["name"], "ok": False,
                "text": f"[FAILED] {type(e).__name__}: {e}",
                "reasoning": "", "elapsed": time.time() - t0,
                "prompt_tokens": None, "completion_tokens": None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--max-tokens", type=int, default=5000)
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-market", action="store_true")
    args = ap.parse_args()

    briefs, conflicts_total = [], 0
    for tk in args.tickers:
        tk = tk.upper()
        try:
            y = from_yfinance(tk)
        except Exception as e:
            print(f"[FAILED]  {tk}: {e}", file=sys.stderr)
            continue
        ob = from_openbb(tk)
        agree, conflict = cross_verify(y["info"], ob)
        conflicts_total += len(conflict)
        mkt = None if args.no_market else market_context(y["hist"])
        briefs.append(build_brief({
            "ticker": tk, "info": y["info"], "openbb": ob,
            "market": mkt, "agree": agree, "conflict": conflict}))
        print(f"[fetched] {tk:6s} yfinance+OpenBB "
              f"({len(agree)} cross-checked, {len(conflict)} conflict(s))",
              file=sys.stderr)

    if not briefs:
        sys.exit("no data fetched")
    brief = "\n".join(briefs)
    peer = len(briefs) > 1
    print(f"[brief] {len(brief):,} chars | "
          f"{conflicts_total} data conflict(s) flagged to both models",
          file=sys.stderr)
    print(f"[querying {len(MODELS)} models in parallel]", file=sys.stderr)

    with cf.ThreadPoolExecutor(max_workers=len(MODELS)) as ex:
        results = list(ex.map(
            lambda c: ask(c, brief, peer, args.max_tokens), MODELS))

    lines = [f"# Dual-Model Fundamental Analysis: {', '.join(t.upper() for t in args.tickers)}",
             "",
             f"Identical brief ({len(brief):,} chars, {conflicts_total} data "
             f"conflict(s) flagged) sent to both models at temperature 0.3.",
             ""]
    for r in results:
        status = "OK" if r["ok"] else "FAILED"
        lines += [f"## {r['name']}", "",
                  f"*{status} | {r['elapsed']:.1f}s | "
                  f"prompt {r['prompt_tokens']} tok | "
                  f"completion {r['completion_tokens']} tok*", ""]
        if r["reasoning"]:
            lines += ["<details><summary>reasoning trace</summary>", "",
                      "```", r["reasoning"][:3000], "```", "", "</details>", ""]
        lines += [r["text"], "", "---", ""]

    report = "\n".join(lines)
    if args.out:
        with open(args.out, "w") as f:
            f.write(report)
        print(f"[written] {args.out}", file=sys.stderr)
    print(report)

    print("\n[timing]", file=sys.stderr)
    for r in results:
        print(f"  {r['name']:34s} {r['elapsed']:6.1f}s  "
              f"{'ok' if r['ok'] else 'FAILED'}", file=sys.stderr)


if __name__ == "__main__":
    main()
