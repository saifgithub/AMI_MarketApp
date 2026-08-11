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
        # DEF256 — `strict=False` permits raw control characters INSIDE strings.
        # Nothing else is relaxed: trailing commas, single quotes and unquoted
        # keys still fail, so a genuinely malformed object is still rejected.
        #
        # Under the default `strict=True`, a model that writes a real line break
        # inside a string value instead of the two characters \n makes the WHOLE
        # object unparseable — and for the PM verdict that is not a degraded
        # read, it is a discarded decision: `_parse_pm_verdict` returns no
        # verdict and the caller fails safe to PASS (DEF059), so a real APPROVE
        # is lost over a whitespace character. DEF236 made this reachable by
        # design when it asked the PM for bullets inside `narration`; the prompt
        # also asks for \n, but P2 is explicit that a prompt instruction is not
        # a control, so this is the control.
        return json.loads(candidate, strict=False)
    except json.JSONDecodeError:
        return None
