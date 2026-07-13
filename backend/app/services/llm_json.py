"""Tolerant JSON extraction from LLM free-text output.

Shared by brief_engine.py (BriefProposal parsing) and room_runner.py
(Portfolio Manager verdict parsing, DEF056) — LLMs wrap JSON in ```json
fences, add leading/trailing prose, or otherwise don't return pure JSON.
"""

from __future__ import annotations

import json
import re


def extract_json_object(text: str) -> dict | None:
    """Extract the first JSON object found in `text`, tolerating ```json
    fences and surrounding prose. Returns None if nothing parses."""
    if not text:
        return None
    cleaned = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    candidate = m.group(1) if m else cleaned
    if not candidate.startswith("{"):
        first = candidate.find("{")
        last = candidate.rfind("}")
        if first == -1 or last == -1 or last <= first:
            return None
        candidate = candidate[first : last + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None
