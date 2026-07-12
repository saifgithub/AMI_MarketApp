"""fundamentals_analyst data recipe.

Builds an SFT JSONL for the fundamentals_analyst LoRA from public HF datasets:

- next-tat/TAT-QA — financial QA over real SEC filings (numerical reasoning)
- ibm-research/finqa — QA over 2.8k financial reports
- kurry/sp500_earnings_transcripts — earnings transcripts (excerpts only)

Plus a ~8% replay mix from HuggingFaceH4/ultrachat_200k.

CRITICAL PATTERN: every example renders a mandate overlay into the USER side
of the prompt (rotating through the 5 seed mandates) so the LoRA learns the
overlay is data it adapts to, not weights it memorises.

Output: chat-style JSONL.

Run on the GB10 (research-only). Reads, never writes, backend/.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from datasets import load_dataset

ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.agents.overlay_generator import generate_overlay  # noqa: E402
from app.schemas import AgentId  # noqa: E402
from _seed_mandates import all_mandates  # noqa: E402

AGENT_ID = AgentId.FUNDAMENTALS_ANALYST
OUT_DIR = ROOT / "02_data" / "processed" / "fundamentals_analyst"
SAMPLE_DIR = ROOT / "02_data" / "samples"
BASE_PROMPT = (REPO_ROOT / "content" / "agents" / "fundamentals_analyst.md").read_text()

TARGET_TOTAL = 20_000
REPLAY_FRACTION = 0.08
SEED = 42


def _tatqa_example(record: dict, overlays: list[str], rng: random.Random) -> dict | None:
    question = record.get("question")
    answer = record.get("answer")
    table = record.get("table")
    paragraphs = record.get("paragraphs") or []
    if not question or answer is None:
        return None
    context_blocks = []
    if table:
        context_blocks.append("Table:\n" + json.dumps(table)[:2000])
    if paragraphs:
        context_blocks.append("Notes:\n" + "\n".join(paragraphs)[:2000])
    context = "\n\n".join(context_blocks) or "(no additional context)"
    overlay = rng.choice(overlays)
    return {
        "messages": [
            {"role": "system", "content": BASE_PROMPT},
            {
                "role": "user",
                "content": (
                    f"{overlay}\n\n"
                    f"{context}\n\nQuestion: {question}"
                ),
            },
            {"role": "assistant", "content": str(answer)},
        ],
    }


def _finqa_example(record: dict, overlays: list[str], rng: random.Random) -> dict | None:
    question = record.get("question")
    answer = record.get("answer") or record.get("final_result")
    pre_text = record.get("pre_text") or []
    post_text = record.get("post_text") or []
    table = record.get("table")
    if not question or answer is None:
        return None
    pre = "\n".join(pre_text)[:1500] if isinstance(pre_text, list) else str(pre_text)[:1500]
    post = "\n".join(post_text)[:1500] if isinstance(post_text, list) else str(post_text)[:1500]
    tbl = json.dumps(table)[:2000] if table else ""
    overlay = rng.choice(overlays)
    return {
        "messages": [
            {"role": "system", "content": BASE_PROMPT},
            {
                "role": "user",
                "content": (
                    f"{overlay}\n\n"
                    f"Filing excerpt:\n{pre}\n\nTable:\n{tbl}\n\n{post}\n\n"
                    f"Question: {question}"
                ),
            },
            {"role": "assistant", "content": str(answer)},
        ],
    }


def _earnings_example(record: dict, overlays: list[str], rng: random.Random) -> dict | None:
    transcript = record.get("transcript") or record.get("text")
    ticker = record.get("ticker") or record.get("symbol") or "the company"
    if not transcript:
        return None
    excerpt = transcript[:4000]
    overlay = rng.choice(overlays)
    user = (
        f"{overlay}\n\n"
        f"Earnings call excerpt for {ticker}:\n\n{excerpt}\n\n"
        "Give a concise fundamental read: durable margins, risks, "
        "and whether this fits the mandate."
    )
    assistant = (
        "I'll structure this around the mandate's risk tolerance and horizon. "
        "Without the full filing context I can only flag what's visible in this excerpt — "
        "please pull the full 10-K before acting."
    )
    return {
        "messages": [
            {"role": "system", "content": BASE_PROMPT},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
    }


def _ultrachat_example(record: dict) -> dict | None:
    messages = record.get("messages")
    if not messages or len(messages) < 2:
        return None
    return {"messages": [{"role": "system", "content": BASE_PROMPT}, *messages[:6]]}


def build() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    overlays = [generate_overlay(AGENT_ID, m) for m in all_mandates()]

    out_path = OUT_DIR / "train.jsonl"
    target_replay = int(TARGET_TOTAL * REPLAY_FRACTION)
    target_per_source = (TARGET_TOTAL - target_replay) // 3

    n_tat = n_finqa = n_earn = n_replay = 0

    with out_path.open("w") as fh:
        for rec in load_dataset("next-tat/TAT-QA", split="train", streaming=True):
            if n_tat >= target_per_source:
                break
            ex = _tatqa_example(rec, overlays, rng)
            if ex:
                fh.write(json.dumps(ex) + "\n")
                n_tat += 1

        for rec in load_dataset("ibm-research/finqa", split="train", streaming=True):
            if n_finqa >= target_per_source:
                break
            ex = _finqa_example(rec, overlays, rng)
            if ex:
                fh.write(json.dumps(ex) + "\n")
                n_finqa += 1

        for rec in load_dataset("kurry/sp500_earnings_transcripts", split="train", streaming=True):
            if n_earn >= target_per_source:
                break
            ex = _earnings_example(rec, overlays, rng)
            if ex:
                fh.write(json.dumps(ex) + "\n")
                n_earn += 1

        for rec in load_dataset("HuggingFaceH4/ultrachat_200k", split="train_sft", streaming=True):
            if n_replay >= target_replay:
                break
            ex = _ultrachat_example(rec)
            if ex:
                fh.write(json.dumps(ex) + "\n")
                n_replay += 1

    with (SAMPLE_DIR / "fundamentals_analyst_sample.jsonl").open("w") as fh:
        with out_path.open() as src:
            for i, line in enumerate(src):
                if i >= 10:
                    break
                fh.write(line)

    total = n_tat + n_finqa + n_earn + n_replay
    print(
        f"Wrote {out_path} — tat={n_tat} finqa={n_finqa} "
        f"earnings={n_earn} replay={n_replay} total={total}"
    )


if __name__ == "__main__":
    build()
