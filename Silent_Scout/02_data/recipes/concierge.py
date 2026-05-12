"""Concierge data recipe.

Builds an SFT JSONL for the Concierge LoRA from two public HF datasets:

- Josephgflowers/Finance-Instruct-500k — filtered to onboarding/explainer turns
- argilla/FinePersonas-v0.1 — sampled for empathetic-coach persona grounding

Plus a ~10% replay mix from HuggingFaceH4/ultrachat_200k to prevent
catastrophic forgetting of general instruction-following.

Output format: chat-style JSONL, one example per line:

    {
      "messages": [
        {"role": "system", "content": "<concierge.md>"},
        {"role": "user",   "content": "<concierge product-context overlay>\\n\\n<user turn>"},
        {"role": "assistant", "content": "<assistant turn>"}
      ]
    }

Note: For Concierge the overlay is the product-context overlay, NOT the
trading mandate overlay. See backend/app/agents/overlay_generator.py.

Run on the GB10 (research-only). Never imports from mobile/.
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

from app.agents.overlay_generator import generate_overlay  # noqa: E402
from app.schemas import AgentId  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _seed_mandates import default_conservative  # noqa: E402

OUT_DIR = ROOT / "02_data" / "processed" / "concierge"
SAMPLE_DIR = ROOT / "02_data" / "samples"
BASE_PROMPT = (REPO_ROOT / "content" / "agents" / "concierge.md").read_text()

TARGET_TOTAL = 30_000
REPLAY_FRACTION = 0.08
SEED = 42


def _load_concierge_seed_mandate():
    """Concierge uses a generic product-context overlay; mandate fields don't
    drive its overlay shape, but we still pass a valid Mandate so the
    generator function is exercised end-to-end."""
    return default_conservative()


def _is_onboarding_shape(record: dict) -> bool:
    """Filter Finance-Instruct-500k to onboarding/explainer-style turns."""
    text = (record.get("user", "") + " " + record.get("assistant", "")).lower()
    onboarding_markers = (
        "what is", "explain", "beginner", "first time", "start investing",
        "open an account", "risk tolerance", "diversification", "compound",
        "etf vs", "stock vs", "how do i", "should i", "long term",
    )
    return any(m in text for m in onboarding_markers)


def _example_from_finance_instruct(record: dict, overlay: str) -> dict | None:
    user = record.get("user") or record.get("instruction") or record.get("question")
    assistant = record.get("assistant") or record.get("output") or record.get("answer")
    if not user or not assistant:
        return None
    return {
        "messages": [
            {"role": "system", "content": BASE_PROMPT},
            {"role": "user", "content": f"{overlay}\n\n{user}"},
            {"role": "assistant", "content": assistant},
        ],
    }


def _example_from_persona(record: dict, overlay: str) -> dict | None:
    persona = record.get("persona") or record.get("description")
    if not persona:
        return None
    user_turn = (
        "I'm new to investing. Here's a bit about me:\n\n"
        f"{persona}\n\n"
        "How should I think about getting started with AMI Trade?"
    )
    assistant_turn = (
        "Welcome — let's start from where you are. Based on what you've shared, "
        "I'd suggest we walk through three things together: your goals, your "
        "comfort with risk, and the time you have. There's no rush. "
        "Whenever you're ready, tell me what kind of outcome would feel like a "
        "win to you a year from now."
    )
    return {
        "messages": [
            {"role": "system", "content": BASE_PROMPT},
            {"role": "user", "content": f"{overlay}\n\n{user_turn}"},
            {"role": "assistant", "content": assistant_turn},
        ],
    }


def _example_from_ultrachat(record: dict) -> dict | None:
    messages = record.get("messages")
    if not messages or len(messages) < 2:
        return None
    return {"messages": [{"role": "system", "content": BASE_PROMPT}, *messages[:6]]}


def build() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    random.seed(SEED)

    overlay = generate_overlay(AgentId.CONCIERGE, _load_concierge_seed_mandate())

    finance = load_dataset(
        "Josephgflowers/Finance-Instruct-500k", split="train", streaming=True,
    )
    personas = load_dataset(
        "argilla/FinePersonas-v0.1", split="train", streaming=True,
    )
    ultrachat = load_dataset(
        "HuggingFaceH4/ultrachat_200k", split="train_sft", streaming=True,
    )

    out_path = OUT_DIR / "train.jsonl"
    n_main = 0
    n_persona = 0
    n_replay = 0
    target_replay = int(TARGET_TOTAL * REPLAY_FRACTION)
    target_persona = int(TARGET_TOTAL * 0.10)
    target_main = TARGET_TOTAL - target_replay - target_persona

    with out_path.open("w") as fh:
        for rec in finance:
            if n_main >= target_main:
                break
            if not _is_onboarding_shape(rec):
                continue
            ex = _example_from_finance_instruct(rec, overlay)
            if ex is None:
                continue
            fh.write(json.dumps(ex) + "\n")
            n_main += 1

        for rec in personas:
            if n_persona >= target_persona:
                break
            ex = _example_from_persona(rec, overlay)
            if ex is None:
                continue
            fh.write(json.dumps(ex) + "\n")
            n_persona += 1

        for rec in ultrachat:
            if n_replay >= target_replay:
                break
            ex = _example_from_ultrachat(rec)
            if ex is None:
                continue
            fh.write(json.dumps(ex) + "\n")
            n_replay += 1

    with (SAMPLE_DIR / "concierge_sample.jsonl").open("w") as fh:
        with out_path.open() as src:
            for i, line in enumerate(src):
                if i >= 10:
                    break
                fh.write(line)

    print(
        f"Wrote {out_path} — main={n_main} persona={n_persona} "
        f"replay={n_replay} total={n_main + n_persona + n_replay}"
    )


if __name__ == "__main__":
    build()
