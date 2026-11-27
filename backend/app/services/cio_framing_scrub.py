"""DEF554 - strip the CIO prompt's classroom framing from user-visible verdict text.

The CIO's system prompt (`content/agents/portfolio_manager.md` line 10 and the safety floor in
`app/agents/safety_floor.py`) tells the model each verdict is "a worked example", asks for the tag
"Worked example - classroom simulation, not financial advice.", and calls the Room "a simulation-only
training exercise". The model echoes that framing into `verdict.reason` ("This is a worked example
... Here is the reasoning behind the approval"). A prompt is not a control (CR038), so this is the
control: a deterministic, sentence-level removal applied once, at `room_runner._guard_pm_text`, to
both the CIO text and `verdict.reason`.

Only the framing sentence (or the "Here is the reasoning behind ...:" lead-in clause) is removed; the
reasoning around it is kept byte for byte. Text with no framing is returned unchanged (same object).
The app's own coded disclaimer ("Educational simulation. Not investment advice.") uses different
wording on purpose and is never matched.
"""

from __future__ import annotations

import re

_LEAD_IN = re.compile(
    r"here(?:'s| is) the (?:reasoning|rationale|logic) behind (?:the|this|my|our) "
    r"(?:approval|decision|verdict|rejection|pass|call|recommendation)[^.:\n]*:[ \t]*",
    re.IGNORECASE,
)

_FRAMING = re.compile(
    r"worked[- ]example"
    r"|classroom (?:simulation|exercise|setting)"
    r"|(?:simulation-only|simulated) (?:classroom|training exercise)"
    r"|training exercise"
    r"|not financial advice"
    r"|how a veteran pm reasons"
    r"|here(?:'s| is) the (?:reasoning|rationale|logic) behind (?:the|this|my|our) "
    r"(?:approval|decision|verdict|rejection|pass|call|recommendation)",
    re.IGNORECASE,
)

_BOUNDARY = re.compile(r"(\n+|(?<=[.!?])[ \t]+)")


def scrub_cio_framing(text: str) -> str:
    """Return `text` with sentences that echo the CIO prompt's classroom framing removed."""
    if not text or not (_FRAMING.search(text)):
        return text
    text = _LEAD_IN.sub("", text)
    if not _FRAMING.search(text):
        return text
    parts = _BOUNDARY.split(text)
    kept: list[str] = []
    for i in range(0, len(parts), 2):
        sentence = parts[i]
        sep = parts[i + 1] if i + 1 < len(parts) else ""
        if sentence and _FRAMING.search(sentence):
            continue
        kept.append(sentence)
        kept.append(sep)
    out = "".join(kept).rstrip()
    return out if out.strip() else text
