"""Role persona-stability eval.

Two probes against a Qwen LoRA candidate served by vLLM:

1. PERSONA STABILITY — given the role's base prompt + a 200-row generic
   finance question probe, do the model's outputs resemble the role's
   Claude Opus reference outputs?
   Metric: mean cosine similarity (sentence-transformers) over 200 rows.
   Gate: >= 0.75.

2. MANDATE SENSITIVITY — given a fixed ticker, does the model produce
   materially different output under 5 different mandates?
   Metric: pairwise embedding distance between same-mandate pairs vs.
   cross-mandate pairs. Cross > same.
   Gate: passes when the cross-mandate centroid distance > intra-mandate
   centroid distance.

Both probes assume a vLLM endpoint at $VLLM_BASE_URL (default
http://192.168.20.74:8001/v1) with the LoRA loaded as an adapter named
after the role.

The Claude Opus reference probe (200 rows) is NOT in this repo — it's
generated separately and parked at /raid/silent_scout/eval/<role>_opus_ref.jsonl
to keep the repo size sane. Format expected: {"prompt": "...", "opus_output": "..."}.

Run:
    python Silent_Scout/04_eval/role_persona_eval.py --role concierge
    python Silent_Scout/04_eval/role_persona_eval.py --role fundamentals_analyst --probe sensitivity
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from statistics import mean

import requests

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(ROOT / "02_data" / "recipes"))

from app.agents.overlay_generator import generate_overlay  # noqa: E402
from app.schemas import AgentId  # noqa: E402
from _seed_mandates import all_mandates  # noqa: E402

VLLM_BASE = os.environ.get("VLLM_BASE_URL", "http://192.168.20.74:8001/v1")
OPUS_REF_DIR = Path(os.environ.get("OPUS_REF_DIR", "/raid/silent_scout/eval"))

PERSONA_GATE = 0.75


_embedder = None


def _embed_batch(texts: list[str]):
    global _embedder
    from sentence_transformers import SentenceTransformer
    if _embedder is None:
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder.encode(texts, convert_to_numpy=True, normalize_embeddings=True)


def _generate(model: str, system: str, user: str, max_tokens: int = 512) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    r = requests.post(f"{VLLM_BASE}/chat/completions", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _role_id_to_agent(role: str) -> AgentId:
    return AgentId(role)


def _load_base_prompt(role: str) -> str:
    return (REPO_ROOT / "content" / "agents" / f"{role}.md").read_text()


def _load_opus_reference(role: str) -> list[dict]:
    p = OPUS_REF_DIR / f"{role}_opus_ref.jsonl"
    if not p.exists():
        raise FileNotFoundError(
            f"Opus reference probe not found at {p}. "
            "Generate via Distilabel + Claude Opus (deferred — see datasets.md §Opus distillation)."
        )
    with p.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def probe_persona_stability(role: str, lora_model_name: str) -> int:
    base_prompt = _load_base_prompt(role)
    ref = _load_opus_reference(role)

    lora_outputs: list[str] = []
    opus_outputs: list[str] = []
    for row in ref:
        prompt = row["prompt"]
        lora_outputs.append(_generate(lora_model_name, base_prompt, prompt))
        opus_outputs.append(row["opus_output"])

    a = _embed_batch(lora_outputs)
    b = _embed_batch(opus_outputs)
    sims = (a * b).sum(axis=1).tolist()
    score = mean(sims)
    print(f"[persona] role={role}  N={len(ref)}  mean_cos={score:.4f}  gate={PERSONA_GATE}")
    if score < PERSONA_GATE:
        print("FAIL")
        return 1
    print("PASS")
    return 0


def probe_mandate_sensitivity(role: str, lora_model_name: str, ticker: str = "AAPL") -> int:
    """For a fixed ticker, generate output under each of the 5 seed mandates twice.
    Check that intra-mandate distance < cross-mandate distance."""
    import numpy as np

    base_prompt = _load_base_prompt(role)
    agent = _role_id_to_agent(role)
    mandates = all_mandates()
    overlays = [generate_overlay(agent, m) for m in mandates]

    user_template = (
        "{overlay}\n\n"
        f"Please give your read on {ticker} for me, given this mandate."
    )

    outputs: list[str] = []
    labels: list[int] = []
    for i, overlay in enumerate(overlays):
        for _ in range(2):
            outputs.append(_generate(lora_model_name, base_prompt, user_template.format(overlay=overlay)))
            labels.append(i)

    emb = _embed_batch(outputs)
    intra = []
    cross = []
    for i in range(len(outputs)):
        for j in range(i + 1, len(outputs)):
            d = 1 - float(np.dot(emb[i], emb[j]))
            (intra if labels[i] == labels[j] else cross).append(d)

    intra_m = mean(intra) if intra else 0.0
    cross_m = mean(cross) if cross else 0.0
    print(f"[sensitivity] role={role}  intra={intra_m:.4f}  cross={cross_m:.4f}")
    if cross_m <= intra_m:
        print("FAIL — mandate does not materially change output")
        return 1
    print("PASS")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--role", required=True, help="e.g. concierge | fundamentals_analyst")
    p.add_argument("--probe", choices=["persona", "sensitivity"], default="persona")
    p.add_argument("--model", default=None, help="vLLM model name (default = role id)")
    p.add_argument("--ticker", default="AAPL")
    args = p.parse_args()

    model = args.model or args.role
    if args.probe == "persona":
        return probe_persona_stability(args.role, model)
    return probe_mandate_sensitivity(args.role, model, args.ticker)


if __name__ == "__main__":
    raise SystemExit(main())
