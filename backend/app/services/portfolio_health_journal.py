"""CR136 M08 — maps a rendered Portfolio Health Finding (M06 artefact) to its Decision Journal entry (pure mapper, no DB access).

One place builds the entry. M06 originally assembled the payload inline at the
point of writing it, which meant the artefact's shape — the thing M07, M09 and
CR137 all read — was a dict literal in the middle of an orchestrator rather than
something with a name and a validator. This module is that name.

The validation is the point, not paperwork. F19 makes the archived Finding carry
its own disclosures forever, because it is a permanent record a user can reopen
in a year and screenshot; a Finding stored without them is a report that will
outlive every caveat that was true when it was written. So a missing or empty
disclosure raises rather than storing a slightly-wrong artefact (CR040).
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.schemas.journal import EntryType, JournalEntryCreate
from app.services.portfolio_health_constants import PORTFOLIO_HEALTH_ENTRY_TYPE

SECTION_KEYS = ("head", "f1", "f2", "f3", "f4", "f5")
FINDING_TAGS = ["portfolio_health", "cr136"]
VALID_RULE_STATES = frozenset({"fired", "cleared"})


def finding_dedupe_key(portfolio_id: UUID | str, as_of: str) -> str:
    """`uq_journal_dedupe`'s value for a Finding — the one place it is spelled.

    Two concurrent POSTs both clear the idempotency check, and this key is what
    lets the database decide between them (measured: five concurrent requests
    produced five Findings against a daily cap of two before the constraint
    existed).
    """
    return f"{portfolio_id}:{as_of}"


def build_finding_entry(
    *,
    user_id: UUID,
    portfolio_id: UUID,
    as_of: str | date,
    sections: dict[str, str],
    context: dict,
    fired_rules: list[dict],
    rule_states: dict[str, str],
    engine_version: str,
    summary: str | None = None,
    llm_used: bool = False,
    llm_rejected_reason: str | None = None,
) -> JournalEntryCreate:
    """The Finding, as a journal entry. Pure — no DB, no clock, no LLM."""
    as_of_str = as_of.isoformat() if isinstance(as_of, date) else str(as_of)

    missing = [key for key in SECTION_KEYS if key not in sections]
    if missing:
        raise ValueError(
            f"Finding sections missing {missing} — the stored artefact is the "
            f"one a user reopens in a year, and a section that is absent at "
            f"write time is absent forever"
        )
    unexpected = sorted(set(sections) - set(SECTION_KEYS))
    if unexpected:
        # The doc pins the key set as EQUAL, not a superset. A stray key would
        # be stored forever and rendered by nothing — the mobile renderer walks
        # a fixed order — so it is content that silently never reaches the user.
        raise ValueError(
            f"Finding sections carry unexpected keys {unexpected} — the "
            f"renderer walks a fixed order, so anything outside {list(SECTION_KEYS)} "
            f"is stored forever and shown to nobody"
        )
    for key in SECTION_KEYS:
        value = sections[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Finding section {key!r} is empty — F19 requires the archived "
                f"artefact to carry its own disclosures and its own content; "
                f"storing a blank section publishes a report with a hole in it"
            )

    bad_states = {
        rule: state for rule, state in rule_states.items()
        if state not in VALID_RULE_STATES
    }
    if bad_states:
        raise ValueError(
            f"rule_states {bad_states} outside {sorted(VALID_RULE_STATES)} — "
            f"an unrecognised state reads as 'cleared' on the next run, which "
            f"silently drops a fired rule's hysteresis memory"
        )

    return JournalEntryCreate(
        user_id=user_id,
        entry_type=EntryType(PORTFOLIO_HEALTH_ENTRY_TYPE),
        # `reference_id = portfolio_id` per build/README's seam register, which
        # overrides this module's own doc: M07 reads Findings by portfolio, and
        # a null reference would make that a payload scan.
        reference_id=portfolio_id,
        title=f"Portfolio Health — Finding {as_of_str}",
        summary=summary,
        ticker=None,          # keeps Findings out of the per-ticker Room lookback
        agents_involved=[],   # deterministic engine; agents arrive with CR137
        tags=list(FINDING_TAGS),
        outcome=None,
        dedupe_key=finding_dedupe_key(portfolio_id, as_of_str),
        payload={
            "engine_version": engine_version,
            "portfolio_id": str(portfolio_id),
            "as_of": as_of_str,
            "sections": dict(sections),
            "context": context,
            "rules_fired": fired_rules,
            "rule_states": rule_states,
            "llm_used": llm_used,
            "llm_rejected_reason": llm_rejected_reason,
        },
    )
