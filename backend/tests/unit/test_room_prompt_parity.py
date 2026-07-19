"""P4 guard — the PM prompt's verdict vocabulary must match the parser (DEF067).

failure_patterns.md P4: a value the prompt tells the model it may issue but the
parser does not understand is silently dropped to the fail-safe PASS. DEF058 and
DEF067 were both this: the base PM profile advertised MODIFY-AND-APPROVE while the
parser knew only APPROVE/PASS, so 90% of live verdicts routed through a fragile
reformatter and ~13% were lost outright.

This test assembles the REAL Portfolio Manager system prompt and asserts that
every action token the prompt enumerates as a verdict option normalises to a
known action via `_normalize_pm_action`. It fails red against the pre-DEF067
parser (MODIFY-AND-APPROVE → None) — that is the check that would have caught the
defect at commit time.
"""

from __future__ import annotations

import re

from app.schemas import AgentId
from app.services.room_prompts import build_room_messages
from app.services.room_runner import _normalize_pm_action

# Lines that actually enumerate verdict actions: a `Verdict:`/`Issue:` directive
# or the JSON schema's `"action"` field, in each case IMMEDIATELY followed by an
# all-caps token (so prose that merely mentions "the 'Verdict:' block" is not
# scanned). Action tokens are ALL-CAPS, optionally hyphenated and bolded.
_ENUM_LINE = re.compile(
    r'(?:\bIssue:\s*\**[A-Z]{3,})'
    r'|(?:\bVerdict:\s*\**[A-Z]{3,})'
    r'|(?:"action"\s*:\s*"?[A-Z]{3,})'
)
_ACTION_TOKEN = re.compile(r"[A-Z][A-Z]{2,}(?:-[A-Z]+)*")

# Caps words that share the shape of an action token but are not verdict values;
# they legitimately appear on an enumeration line and must not fail the parity.
_NON_ACTION_CAPS = {"FAIL", "REASON", "JSON", "AMI"}


def _pm_system_prompt(mandate) -> str:
    system_prompt, _ = build_room_messages(
        agent_id=AgentId.PORTFOLIO_MANAGER, mandate=mandate, user_id=None,
        ticker="AAPL", profile={"data_source": "synthetic"}, transcript=[],
        trade_proposal={"size_pct": 5.0, "entry": 100.0, "stop": 81.0},
    )
    return system_prompt


def _offered_action_tokens(prompt: str) -> set[str]:
    tokens: set[str] = set()
    for line in prompt.splitlines():
        if not _ENUM_LINE.search(line):
            continue
        for tok in _ACTION_TOKEN.findall(line):
            if tok in _NON_ACTION_CAPS:
                continue
            tokens.add(tok)
    return tokens


def test_pm_prompt_offers_at_least_the_core_actions(base_mandate):
    """Sanity: the extractor actually finds the verdict vocabulary, so a green
    parity result means 'all understood', never 'found nothing'."""
    tokens = _offered_action_tokens(_pm_system_prompt(base_mandate))
    assert {"APPROVE", "PASS"} <= tokens
    # The base PM profile still advertises the modify form — the exact token
    # that broke DEF067. If this ever disappears, revisit the profile too.
    assert any("MODIFY" in t for t in tokens)


def test_every_offered_pm_action_is_understood_by_the_parser(base_mandate):
    """P4: no verdict token the prompt offers may be unknown to the parser."""
    prompt = _pm_system_prompt(base_mandate)
    unknown = {
        tok for tok in _offered_action_tokens(prompt)
        if _normalize_pm_action(tok) is None
    }
    assert not unknown, (
        f"PM prompt offers action tokens the parser drops to PASS: {sorted(unknown)}. "
        "Add them to _PM_ACTION_SYNONYMS or remove them from the prompt (DEF067/P4)."
    )
