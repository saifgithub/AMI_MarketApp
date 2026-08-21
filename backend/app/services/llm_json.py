"""Tolerant JSON extraction from LLM free-text output.

Shared by brief_engine.py (BriefProposal parsing) and room_runner.py
(Portfolio Manager verdict parsing, DEF056) — LLMs wrap JSON in ```json
fences, add leading/trailing prose, or otherwise don't return pure JSON.
"""

from __future__ import annotations

import json
import re


def _close_truncated_object(candidate: str) -> str | None:
    """Rebuild a syntactically complete object from one the decoder ran out of.

    DEF258 — the PM's decode budget is a ceiling, and when it is reached the
    JSON stops mid-token: no closing quote, no closing brace. Every field is
    intact up to that point, so the DECISION (`action`, `size_pct`, the levels)
    is present and only the tail of the long trailing string is lost. Discarding
    it costs the whole verdict; closing it costs the tail of one sentence.

    Walks the string once tracking quote/escape state and brace depth, drops any
    trailing partial token, then closes the open string and the open containers.
    Returns None when the object was not in fact truncated (balanced already) or
    when nothing survives the trim — a genuinely malformed object must still be
    rejected, not guessed at.
    """
    in_string = False
    escaped = False
    stack: list[str] = []
    # The last prefix known to end on a COMPLETE member, with the container
    # stack as it stood there. Only commas and closers qualify: a bare `"` is
    # ambiguous — it closes keys as well as values, and cutting on a key's quote
    # yields `{"size_pct"}`, which is not JSON.
    safe: tuple[int, tuple[str, ...]] | None = None
    for i, ch in enumerate(candidate):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if in_string:
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
            safe = (i + 1, tuple(stack))
        elif ch == ",":
            safe = (i, tuple(stack))
    if not stack and not in_string and not escaped:
        return None

    if escaped:
        # A dangling backslash would escape the quote appended below.
        candidate = candidate[:-1]
        in_string = True

    if in_string:
        # Mid-sentence inside a string value — the common case, and the only one
        # where the clipped content is worth keeping: close the quote in place.
        repaired = candidate + '"'
        open_containers = stack
    else:
        # Outside a string the tail is a partial number, keyword or valueless
        # key (`2.`, `tru`, `"narration":`). Fall back to the last complete
        # member and drop everything after it.
        if safe is None:
            return None
        cut, open_containers = safe[0], list(safe[1])
        repaired = candidate[:cut]

    for opener in reversed(open_containers):
        repaired += "}" if opener == "{" else "]"
    return repaired


def extract_json_object(text: str, *, repair_truncated: bool = False) -> dict | None:
    """Extract the first JSON object found in `text`, tolerating ```json
    fences and surrounding prose. Returns None if nothing parses.

    `repair_truncated` is opt-in (DEF258): only the PM verdict path asks for it,
    and only after a strict read has already failed, because a repaired object
    is a partial read and the caller must disclose it as one.
    """
    if not text:
        return None
    cleaned = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    candidate = m.group(1) if m else cleaned
    if not candidate.startswith("{"):
        first = candidate.find("{")
        last = candidate.rfind("}")
        if first == -1:
            return None
        if last == -1 or last <= first:
            # DEF258: an object that opened and never closed. Without the repair
            # pass there is nothing to salvage, so keep the original rejection.
            if not repair_truncated:
                return None
            candidate = candidate[first:]
        else:
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
        pass
    # DEF352 — trailing prose AFTER a complete object.
    #
    # The trim above only runs when the reply does NOT start with `{`, so a
    # reply that opens with the object and then adds a sentence — measured
    # shape: `{...}\n\nWorked example — classroom simulation, not financial
    # advice.` — reached json.loads whole and was rejected outright, discarding
    # a decision the model had already made correctly. Measured at 42.6% of
    # Risk Officer replies on the CR201 production assembly (2026-08-21), vs
    # 1.5% on CR197's, and isolated to the simulated-portfolio block being
    # present. The JSON contract already says "No prose outside it"; P2 is
    # explicit that a prompt instruction is not a control, so this is the
    # control. Deliberately NOT gated on `repair_truncated`: nothing is being
    # repaired or guessed here — the object is complete, only the tail is cut.
    if candidate.startswith("{"):
        last = candidate.rfind("}")
        if last > 0 and last + 1 < len(candidate):
            try:
                trimmed = json.loads(candidate[: last + 1], strict=False)
            except json.JSONDecodeError:
                trimmed = None
            if isinstance(trimmed, dict):
                return trimmed
    if not repair_truncated:
        return None
    closed = _close_truncated_object(candidate)
    if closed is None:
        return None
    try:
        result = json.loads(closed, strict=False)
    except json.JSONDecodeError:
        return None
    return result if isinstance(result, dict) else None
