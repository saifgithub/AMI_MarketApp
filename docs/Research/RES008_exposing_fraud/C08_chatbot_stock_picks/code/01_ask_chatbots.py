"""C08 parts 2 and 3 — put the pre-registered prompts to three chatbots, ten fresh runs each.

Prompts are verbatim from PREREGISTRATION.md (commit 3ac320eb). Raw replies land in
out/responses/; nothing is parsed here so the record of what was said stays untouched.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from common.ask_chatbot import MODELS, ask_many  # noqa: E402

PROMPTS = {
    "now": "I would like to outperform the S&P 500 in the next year. Can you propose 10 stocks I should buy?",
    "asof2019": (
        "It is January 2, 2019. I would like to outperform the S&P 500 over the next five years. "
        "Can you propose 10 stocks I should buy? Answer as of that date."
    ),
}
RUNS = 10

jobs = [
    {"name": f"{key}_{model}_{run:02d}", "model": model, "prompt": prompt}
    for key, prompt in PROMPTS.items()
    for model in MODELS
    for run in range(1, RUNS + 1)
]
ask_many(jobs, Path(__file__).resolve().parents[1] / "out" / "responses", workers=5)
