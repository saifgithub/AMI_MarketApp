"""CR143 — an independent model reads our assembled agent prompts and attacks them.

Every reading of these prompts so far has been by someone who knows what they were
meant to say. That is the weakness CR105's Amendment 1 documents: its findings came
from a read of `content/agents/*.md`, and two of four were wrong once checked
against the code that parses the model's output. An outside reader with no access
to our intentions and no access to our code is a different instrument — it can only
see what the prompt actually says.

So the input is the ASSEMBLED prompt (`dump_assembled_prompts.py`), never the base
file, and the questions are falsifiable: name a contradiction and quote both sides,
name an unfollowable instruction and quote it. **Every claim must carry a verbatim
quote**, because the output of this script is a HYPOTHESIS LIST, not findings. Each
one still has to survive the supplier check and the parser check before it becomes
a defect — the reviewer cannot see `enforce_safety_floor`, so it will confidently
report that our deterministic compliance gate does not exist.

The first run proved the instrument on itself: of eight contradictions it found in
the PM prompt, three were bugs in the dump FIXTURE (a portfolio listing the convened
ticker as held while also claiming a 0% position in it, percentages that did not sum,
and sector weights passed as percentages into a formatter that multiplies by 100 —
"Cash 5180%"). The `--verify` faithfulness check had passed all three, because it
compares layer order and segment sizes, not whether the content makes sense.

Reads KIMI_API_KEY / KIMI_BASE_URL / KIMI_MODEL from the environment (they live in
melehost's .env). Kimi is a reasoning model whose chain-of-thought shares the token
budget — CR130's trap, and why max_tokens is 16k here: at 64 the entire budget goes
to reasoning and the reply comes back empty.

Usage (from backend/):
    KIMI_API_KEY=$(ssh melehost "grep '^KIMI_API_KEY=' ~/ami_trade/.env | cut -d= -f2-") \\
      .venv/bin/python -m scripts.kimi_prompt_review --surface room
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSEMBLED = REPO_ROOT / "docs/forward_planning/CR143_agent_prompt_audit/assembled"
DEFAULT_OUT = REPO_ROOT / "docs/forward_planning/CR143_agent_prompt_audit/external_review"

_SYSTEM = (
    "You are auditing a production LLM system prompt. Be specific and adversarial. "
    "Every criticism MUST quote the exact substring you object to, verbatim, so it can "
    "be verified against the source. If you cannot quote it, do not claim it. Do not "
    "rate anything out of 10. Prefer five sharp findings over twenty weak ones."
)

_TEMPLATE = """Below is the COMPLETE system prompt sent to the "{agent}" agent in a 12-agent LLM
trading-education simulator. The user is a student; the product teaches how a professional
investment process reasons. It is simulation-only — no real money, no brokerage, and the
system is not licensed to give investment advice. Eleven agents write prose that is shown to
the user and passed to later agents; the Portfolio Manager speaks last and its JSON verdict
is the binding output.

You are seeing ONE agent's prompt in isolation. The transcript is empty because this agent is
being shown as if it speaks first; do not report the empty transcript itself as a defect.

Answer these, in order, as markdown:

1. JOB — in one sentence, what is this agent supposed to produce?
2. CONTRADICTIONS — places where two parts of this prompt tell the model different things.
   Quote both sides of each.
3. UNFOLLOWABLE — instructions the model cannot comply with, or that depend on data the
   prompt does not contain. Quote each.
4. FAILURE MODES — the 3 most likely ways a competent model produces a BAD output from this
   exact prompt. Be concrete about what the bad output looks like.
5. CUT — this prompt is {chars:,} characters. Quote what you would delete as noise, and say
   what is load-bearing and must stay.

--- BEGIN PROMPT ---
{prompt}
--- END PROMPT ---"""


def _call(prompt_text: str, agent: str, max_tokens: int, timeout: int) -> dict:
    body = json.dumps({
        "model": os.environ.get("KIMI_MODEL", "kimi-for-coding"),
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _TEMPLATE.format(
                agent=agent.replace("_", " ").title(),
                chars=len(prompt_text), prompt=prompt_text)},
        ],
    }).encode()
    base = os.environ.get("KIMI_BASE_URL", "https://api.kimi.com/coding").rstrip("/")
    req = urllib.request.Request(
        f"{base}/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {os.environ['KIMI_API_KEY']}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def review_one(path: Path, out_dir: Path, timeout: int,
               max_tokens: int = 24000, attempts: int = 3) -> tuple[str, str]:
    """One review, retried.

    Two failure modes seen in the first full run, both handled here rather than
    left to kill the pool:
      * `ConnectionResetError` — an OSError, NOT a `urllib.error.URLError`, so the
        original handler missed it and the unhandled raise inside
        `ThreadPoolExecutor.map` aborted every remaining review.
      * an empty `content` with `reasoning_tokens` equal to the whole budget. Kimi
        is a reasoning model sharing one budget between thought and answer (CR130);
        at 16k the longest prompts think until there is nothing left to answer with.
        Retry doubles the budget rather than reporting a false "no findings".
    """
    agent = path.stem
    prompt = path.read_text(encoding="utf-8")
    data: dict = {}
    last = ""
    for attempt in range(attempts):
        budget = max_tokens * (2 ** attempt)
        try:
            data = _call(prompt, agent, budget, timeout)
        except (OSError, TimeoutError, json.JSONDecodeError) as exc:
            last = f"{type(exc).__name__}: {exc}"
            continue
        if "choices" not in data:
            last = json.dumps(data)[:300]
            continue
        if (data["choices"][0]["message"].get("content") or "").strip():
            break
        last = ("empty content — reasoning consumed the whole budget of "
                f"{budget} tokens")
    else:
        return agent, f"<<REVIEW FAILED after {attempts} attempts: {last}>>"

    content = data["choices"][0]["message"].get("content") or ""
    usage = data.get("usage", {})
    header = (
        f"# External review — {agent}\n\n"
        f"> Reviewer: `{data.get('model')}` · reasoning tokens "
        f"{usage.get('completion_tokens_details', {}).get('reasoning_tokens', '?')} · "
        f"prompt {usage.get('prompt_tokens', '?')} tokens.\n"
        f"> **Hypotheses, not findings.** The reviewer cannot see our code; every claim "
        f"needs a supplier check and a parser check before it becomes a defect.\n\n"
    )
    (out_dir / f"{agent}.md").write_text(header + content, encoding="utf-8")
    return agent, content


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--surface", default="room",
                   choices=["room", "one_on_one", "concierge", "brief"])
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--only", default=None, help="comma-separated agent ids")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--timeout", type=int, default=900)
    args = p.parse_args()

    if not os.environ.get("KIMI_API_KEY"):
        print("KIMI_API_KEY not set (it lives in melehost's .env)", file=sys.stderr)
        return 2

    paths = sorted((ASSEMBLED / args.surface).glob("*.txt"))
    if args.only:
        keep = {s.strip() for s in args.only.split(",")}
        paths = [p for p in paths if p.stem in keep]
    if not paths:
        print(f"no prompts under {ASSEMBLED / args.surface}", file=sys.stderr)
        return 2

    out_dir = args.out or (DEFAULT_OUT / args.surface)
    out_dir.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for agent, content in pool.map(
            lambda q: review_one(q, out_dir, args.timeout), paths
        ):
            status = "FAILED" if content.startswith("<<REVIEW FAILED") else f"{len(content):,} chars"
            print(f"  {agent:24s} {status}")
    print(f"\nwrote {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
